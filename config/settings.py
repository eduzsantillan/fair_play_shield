import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "fair_play_shield"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

FOOTBALL_DATA_BASE_URL = "https://www.football-data.co.uk"

EUROPA_LEAGUE_SEASONS = {
    "2024-2025": f"{FOOTBALL_DATA_BASE_URL}/new/EC.csv",
    "2023-2024": f"{FOOTBALL_DATA_BASE_URL}/new/EC.csv",
}

INTERNATIONAL_LEAGUES = {
    "EC": "UEFA Europa League / Europa Conference League",
}

MATCH_INTEGRITY_THRESHOLDS = {
    "normal": (0, 30),
    "monitor": (31, 60),
    "suspicious": (61, 80),
    "high_alert": (81, 100),
}

ODDS_MOVEMENT_SUSPICIOUS_PCT = 0.15
MIN_WIN_STREAK_FOR_UPSET_FLAG = 5
GOALS_ANOMALY_MULTIPLIER = 4
XG_DEVIATION_THRESHOLD = 2.0
