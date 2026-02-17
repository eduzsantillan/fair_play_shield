CREATE TABLE IF NOT EXISTS matches (
    match_id SERIAL PRIMARY KEY,
    season VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    time TIME,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    home_goals INT,
    away_goals INT,
    ht_home_goals INT,
    ht_away_goals INT,
    result CHAR(1) CHECK (result IN ('H','A','D')),
    ht_result CHAR(1) CHECK (ht_result IN ('H','A','D')),
    referee VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS betting_odds (
    odds_id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(match_id) ON DELETE CASCADE,
    bookmaker VARCHAR(50),
    home_win_odds FLOAT,
    draw_odds FLOAT,
    away_win_odds FLOAT,
    over25_odds FLOAT,
    under25_odds FLOAT,
    home_win_close FLOAT,
    draw_close FLOAT,
    away_win_close FLOAT,
    odds_movement_home FLOAT,
    odds_movement_draw FLOAT,
    odds_movement_away FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS match_stats (
    stat_id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(match_id) ON DELETE CASCADE,
    home_shots INT,
    away_shots INT,
    home_shots_on_target INT,
    away_shots_on_target INT,
    home_corners INT,
    away_corners INT,
    home_fouls INT,
    away_fouls INT,
    home_yellow_cards INT,
    away_yellow_cards INT,
    home_red_cards INT,
    away_red_cards INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS integrity_scores (
    score_id SERIAL PRIMARY KEY,
    match_id INT REFERENCES matches(match_id) ON DELETE CASCADE,
    integrity_score FLOAT NOT NULL,
    odds_anomaly_score FLOAT DEFAULT 0,
    performance_anomaly_score FLOAT DEFAULT 0,
    historical_anomaly_score FLOAT DEFAULT 0,
    referee_anomaly_score FLOAT DEFAULT 0,
    betting_volume_anomaly_score FLOAT DEFAULT 0,
    alert_level VARCHAR(20) CHECK (alert_level IN ('normal','monitor','suspicious','high_alert')),
    alert_reasons JSONB,
    reviewed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS team_form (
    form_id SERIAL PRIMARY KEY,
    team VARCHAR(100) NOT NULL,
    season VARCHAR(20) NOT NULL,
    matches_played INT DEFAULT 0,
    wins INT DEFAULT 0,
    draws INT DEFAULT 0,
    losses INT DEFAULT 0,
    goals_scored INT DEFAULT 0,
    goals_conceded INT DEFAULT 0,
    current_win_streak INT DEFAULT 0,
    current_loss_streak INT DEFAULT 0,
    current_unbeaten_streak INT DEFAULT 0,
    last5_results VARCHAR(10),
    avg_goals_scored FLOAT DEFAULT 0,
    avg_goals_conceded FLOAT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(date);
CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team, away_team);
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season);
CREATE INDEX IF NOT EXISTS idx_integrity_alert ON integrity_scores(alert_level);
CREATE INDEX IF NOT EXISTS idx_integrity_score ON integrity_scores(integrity_score DESC);
