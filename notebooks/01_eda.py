import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path
import sys
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "eda_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", palette="husl")
plt.rcParams["figure.figsize"] = (14, 6)
plt.rcParams["figure.dpi"] = 120


def load_data():
    el = pd.read_csv(RAW_DATA_DIR / "europa_league_matches.csv", parse_dates=["date"])
    leagues = pd.read_csv(
        PROCESSED_DATA_DIR / "european_leagues_with_odds_processed.csv",
        parse_dates=["date"],
        low_memory=False,
    )
    print(f"Europa League: {len(el)} partidos | {el.columns.size} columnas")
    print(f"Ligas Europeas: {len(leagues)} partidos | {leagues.columns.size} columnas")
    return el, leagues


def eda_europa_league(df):
    print("\n" + "=" * 60)
    print("EDA — UEFA EUROPA LEAGUE")
    print("=" * 60)

    print(f"\nTemporadas: {df['season'].unique()}")
    print(f"Equipos únicos: {len(set(df['home_team']) | set(df['away_team']))}")
    print(f"Estadios: {df['stadium'].nunique()}")
    print(f"Países: {df['country'].nunique()}")

    print("\n--- Distribución de resultados ---")
    result_counts = df["result"].value_counts()
    total = len(df)
    for r, c in result_counts.items():
        label = {"H": "Local", "A": "Visitante", "D": "Empate"}.get(r, r)
        print(f"  {label} ({r}): {c} ({c/total*100:.1f}%)")

    print(f"\n--- Goles ---")
    print(f"  Promedio total: {df['total_goals'].mean():.2f}")
    print(f"  Promedio local: {df['home_goals'].mean():.2f}")
    print(f"  Promedio visitante: {df['away_goals'].mean():.2f}")
    print(f"  Max goles en un partido: {df['total_goals'].max()}")

    if "attendance" in df.columns:
        att = df["attendance"].dropna()
        if len(att) > 0:
            print(f"\n--- Asistencia ---")
            print(f"  Media: {att.mean():.0f}")
            print(f"  Mediana: {att.median():.0f}")
            print(f"  Max: {att.max():.0f}")

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("EDA — UEFA Europa League", fontsize=16, fontweight="bold")

    df["result"].value_counts().plot.pie(
        ax=axes[0, 0],
        autopct="%1.1f%%",
        labels=["Local", "Empate", "Visitante"],
        colors=["#2ecc71", "#f39c12", "#e74c3c"],
    )
    axes[0, 0].set_title("Distribución de resultados")
    axes[0, 0].set_ylabel("")

    axes[0, 1].hist(df["total_goals"], bins=range(0, 12), edgecolor="white", color="#3498db", alpha=0.8)
    axes[0, 1].axvline(df["total_goals"].mean(), color="red", linestyle="--", label=f"Media: {df['total_goals'].mean():.2f}")
    axes[0, 1].set_title("Distribución de goles totales")
    axes[0, 1].set_xlabel("Goles")
    axes[0, 1].legend()

    if "home_possession" in df.columns:
        poss = df["home_possession"].dropna()
        if len(poss) > 0:
            axes[0, 2].hist(poss, bins=20, edgecolor="white", color="#9b59b6", alpha=0.8)
            axes[0, 2].set_title("Posesión local (%)")
            axes[0, 2].set_xlabel("Posesión %")

    if "ht_result_changed" in df.columns:
        ht_changed = df["ht_result_changed"].value_counts()
        ht_changed.plot.bar(ax=axes[1, 0], color=["#2ecc71", "#e74c3c"])
        axes[1, 0].set_title("Cambio resultado 1er→2do tiempo")
        axes[1, 0].set_xticklabels(["Sin cambio", "Cambió"], rotation=0)

    if "total_cards" in df.columns:
        cards = df["total_cards"].dropna()
        if len(cards) > 0:
            axes[1, 1].hist(cards, bins=range(0, 15), edgecolor="white", color="#e67e22", alpha=0.8)
            axes[1, 1].set_title("Tarjetas totales por partido")

    top_teams = df["home_team"].value_counts().head(15)
    top_teams.plot.barh(ax=axes[1, 2], color="#1abc9c")
    axes[1, 2].set_title("Top 15 equipos (como local)")
    axes[1, 2].invert_yaxis()

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "01_europa_league_eda.png", bbox_inches="tight")
    plt.close()
    print(f"\n[SAVED] {OUTPUT_DIR / '01_europa_league_eda.png'}")


def eda_leagues_betting(df):
    print("\n" + "=" * 60)
    print("EDA — LIGAS EUROPEAS + APUESTAS")
    print("=" * 60)

    print(f"\nLigas: {df['league_name'].nunique() if 'league_name' in df.columns else 'N/A'}")
    print(f"Temporadas: {df['season'].nunique()}")

    odds_cols = ["avg_odds_home", "avg_odds_draw", "avg_odds_away"]
    available_odds = [c for c in odds_cols if c in df.columns]
    if available_odds:
        print("\n--- Cuotas promedio ---")
        for c in available_odds:
            vals = df[c].dropna()
            print(f"  {c}: media={vals.mean():.2f}, mediana={vals.median():.2f}")

    if "odds_movement_abs_max" in df.columns:
        moves = df["odds_movement_abs_max"].dropna()
        print(f"\n--- Movimiento de cuotas ---")
        print(f"  Media: {moves.mean():.4f}")
        print(f"  Mediana: {moves.median():.4f}")
        print(f"  P95: {moves.quantile(0.95):.4f}")
        print(f"  P99: {moves.quantile(0.99):.4f}")
        print(f"  Max: {moves.max():.4f}")
        suspicious = (moves.abs() > 0.15).sum()
        print(f"  Movimiento >15%: {suspicious} ({suspicious/len(moves)*100:.1f}%)")

    if "result_surprise" in df.columns:
        surprises = df["result_surprise"].sum()
        print(f"\n--- Resultados sorpresa ---")
        print(f"  Total: {surprises} ({surprises/len(df)*100:.1f}%)")

    flag_cols = [c for c in df.columns if c.startswith("flag_")]
    if flag_cols:
        print(f"\n--- Flags de anomalía ---")
        for c in flag_cols:
            count = df[c].sum()
            print(f"  {c}: {int(count)} ({count/len(df)*100:.1f}%)")

        if "total_flags" in df.columns:
            print(f"\n--- Distribución de flags acumulados ---")
            for n in range(0, 6):
                count = (df["total_flags"] == n).sum()
                print(f"  {n} flags: {count} ({count/len(df)*100:.1f}%)")
            high = (df["total_flags"] >= 3).sum()
            print(f"  3+ flags (alta sospecha): {high} ({high/len(df)*100:.1f}%)")

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("EDA — Ligas Europeas + Cuotas de Apuestas", fontsize=16, fontweight="bold")

    if "avg_odds_home" in df.columns:
        df["avg_odds_home"].dropna().hist(ax=axes[0, 0], bins=50, color="#3498db", alpha=0.8, edgecolor="white")
        axes[0, 0].set_title("Distribución cuotas Local")
        axes[0, 0].set_xlabel("Cuota")
        axes[0, 0].axvline(df["avg_odds_home"].mean(), color="red", linestyle="--")

    if "odds_movement_abs_max" in df.columns:
        moves = df["odds_movement_abs_max"].dropna()
        moves_clipped = moves.clip(upper=moves.quantile(0.99))
        moves_clipped.hist(ax=axes[0, 1], bins=50, color="#e74c3c", alpha=0.8, edgecolor="white")
        axes[0, 1].axvline(0.15, color="black", linestyle="--", linewidth=2, label="Umbral 15%")
        axes[0, 1].set_title("Movimiento máx. cuotas (apertura→cierre)")
        axes[0, 1].legend()

    if "result_surprise" in df.columns and "avg_odds_home" in df.columns:
        surprise_data = df[df["result_surprise"].notna()]
        for val, color, label in [(0, "#2ecc71", "Esperado"), (1, "#e74c3c", "Sorpresa")]:
            subset = surprise_data[surprise_data["result_surprise"] == val]["avg_odds_home"].dropna()
            if len(subset) > 0:
                axes[0, 2].hist(subset, bins=40, alpha=0.5, color=color, label=label, edgecolor="white")
        axes[0, 2].set_title("Cuota local: Esperado vs Sorpresa")
        axes[0, 2].legend()

    if "total_flags" in df.columns:
        flag_dist = df["total_flags"].value_counts().sort_index()
        flag_dist.plot.bar(ax=axes[1, 0], color="#f39c12", edgecolor="white")
        axes[1, 0].set_title("Distribución de flags de anomalía")
        axes[1, 0].set_xlabel("Número de flags")

    if "league_name" in df.columns and "total_flags" in df.columns:
        league_flags = df.groupby("league_name")["total_flags"].mean().sort_values(ascending=False)
        league_flags.plot.barh(ax=axes[1, 1], color="#1abc9c")
        axes[1, 1].set_title("Media de flags por liga")
        axes[1, 1].invert_yaxis()

    if flag_cols and len(flag_cols) > 1:
        flag_corr = df[flag_cols].corr()
        sns.heatmap(flag_corr, ax=axes[1, 2], annot=True, fmt=".2f", cmap="RdYlGn_r",
                    vmin=-0.3, vmax=0.5, square=True, cbar_kws={"shrink": 0.8})
        axes[1, 2].set_title("Correlación entre flags")
        axes[1, 2].tick_params(axis="x", rotation=45)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "02_leagues_betting_eda.png", bbox_inches="tight")
    plt.close()
    print(f"\n[SAVED] {OUTPUT_DIR / '02_leagues_betting_eda.png'}")


def statistical_tests(df):
    print("\n" + "=" * 60)
    print("TESTS ESTADÍSTICOS")
    print("=" * 60)

    if "total_goals" in df.columns:
        goals = df["total_goals"].dropna()
        stat_sw, p_sw = stats.shapiro(goals.sample(min(5000, len(goals)), random_state=42))
        print(f"\n--- Shapiro-Wilk (normalidad goles) ---")
        print(f"  W={stat_sw:.4f}, p={p_sw:.6f}")
        print(f"  {'Normal' if p_sw > 0.05 else 'No normal'}")

    if "result_surprise" in df.columns and "odds_movement_abs_max" in df.columns:
        surprise = df[df["result_surprise"] == 1]["odds_movement_abs_max"].dropna()
        expected = df[df["result_surprise"] == 0]["odds_movement_abs_max"].dropna()
        if len(surprise) > 10 and len(expected) > 10:
            stat_mw, p_mw = stats.mannwhitneyu(surprise, expected, alternative="two-sided")
            print(f"\n--- Mann-Whitney U (mov. cuotas: sorpresa vs esperado) ---")
            print(f"  U={stat_mw:.2f}, p={p_mw:.6f}")
            print(f"  {'Diferencia significativa' if p_mw < 0.05 else 'Sin diferencia significativa'}")
            print(f"  Mediana sorpresa: {surprise.median():.4f}")
            print(f"  Mediana esperado: {expected.median():.4f}")

    if "league_name" in df.columns and "total_flags" in df.columns:
        groups = [g["total_flags"].dropna().values for _, g in df.groupby("league_name") if len(g) > 30]
        if len(groups) >= 2:
            stat_kw, p_kw = stats.kruskal(*groups)
            print(f"\n--- Kruskal-Wallis (flags por liga) ---")
            print(f"  H={stat_kw:.2f}, p={p_kw:.6f}")
            print(f"  {'Diferencia significativa entre ligas' if p_kw < 0.05 else 'Sin diferencia'}")

    if "result" in df.columns and "ht_result_changed" in df.columns:
        contingency = pd.crosstab(df["result"], df["ht_result_changed"].fillna(0).astype(int))
        if contingency.shape[0] >= 2 and contingency.shape[1] >= 2:
            chi2, p_chi, dof, expected_freq = stats.chi2_contingency(contingency)
            print(f"\n--- Chi² (resultado vs cambio HT) ---")
            print(f"  χ²={chi2:.2f}, p={p_chi:.6f}, dof={dof}")
            print(f"  {'Asociación significativa' if p_chi < 0.05 else 'Sin asociación'}")

    numeric_cols = ["total_goals", "total_cards", "total_fouls", "total_corners"]
    available = [c for c in numeric_cols if c in df.columns]
    if len(available) >= 2:
        print(f"\n--- Correlaciones (Spearman) ---")
        for i, c1 in enumerate(available):
            for c2 in available[i+1:]:
                valid = df[[c1, c2]].dropna()
                if len(valid) > 30:
                    rho, p = stats.spearmanr(valid[c1], valid[c2])
                    sig = "*" if p < 0.05 else ""
                    print(f"  {c1} ↔ {c2}: ρ={rho:.3f} (p={p:.4f}) {sig}")


def outlier_analysis(df):
    print("\n" + "=" * 60)
    print("ANÁLISIS DE OUTLIERS (IQR + Z-Score)")
    print("=" * 60)

    target_cols = ["total_goals", "total_cards"]
    if "odds_movement_abs_max" in df.columns:
        target_cols.append("odds_movement_abs_max")
    if "total_fouls" in df.columns:
        target_cols.append("total_fouls")

    for col in target_cols:
        if col not in df.columns:
            continue
        data = df[col].dropna()
        if len(data) < 10:
            continue

        q1 = data.quantile(0.25)
        q3 = data.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        iqr_outliers = ((data < lower) | (data > upper)).sum()

        z_scores = np.abs(stats.zscore(data))
        z_outliers = (z_scores > 2).sum()

        print(f"\n  {col}:")
        print(f"    IQR: [{lower:.2f}, {upper:.2f}] → {iqr_outliers} outliers ({iqr_outliers/len(data)*100:.1f}%)")
        print(f"    Z-Score>2: {z_outliers} outliers ({z_outliers/len(data)*100:.1f}%)")


def main():
    el, leagues = load_data()
    eda_europa_league(el)
    eda_leagues_betting(leagues)
    statistical_tests(leagues)
    outlier_analysis(leagues)

    print("\n" + "=" * 60)
    print("EDA COMPLETADO")
    print(f"Gráficos guardados en: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
