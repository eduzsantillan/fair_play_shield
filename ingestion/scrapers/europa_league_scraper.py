import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timedelta, date as _date
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.settings import RAW_DATA_DIR

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard"

_today = _date.today()
_season_start_year = _today.year if _today.month >= 7 else _today.year - 1

SEASON_RANGES = {}
for _y in range(2015, _season_start_year + 1):
    _key = f"{_y}-{_y + 1}"
    _start = f"{_y}0901"
    _end = f"{_y + 1}0601"
    SEASON_RANGES[_key] = (_start, _end)


def get_stat(stats_list, stat_name):
    for s in stats_list:
        if s.get("name") == stat_name:
            val = s.get("displayValue", s.get("value"))
            try:
                return float(val)
            except (ValueError, TypeError):
                return val
    return None


def parse_event(event):
    comp = event.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    if len(competitors) < 2:
        return None

    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

    status = comp.get("status", {}).get("type", {})
    if not status.get("completed", False):
        return None

    home_score = int(home.get("score", 0))
    away_score = int(away.get("score", 0))

    if home_score > away_score:
        result = "H"
    elif away_score > home_score:
        result = "A"
    else:
        result = "D"

    venue = comp.get("venue", event.get("venue", {}))
    address = venue.get("address", {})

    home_stats = home.get("statistics", [])
    away_stats = away.get("statistics", [])

    details = comp.get("details", [])
    home_team_id = home.get("id")
    away_team_id = away.get("id")

    home_yellow = 0
    away_yellow = 0
    home_red = 0
    away_red = 0
    goal_minutes_home = []
    goal_minutes_away = []

    for d in details:
        d_type = d.get("type", {})
        d_team = d.get("team", {}).get("id")
        type_text = d_type.get("text", "").lower()

        if "yellow" in type_text and "red" not in type_text:
            if d_team == home_team_id:
                home_yellow += 1
            else:
                away_yellow += 1
        elif "red" in type_text or "second yellow" in type_text:
            if d_team == home_team_id:
                home_red += 1
            else:
                away_red += 1

        if d.get("scoringPlay"):
            minute = d.get("clock", {}).get("displayValue", "")
            if d_team == home_team_id:
                goal_minutes_home.append(minute)
            else:
                goal_minutes_away.append(minute)

    ht_home = 0
    ht_away = 0
    for d in details:
        if d.get("scoringPlay"):
            clock_val = d.get("clock", {}).get("value", 0)
            d_team = d.get("team", {}).get("id")
            if clock_val <= 2700:
                if d_team == home_team_id:
                    ht_home += 1
                else:
                    ht_away += 1

    series = comp.get("series", {})
    round_title = series.get("title", "")
    leg = comp.get("leg", {})
    leg_display = leg.get("displayValue", "")

    season_info = event.get("season", {})

    row = {
        "date": event.get("date", ""),
        "home_team": home.get("team", {}).get("displayName", ""),
        "away_team": away.get("team", {}).get("displayName", ""),
        "home_goals": home_score,
        "away_goals": away_score,
        "ht_home_goals": ht_home,
        "ht_away_goals": ht_away,
        "result": result,
        "stadium": venue.get("fullName", ""),
        "city": address.get("city", ""),
        "country": address.get("country", ""),
        "attendance": comp.get("attendance", None),
        "round": round_title,
        "leg": leg_display,
        "tournament": "UEFA Europa League",
        "season_name": season_info.get("displayName", ""),
        "home_form": home.get("form", ""),
        "away_form": away.get("form", ""),
        "home_fouls": get_stat(home_stats, "foulsCommitted"),
        "away_fouls": get_stat(away_stats, "foulsCommitted"),
        "home_corners": get_stat(home_stats, "wonCorners"),
        "away_corners": get_stat(away_stats, "wonCorners"),
        "home_shots_on_target": get_stat(home_stats, "shotsOnTarget"),
        "away_shots_on_target": get_stat(away_stats, "shotsOnTarget"),
        "home_possession": get_stat(home_stats, "possessionPct"),
        "away_possession": get_stat(away_stats, "possessionPct"),
        "home_yellow_cards": home_yellow,
        "away_yellow_cards": away_yellow,
        "home_red_cards": home_red,
        "away_red_cards": away_red,
        "goal_minutes_home": ",".join(goal_minutes_home),
        "goal_minutes_away": ",".join(goal_minutes_away),
        "match_id_espn": event.get("id", ""),
    }
    return row


def generate_dates(start_str, end_str):
    start = datetime.strptime(start_str, "%Y%m%d")
    end = datetime.strptime(end_str, "%Y%m%d")
    today = datetime.now()
    if end > today:
        end = today
    current = start
    dates = []
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return dates


def scrape_season(season_name, start_date, end_date):
    all_matches = []
    dates = generate_dates(start_date, end_date)
    checked = 0
    empty_streak = 0

    for date_str in dates:
        url = f"{ESPN_BASE}?dates={date_str}"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            events = data.get("events", [])
            checked += 1

            if not events:
                empty_streak += 1
                if checked > 30 and empty_streak > 20 and not all_matches:
                    break
                continue

            empty_streak = 0
            for event in events:
                row = parse_event(event)
                if row:
                    row["season"] = season_name
                    all_matches.append(row)

            if events:
                time.sleep(0.5)
            else:
                time.sleep(0.1)

        except Exception:
            continue

    return all_matches


def scrape_season_smart(season_name, start_date, end_date):
    all_matches = []
    seen_ids = set()

    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    today = datetime.now()
    if end > today:
        end = today

    target_days = set()
    current = start
    while current <= end:
        dow = current.weekday()
        if dow in (0, 1, 2, 3):
            target_days.add(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    all_dates = sorted(target_days)

    for date_str in all_dates:
        url = f"{ESPN_BASE}?dates={date_str}"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            events = data.get("events", [])

            for event in events:
                eid = event.get("id", "")
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                row = parse_event(event)
                if row:
                    row["season"] = season_name
                    all_matches.append(row)

            time.sleep(0.2)
        except Exception:
            continue

    return all_matches


def scrape_europa_league(seasons_back=5, thorough=False):
    all_matches = []
    sorted_seasons = sorted(SEASON_RANGES.keys(), reverse=True)[:seasons_back]

    print("=" * 60)
    print("DESCARGA UEFA EUROPA LEAGUE (ESPN API)")
    print(f"Temporadas: {len(sorted_seasons)} | Modo: {'exhaustivo' if thorough else 'rápido'}")
    print("=" * 60)

    for season in sorted_seasons:
        start_date, end_date = SEASON_RANGES[season]
        print(f"\n  {season} ({start_date[:4]}.{start_date[4:6]} → {end_date[:4]}.{end_date[4:6]})...")

        if thorough:
            matches = scrape_season(season, start_date, end_date)
        else:
            matches = scrape_season_smart(season, start_date, end_date)

        all_matches.extend(matches)
        print(f"  [OK] {len(matches)} partidos")

    if not all_matches:
        print("\n[ERROR] No se pudieron descargar datos de Europa League")
        return pd.DataFrame()

    df = pd.DataFrame(all_matches)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    df = df.drop_duplicates(subset=["match_id_espn"], keep="first")

    if "home_goals" in df.columns:
        df["total_goals"] = df["home_goals"] + df["away_goals"]
        df["goal_difference"] = df["home_goals"] - df["away_goals"]

    if "ht_home_goals" in df.columns:
        df["ht_total_goals"] = df["ht_home_goals"] + df["ht_away_goals"]
        df["ht_result"] = "D"
        df.loc[df["ht_home_goals"] > df["ht_away_goals"], "ht_result"] = "H"
        df.loc[df["ht_home_goals"] < df["ht_away_goals"], "ht_result"] = "A"
        df["ht_result_changed"] = (df["ht_result"] != df["result"]).astype(int)

    if "home_fouls" in df.columns:
        df["total_fouls"] = df["home_fouls"].fillna(0) + df["away_fouls"].fillna(0)

    df["total_cards"] = (
        df["home_yellow_cards"].fillna(0) + df["away_yellow_cards"].fillna(0)
        + df["home_red_cards"].fillna(0) + df["away_red_cards"].fillna(0)
    )

    if "home_corners" in df.columns:
        df["total_corners"] = df["home_corners"].fillna(0) + df["away_corners"].fillna(0)

    print(f"\n  Total: {len(df)} partidos únicos de Europa League")
    print(f"  Temporadas: {df['season'].nunique()}")
    if "date" in df.columns and not df["date"].isna().all():
        print(f"  Rango: {df['date'].min().date()} → {df['date'].max().date()}")
    print(f"  Estadios: {df['stadium'].nunique()}")
    print(f"  Equipos: {len(set(df['home_team'].unique()) | set(df['away_team'].unique()))}")

    return df


def save_data(df, filename="europa_league_matches.csv"):
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RAW_DATA_DIR / filename
    df.to_csv(filepath, index=False)
    print(f"[SAVED] {filepath} ({len(df)} filas, {len(df.columns)} columnas)")
    return filepath


def run(seasons_back=5):
    df = scrape_europa_league(seasons_back=seasons_back, thorough=False)

    if df.empty:
        print("[WARN] Modo rápido sin resultados, intentando modo exhaustivo para 2 temporadas...")
        df = scrape_europa_league(seasons_back=min(seasons_back, 2), thorough=True)

    if df.empty:
        print("[ERROR] No se pudieron obtener datos de Europa League")
        return None, None

    path = save_data(df)
    return df, path


if __name__ == "__main__":
    df, path = run(seasons_back=5)
    if df is not None:
        print(f"\nDescarga completada: {len(df)} partidos de Europa League")
