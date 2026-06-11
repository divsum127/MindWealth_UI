CREATE TABLE IF NOT EXISTS ssi_daily (
    date TEXT PRIMARY KEY,
    ssi_level REAL NOT NULL,
    ssi_percentile_5y REAL,
    hyg_lqd REAL,
    dbmf_beta REAL,
    cnn_fg REAL,
    vix_ratio REAL,
    layer2_status TEXT,
    layer2_confirmed_count INTEGER,
    ssi_multiplier REAL,
    payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ssi_daily_date ON ssi_daily(date);
