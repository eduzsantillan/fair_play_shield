import pandas as pd
import numpy as np
from scipy import stats
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score, precision_score, recall_score, f1_score
import joblib
from pathlib import Path
import sys
import os
import warnings
warnings.filterwarnings("ignore")

try:
    import mlflow
    import mlflow.sklearn
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import PROCESSED_DATA_DIR, MATCH_INTEGRITY_THRESHOLDS

MODEL_DIR = Path(__file__).resolve().parent / "trained"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001")
MLFLOW_EXPERIMENT_NAME = "fair_play_shield"


FEATURE_COLS_LEAGUES = [
    "odds_movement_abs_max",
    "result_surprise",
    "ht_result_changed",
    "total_goals",
    "total_cards",
    "flag_odds_movement",
    "flag_result_surprise",
    "flag_streak_break",
    "flag_goals_anomaly_home",
    "flag_goals_anomaly_away",
    "flag_ht_result_changed",
    "flag_cards_anomaly",
]

FEATURE_COLS_EL = [
    "total_goals",
    "goal_difference",
    "ht_result_changed",
    "total_cards",
    "total_fouls",
    "total_corners",
    "home_possession",
    "away_possession",
    "home_shots_on_target",
    "away_shots_on_target",
]


class IntegrityScorer:

    def __init__(self):
        self.scaler = StandardScaler()
        self.isolation_forest = IsolationForest(
            contamination=0.08,
            n_estimators=200,
            max_samples="auto",
            random_state=42,
        )
        self.random_forest = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=5,
            random_state=42,
            class_weight="balanced",
        )
        self.logistic = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        )
        self.feature_cols = []
        self.is_fitted = False

    def prepare_features(self, df, feature_cols):
        available = [c for c in feature_cols if c in df.columns]
        if not available:
            raise ValueError(f"No feature columns available. Tried: {feature_cols}")
        self.feature_cols = available
        X = df[available].copy()
        X = X.fillna(0)
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce").fillna(0)
        return X

    def create_synthetic_labels(self, df, X):
        labels = pd.Series(0, index=df.index)

        if "total_flags" in df.columns:
            labels[df["total_flags"] >= 3] = 1
        else:
            flag_cols = [c for c in df.columns if c.startswith("flag_")]
            if flag_cols:
                flag_sum = df[flag_cols].sum(axis=1)
                labels[flag_sum >= 3] = 1

        if "odds_movement_abs_max" in df.columns:
            threshold = df["odds_movement_abs_max"].quantile(0.95)
            labels[df["odds_movement_abs_max"] > threshold] = 1

        if "total_goals" in df.columns:
            goals_mean = df["total_goals"].mean()
            goals_std = df["total_goals"].std()
            if goals_std > 0:
                z_goals = (df["total_goals"] - goals_mean) / goals_std
                labels[z_goals.abs() > 2.5] = 1

        print(f"  Labels: {(labels == 0).sum()} normal, {(labels == 1).sum()} sospechoso ({labels.mean()*100:.1f}%)")
        return labels

    def fit(self, df, feature_cols=None, log_to_mlflow=True):
        if feature_cols is None:
            feature_cols = FEATURE_COLS_LEAGUES
        X = self.prepare_features(df, feature_cols)
        y = self.create_synthetic_labels(df, X)

        print(f"\n  Entrenando con {len(X)} partidos, {len(self.feature_cols)} features...")

        X_scaled = self.scaler.fit_transform(X)

        print("  [1/3] Isolation Forest...")
        self.isolation_forest.fit(X_scaled)
        iso_scores = self.isolation_forest.decision_function(X_scaled)
        iso_labels = self.isolation_forest.predict(X_scaled)
        iso_anomalies = (iso_labels == -1).sum()
        print(f"        Anomalías detectadas: {iso_anomalies} ({iso_anomalies/len(X)*100:.1f}%)")

        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )

        print("  [2/3] Random Forest...")
        self.random_forest.fit(X_train, y_train)
        rf_pred = self.random_forest.predict(X_test)
        rf_proba = self.random_forest.predict_proba(X_test)[:, 1]
        rf_auc = roc_auc_score(y_test, rf_proba) if y_test.nunique() > 1 else 0
        rf_precision = precision_score(y_test, rf_pred, zero_division=0)
        rf_recall = recall_score(y_test, rf_pred, zero_division=0)
        rf_f1 = f1_score(y_test, rf_pred, zero_division=0)
        print(f"        AUC-ROC: {rf_auc:.4f}")
        print(classification_report(y_test, rf_pred, target_names=["Normal", "Sospechoso"], zero_division=0))

        print("  [3/3] Logistic Regression...")
        self.logistic.fit(X_train, y_train)
        lr_pred = self.logistic.predict(X_test)
        lr_proba = self.logistic.predict_proba(X_test)[:, 1]
        lr_auc = roc_auc_score(y_test, lr_proba) if y_test.nunique() > 1 else 0
        lr_precision = precision_score(y_test, lr_pred, zero_division=0)
        lr_recall = recall_score(y_test, lr_pred, zero_division=0)
        lr_f1 = f1_score(y_test, lr_pred, zero_division=0)
        print(f"        AUC-ROC: {lr_auc:.4f}")

        print("\n  Feature Importance (Random Forest):")
        importances = pd.Series(
            self.random_forest.feature_importances_, index=self.feature_cols
        ).sort_values(ascending=False)
        for feat, imp in importances.items():
            bar = "█" * int(imp * 50)
            print(f"    {feat:35s} {imp:.4f} {bar}")

        self.metrics_ = {
            "iso_anomalies_pct": iso_anomalies / len(X) * 100,
            "rf_auc": rf_auc,
            "rf_precision": rf_precision,
            "rf_recall": rf_recall,
            "rf_f1": rf_f1,
            "lr_auc": lr_auc,
            "lr_precision": lr_precision,
            "lr_recall": lr_recall,
            "lr_f1": lr_f1,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "suspicious_pct": y.mean() * 100,
        }
        self.feature_importances_ = importances.to_dict()

        self.is_fitted = True
        return self

    def score(self, df):
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X = self.prepare_features(df, self.feature_cols)
        X_scaled = self.scaler.transform(X)

        iso_scores_raw = self.isolation_forest.decision_function(X_scaled)
        iso_norm = 1 - (iso_scores_raw - iso_scores_raw.min()) / (iso_scores_raw.max() - iso_scores_raw.min() + 1e-8)

        rf_proba = self.random_forest.predict_proba(X_scaled)[:, 1]

        lr_proba = self.logistic.predict_proba(X_scaled)[:, 1]

        combined = (0.35 * iso_norm + 0.40 * rf_proba + 0.25 * lr_proba)

        integrity_score = (combined * 100).clip(0, 100)

        alert_levels = pd.cut(
            integrity_score,
            bins=[-1, 30, 60, 80, 101],
            labels=["normal", "monitor", "suspicious", "high_alert"],
        )

        results = df[["date", "home_team", "away_team"]].copy() if all(c in df.columns for c in ["date", "home_team", "away_team"]) else df.iloc[:, :3].copy()
        results["integrity_score"] = integrity_score.round(2)
        results["alert_level"] = alert_levels
        results["iso_score"] = (iso_norm * 100).round(2)
        results["rf_score"] = (rf_proba * 100).round(2)
        results["lr_score"] = (lr_proba * 100).round(2)

        if "home_goals" in df.columns:
            results["home_goals"] = df["home_goals"]
            results["away_goals"] = df["away_goals"]
            results["result"] = df["result"]

        if "season" in df.columns:
            results["season"] = df["season"]
        if "league_name" in df.columns:
            results["league_name"] = df["league_name"]

        return results

    def save(self, prefix="fps"):
        joblib.dump(self.scaler, MODEL_DIR / f"{prefix}_scaler.pkl")
        joblib.dump(self.isolation_forest, MODEL_DIR / f"{prefix}_isolation_forest.pkl")
        joblib.dump(self.random_forest, MODEL_DIR / f"{prefix}_random_forest.pkl")
        joblib.dump(self.logistic, MODEL_DIR / f"{prefix}_logistic.pkl")
        joblib.dump(self.feature_cols, MODEL_DIR / f"{prefix}_feature_cols.pkl")
        print(f"  [SAVED] Modelos guardados en {MODEL_DIR}/")

    def load(self, prefix="fps"):
        self.scaler = joblib.load(MODEL_DIR / f"{prefix}_scaler.pkl")
        self.isolation_forest = joblib.load(MODEL_DIR / f"{prefix}_isolation_forest.pkl")
        self.random_forest = joblib.load(MODEL_DIR / f"{prefix}_random_forest.pkl")
        self.logistic = joblib.load(MODEL_DIR / f"{prefix}_logistic.pkl")
        self.feature_cols = joblib.load(MODEL_DIR / f"{prefix}_feature_cols.pkl")
        self.is_fitted = True
        print(f"  [LOADED] Modelos cargados ({len(self.feature_cols)} features)")


def setup_mlflow():
    if not MLFLOW_AVAILABLE:
        print("[MLFLOW] MLflow no disponible, continuando sin tracking")
        return False
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
        print(f"[MLFLOW] Conectado a {MLFLOW_TRACKING_URI}")
        return True
    except Exception as e:
        print(f"[MLFLOW] Error conectando: {e}")
        return False


def log_to_mlflow(scorer, results, df):
    if not MLFLOW_AVAILABLE:
        return

    with mlflow.start_run(run_name=f"training_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"):
        mlflow.log_param("isolation_forest_contamination", 0.08)
        mlflow.log_param("isolation_forest_n_estimators", 200)
        mlflow.log_param("random_forest_n_estimators", 200)
        mlflow.log_param("random_forest_max_depth", 10)
        mlflow.log_param("random_forest_min_samples_leaf", 5)
        mlflow.log_param("logistic_max_iter", 1000)
        mlflow.log_param("ensemble_weight_if", 0.35)
        mlflow.log_param("ensemble_weight_rf", 0.40)
        mlflow.log_param("ensemble_weight_lr", 0.25)
        mlflow.log_param("n_features", len(scorer.feature_cols))
        mlflow.log_param("features", ",".join(scorer.feature_cols))
        mlflow.log_param("total_matches", len(df))

        for metric_name, metric_value in scorer.metrics_.items():
            mlflow.log_metric(metric_name, metric_value)

        alert_dist = results["alert_level"].value_counts()
        for level in ["normal", "monitor", "suspicious", "high_alert"]:
            count = alert_dist.get(level, 0)
            mlflow.log_metric(f"alert_{level}_count", count)
            mlflow.log_metric(f"alert_{level}_pct", count / len(results) * 100)

        mlflow.log_metric("avg_integrity_score", results["integrity_score"].mean())
        mlflow.log_metric("max_integrity_score", results["integrity_score"].max())

        mlflow.sklearn.log_model(scorer.isolation_forest, "isolation_forest")
        mlflow.sklearn.log_model(scorer.random_forest, "random_forest")
        mlflow.sklearn.log_model(scorer.logistic, "logistic_regression")

        importance_df = pd.DataFrame([scorer.feature_importances_]).T
        importance_df.columns = ["importance"]
        importance_df = importance_df.sort_values("importance", ascending=False)
        importance_path = MODEL_DIR / "feature_importance.csv"
        importance_df.to_csv(importance_path)
        mlflow.log_artifact(str(importance_path))

        print(f"[MLFLOW] Run logged successfully")


def score_only(prefix="fps_leagues"):
    print("=" * 60)
    print("FAIR PLAY SHIELD — Scoring con modelo existente")
    print("=" * 60)

    leagues_path = PROCESSED_DATA_DIR / "european_leagues_with_odds_processed.csv"
    if not leagues_path.exists():
        print(f"[ERROR] No se encontró: {leagues_path}")
        return None

    model_path = MODEL_DIR / f"{prefix}_scaler.pkl"
    if not model_path.exists():
        print(f"[ERROR] Modelo '{prefix}' no encontrado. Ejecuta train_and_score() primero.")
        return None

    df = pd.read_csv(leagues_path, parse_dates=["date"], low_memory=False)
    print(f"\nDatos cargados: {len(df)} partidos")

    scorer = IntegrityScorer()
    scorer.load(prefix)

    results = scorer.score(df)

    print("\n--- Distribución de alertas ---")
    alert_dist = results["alert_level"].value_counts()
    for level in ["normal", "monitor", "suspicious", "high_alert"]:
        count = alert_dist.get(level, 0)
        pct = count / len(results) * 100
        emoji = {"normal": "🟢", "monitor": "🟡", "suspicious": "🟠", "high_alert": "🔴"}.get(level, "")
        print(f"  {emoji} {level:15s}: {count:5d} ({pct:.1f}%)")

    output_path = PROCESSED_DATA_DIR / "integrity_scores.csv"
    results.to_csv(output_path, index=False)
    print(f"\n[SAVED] Scores guardados en: {output_path}")

    return results


def train_and_score():
    print("=" * 60)
    print("FAIR PLAY SHIELD — Entrenamiento de modelos")
    print("=" * 60)

    mlflow_enabled = setup_mlflow()

    leagues_path = PROCESSED_DATA_DIR / "european_leagues_with_odds_processed.csv"
    if not leagues_path.exists():
        print(f"[ERROR] No se encontró: {leagues_path}")
        return None, None

    df = pd.read_csv(leagues_path, parse_dates=["date"], low_memory=False)
    print(f"\nDatos cargados: {len(df)} partidos")

    scorer = IntegrityScorer()
    scorer.fit(df, feature_cols=FEATURE_COLS_LEAGUES)
    scorer.save("fps_leagues")

    results = scorer.score(df)

    print("\n" + "=" * 60)
    print("RESULTADOS DEL SCORING")
    print("=" * 60)

    print("\n--- Distribución de alertas ---")
    alert_dist = results["alert_level"].value_counts()
    for level in ["normal", "monitor", "suspicious", "high_alert"]:
        count = alert_dist.get(level, 0)
        pct = count / len(results) * 100
        emoji = {"normal": "🟢", "monitor": "🟡", "suspicious": "🟠", "high_alert": "🔴"}.get(level, "")
        print(f"  {emoji} {level:15s}: {count:5d} ({pct:.1f}%)")

    print("\n--- Top 20 partidos más sospechosos ---")
    top = results.sort_values("integrity_score", ascending=False).head(20)
    display_cols = ["date", "home_team", "away_team", "home_goals", "away_goals",
                    "result", "integrity_score", "alert_level"]
    available = [c for c in display_cols if c in top.columns]
    print(top[available].to_string(index=False))

    output_path = PROCESSED_DATA_DIR / "integrity_scores.csv"
    results.to_csv(output_path, index=False)
    print(f"\n[SAVED] Scores guardados en: {output_path}")

    if "league_name" in results.columns:
        print("\n--- Sospecha promedio por liga ---")
        league_avg = results.groupby("league_name")["integrity_score"].agg(["mean", "max", "count"])
        league_avg = league_avg.sort_values("mean", ascending=False)
        print(league_avg.to_string())

    if mlflow_enabled:
        log_to_mlflow(scorer, results, df)

    return scorer, results


if __name__ == "__main__":
    scorer, results = train_and_score()
