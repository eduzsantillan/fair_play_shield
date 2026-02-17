import pandas as pd
import requests
from io import StringIO
from pathlib import Path
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import RAW_DATA_DIR, FOOTBALL_DATA_BASE_URL

LEAGUE_CODES = {
    "SP1": "La Liga (España)",
    "D1": "Bundesliga (Alemania)",
    "I1": "Serie A (Italia)",
    "F1": "Ligue 1 (Francia)",
    "N1": "Eredivisie (Países Bajos)",
    "B1": "Jupiler League (Bélgica)",
    "P1": "Liga Portugal",
    "T1": "Süper Lig (Turquía)",
    "G1": "Super League (Grecia)",
    "E0": "Premier League (Inglaterra)",
}

SEASONS = []
for year in range(2014, 2025):
    short = f"{str(year)[-2:]}{str(year + 1)[-2:]}"
    SEASONS.append((f"{year}-{year+1}", short))


COLUMN_MAP = {
    "Div": "division",
    "Date": "date",
    "Time": "time",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "Home": "home_team",
    "Away": "away_team",
    "HG": "home_goals",
    "AG": "away_goals",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "result",
    "Res": "result",
    "HTHG": "ht_home_goals",
    "HTAG": "ht_away_goals",
    "HTR": "ht_result",
    "Referee": "referee",
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HC": "home_corners",
    "AC": "away_corners",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HY": "home_yellow_cards",
    "AY": "away_yellow_cards",
    "HR": "home_red_cards",
    "AR": "away_red_cards",
    "B365H": "b365_home",
    "B365D": "b365_draw",
    "B365A": "b365_away",
    "BWH": "bw_home",
    "BWD": "bw_draw",
    "BWA": "bw_away",
    "IWH": "iw_home",
    "IWD": "iw_draw",
    "IWA": "iw_away",
    "PSH": "ps_home",
    "PSD": "ps_draw",
    "PSA": "ps_away",
    "WHH": "wh_home",
    "WHD": "wh_draw",
    "WHA": "wh_away",
    "VCH": "vc_home",
    "VCD": "vc_draw",
    "VCA": "vc_away",
    "PSCH": "ps_close_home",
    "PSCD": "ps_close_draw",
    "PSCA": "ps_close_away",
    "MaxH": "max_home",
    "MaxD": "max_draw",
    "MaxA": "max_away",
    "AvgH": "avg_home",
    "AvgD": "avg_draw",
    "AvgA": "avg_away",
    "Max>2.5": "max_over25",
    "Max<2.5": "max_under25",
    "Avg>2.5": "avg_over25",
    "Avg<2.5": "avg_under25",
    "BbMxH": "bb_max_home",
    "BbMxD": "bb_max_draw",
    "BbMxA": "bb_max_away",
    "BbAvH": "bb_avg_home",
    "BbAvD": "bb_avg_draw",
    "BbAvA": "bb_avg_away",
    "BbMx>2.5": "bb_max_over25",
    "BbMx<2.5": "bb_max_under25",
    "BbAv>2.5": "bb_avg_over25",
    "BbAv<2.5": "bb_avg_under25",
    "BbOU": "bb_num_ou_bookmakers",
    "Bb1X2": "bb_num_1x2_bookmakers",
}


def download_csv(url, label):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.text
        if not content.strip():
            return None
        df = pd.read_csv(StringIO(content), on_bad_lines="skip")
        if df.empty or len(df.columns) < 5:
            return None
        df = df.dropna(how="all")
        df = df.dropna(subset=df.columns[:5], how="all")
        return df
    except Exception:
        return None


def normalize_columns(df):
    rename_dict = {}
    for col in df.columns:
        clean = col.strip()
        if clean in COLUMN_MAP:
            rename_dict[col] = COLUMN_MAP[clean]
        else:
            rename_dict[col] = clean.lower().replace(" ", "_").replace(">", "over").replace("<", "under")
    return df.rename(columns=rename_dict)


def parse_dates(df):
    if "date" not in df.columns:
        return df
    for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]:
        try:
            df["date"] = pd.to_datetime(df["date"], format=fmt)
            return df
        except (ValueError, TypeError):
            continue
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    return df


def compute_odds_features(df):
    home_odds = [c for c in df.columns if c.endswith("_home") and "team" not in c and "goal" not in c and "shot" not in c and "corner" not in c and "foul" not in c and "card" not in c]
    draw_odds = [c for c in df.columns if c.endswith("_draw")]
    away_odds = [c for c in df.columns if c.endswith("_away") and "team" not in c and "goal" not in c and "shot" not in c and "corner" not in c and "foul" not in c and "card" not in c]

    if home_odds:
        df["avg_odds_home"] = df[home_odds].mean(axis=1)
    if draw_odds:
        df["avg_odds_draw"] = df[draw_odds].mean(axis=1)
    if away_odds:
        df["avg_odds_away"] = df[away_odds].mean(axis=1)

    if "ps_home" in df.columns and "ps_close_home" in df.columns:
        for suffix in ["home", "draw", "away"]:
            open_col = f"ps_{suffix}"
            close_col = f"ps_close_{suffix}"
            if open_col in df.columns and close_col in df.columns:
                df[f"odds_movement_{suffix}"] = (df[close_col] - df[open_col]) / df[open_col].replace(0, float("nan"))
        move_cols = [c for c in df.columns if c.startswith("odds_movement_")]
        if move_cols:
            df["odds_movement_abs_max"] = df[move_cols].abs().max(axis=1)

    if "avg_odds_home" in df.columns:
        df["implied_prob_home"] = 1 / df["avg_odds_home"]
        df["implied_prob_draw"] = 1 / df["avg_odds_draw"]
        df["implied_prob_away"] = 1 / df["avg_odds_away"]
        prob_sum = df["implied_prob_home"] + df["implied_prob_draw"] + df["implied_prob_away"]
        df["overround"] = prob_sum - 1
        df["norm_prob_home"] = df["implied_prob_home"] / prob_sum
        df["norm_prob_draw"] = df["implied_prob_draw"] / prob_sum
        df["norm_prob_away"] = df["implied_prob_away"] / prob_sum
        expected = df[["norm_prob_home", "norm_prob_draw", "norm_prob_away"]].idxmax(axis=1)
        df["expected_result"] = expected.map({"norm_prob_home": "H", "norm_prob_draw": "D", "norm_prob_away": "A"})
        if "result" in df.columns:
            df["result_surprise"] = (df["result"] != df["expected_result"]).astype(int)

    return df


def compute_match_features(df):
    if "home_goals" in df.columns and "away_goals" in df.columns:
        df["total_goals"] = df["home_goals"] + df["away_goals"]
        df["goal_difference"] = df["home_goals"] - df["away_goals"]

    if "ht_home_goals" in df.columns:
        df["ht_total_goals"] = df["ht_home_goals"] + df["ht_away_goals"]
        df["second_half_home_goals"] = df["home_goals"] - df["ht_home_goals"]
        df["second_half_away_goals"] = df["away_goals"] - df["ht_away_goals"]
        mask = df["ht_result"].notna() & df["result"].notna()
        df["ht_result_changed"] = 0
        df.loc[mask, "ht_result_changed"] = (df.loc[mask, "ht_result"] != df.loc[mask, "result"]).astype(int)

    if "home_shots" in df.columns:
        df["total_shots"] = df["home_shots"] + df["away_shots"]
        df["shot_accuracy_home"] = df["home_shots_on_target"] / df["home_shots"].replace(0, 1)
        df["shot_accuracy_away"] = df["away_shots_on_target"] / df["away_shots"].replace(0, 1)

    if "home_fouls" in df.columns:
        df["total_fouls"] = df["home_fouls"] + df["away_fouls"]

    if "home_yellow_cards" in df.columns:
        df["total_cards"] = df["home_yellow_cards"] + df["away_yellow_cards"]
        if "home_red_cards" in df.columns:
            df["total_cards"] += df["home_red_cards"] + df["away_red_cards"]

    if "home_corners" in df.columns:
        df["total_corners"] = df["home_corners"] + df["away_corners"]

    return df


def scrape_european_leagues(seasons_back=5, leagues=None):
    if leagues is None:
        leagues = list(LEAGUE_CODES.keys())

    all_data = []
    selected_seasons = SEASONS[-seasons_back:]

    print("=" * 60)
    print("DESCARGA DE LIGAS EUROPEAS (con cuotas de apuestas)")
    print("=" * 60)
    print(f"Ligas: {len(leagues)} | Temporadas: {len(selected_seasons)}")

    for season_name, season_code in selected_seasons:
        for league_code in leagues:
            url = f"{FOOTBALL_DATA_BASE_URL}/mmz4281/{season_code}/{league_code}.csv"
            label = f"{LEAGUE_CODES.get(league_code, league_code)} {season_name}"
            df = download_csv(url, label)
            if df is not None:
                df["season"] = season_name
                df["league_code"] = league_code
                df["league_name"] = LEAGUE_CODES.get(league_code, league_code)
                all_data.append(df)
                print(f"  [OK] {label}: {len(df)} partidos")
            else:
                print(f"  [--] {label}: no disponible")
            time.sleep(0.3)

    if not all_data:
        print("[ERROR] No se pudieron descargar datos")
        return pd.DataFrame()

    processed = []
    for df in all_data:
        df = normalize_columns(df)
        df = parse_dates(df)
        processed.append(df)

    combined = pd.concat(processed, ignore_index=True)
    combined = combined.dropna(subset=["home_team", "away_team"], how="any")
    combined = compute_odds_features(combined)
    combined = compute_match_features(combined)

    print(f"\n  Total: {len(combined)} partidos de {combined['league_name'].nunique()} ligas")
    return combined


def save_data(df, filename="european_leagues_with_odds.csv"):
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RAW_DATA_DIR / filename
    df.to_csv(filepath, index=False)
    print(f"[SAVED] {filepath} ({len(df)} filas, {len(df.columns)} columnas)")
    return filepath


def run(seasons_back=5):
    df = scrape_european_leagues(seasons_back=seasons_back)
    if df.empty:
        return None, None
    path = save_data(df)
    return df, path


if __name__ == "__main__":
    df, path = run(seasons_back=5)
    if df is not None:
        print(f"\nDescarga completada: {len(df)} partidos")
