import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR


def load_raw_data(filename="europa_league_complete.csv"):
    filepath = RAW_DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {filepath}")
    df = pd.read_csv(filepath, parse_dates=["date"])
    print(f"[LOAD] {len(df)} registros cargados desde {filepath}")
    return df


def clean_matches(df):
    required = ["home_team", "away_team", "home_goals", "away_goals", "result"]
    available = [c for c in required if c in df.columns]
    df = df.dropna(subset=available)

    if "home_team" in df.columns:
        df["home_team"] = df["home_team"].str.strip()
        df["away_team"] = df["away_team"].str.strip()

    for col in ["home_goals", "away_goals", "ht_home_goals", "ht_away_goals"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "result" in df.columns:
        df["result"] = df["result"].str.strip().str.upper()
        df = df[df["result"].isin(["H", "A", "D"])]

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if "odds" in col or "prob" in col or col.endswith(("_home", "_draw", "_away")):
            df[col] = df[col].clip(lower=0)

    df = df.drop_duplicates(subset=["date", "home_team", "away_team"], keep="first")

    print(f"[CLEAN] {len(df)} registros después de limpieza")
    return df


def compute_team_form(df):
    if "date" not in df.columns:
        return df

    df = df.sort_values("date").reset_index(drop=True)

    teams = set(df["home_team"].unique()) | set(df["away_team"].unique())
    team_stats = {t: {"wins": 0, "draws": 0, "losses": 0, "goals_for": 0, "goals_against": 0, "last5": []} for t in teams}

    win_streaks = []
    loss_streaks = []
    form_last5_home = []
    form_last5_away = []
    home_avg_gf = []
    home_avg_ga = []
    away_avg_gf = []
    away_avg_ga = []

    for _, row in df.iterrows():
        ht = row["home_team"]
        at = row["away_team"]
        r = row.get("result")

        hs = team_stats[ht]
        ast = team_stats[at]

        h_total = hs["wins"] + hs["draws"] + hs["losses"]
        a_total = ast["wins"] + ast["draws"] + ast["losses"]

        form_last5_home.append("".join(hs["last5"][-5:]) if hs["last5"] else "")
        form_last5_away.append("".join(ast["last5"][-5:]) if ast["last5"] else "")

        h_streak = 0
        for res in reversed(hs["last5"]):
            if res == "W":
                h_streak += 1
            else:
                break

        a_streak = 0
        for res in reversed(ast["last5"]):
            if res == "L":
                a_streak += 1
            else:
                break

        win_streaks.append(h_streak)
        loss_streaks.append(a_streak)

        home_avg_gf.append(hs["goals_for"] / max(h_total, 1))
        home_avg_ga.append(hs["goals_against"] / max(h_total, 1))
        away_avg_gf.append(ast["goals_for"] / max(a_total, 1))
        away_avg_ga.append(ast["goals_against"] / max(a_total, 1))

        hg = row.get("home_goals", 0) or 0
        ag = row.get("away_goals", 0) or 0

        if r == "H":
            hs["wins"] += 1
            hs["last5"].append("W")
            ast["losses"] += 1
            ast["last5"].append("L")
        elif r == "A":
            hs["losses"] += 1
            hs["last5"].append("L")
            ast["wins"] += 1
            ast["last5"].append("W")
        elif r == "D":
            hs["draws"] += 1
            hs["last5"].append("D")
            ast["draws"] += 1
            ast["last5"].append("D")

        hs["goals_for"] += hg
        hs["goals_against"] += ag
        ast["goals_for"] += ag
        ast["goals_against"] += hg

    df["home_win_streak"] = win_streaks
    df["away_loss_streak"] = loss_streaks
    df["home_form_last5"] = form_last5_home
    df["away_form_last5"] = form_last5_away
    df["home_avg_goals_scored"] = home_avg_gf
    df["home_avg_goals_conceded"] = home_avg_ga
    df["away_avg_goals_scored"] = away_avg_gf
    df["away_avg_goals_conceded"] = away_avg_ga

    print(f"[FORM] Forma de equipo calculada para {len(teams)} equipos")
    return df


def flag_anomalies(df):
    flags = pd.DataFrame(index=df.index)

    if "odds_movement_abs_max" in df.columns:
        flags["flag_odds_movement"] = (df["odds_movement_abs_max"].abs() > 0.15).astype(int)

    if "result_surprise" in df.columns:
        flags["flag_result_surprise"] = df["result_surprise"]

    if "home_win_streak" in df.columns and "result" in df.columns:
        flags["flag_streak_break"] = (
            (df["home_win_streak"] >= 5) & (df["result"] == "A")
        ).astype(int)

    if "home_avg_goals_scored" in df.columns and "home_goals" in df.columns:
        flags["flag_goals_anomaly_home"] = (
            df["home_goals"] > df["home_avg_goals_scored"] * 4
        ).astype(int)
        flags["flag_goals_anomaly_away"] = (
            df["away_goals"] > df["away_avg_goals_scored"] * 4
        ).astype(int)

    if "ht_result_changed" in df.columns:
        flags["flag_ht_result_changed"] = df["ht_result_changed"]

    if "total_cards" in df.columns:
        mean_cards = df["total_cards"].mean()
        std_cards = df["total_cards"].std()
        if std_cards > 0:
            flags["flag_cards_anomaly"] = (
                (df["total_cards"] - mean_cards) / std_cards > 2
            ).astype(int)

    flag_cols = [c for c in flags.columns if c.startswith("flag_")]
    if flag_cols:
        flags["total_flags"] = flags[flag_cols].sum(axis=1)

    for col in flags.columns:
        df[col] = flags[col]

    flagged = df[df.get("total_flags", 0) > 0]
    print(f"[FLAGS] {len(flagged)} partidos con al menos 1 anomalía detectada")
    return df


def process_and_save(input_file="europa_league_complete.csv", output_file="europa_league_processed.csv"):
    df = load_raw_data(input_file)
    df = clean_matches(df)
    df = compute_team_form(df)
    df = flag_anomalies(df)

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DATA_DIR / output_file
    df.to_csv(output_path, index=False)
    print(f"\n[SAVED] Datos procesados guardados en: {output_path}")
    print(f"  Filas: {len(df)}")
    print(f"  Columnas: {len(df.columns)}")

    flag_cols = [c for c in df.columns if c.startswith("flag_")]
    if flag_cols:
        print(f"\n  --- Resumen de anomalías ---")
        for col in flag_cols:
            count = df[col].sum()
            pct = count / len(df) * 100
            print(f"  {col}: {int(count)} ({pct:.1f}%)")

    return df, output_path


if __name__ == "__main__":
    df, path = process_and_save()
