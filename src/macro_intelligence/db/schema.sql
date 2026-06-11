-- Runic Agent v2.2 SQLite schema

CREATE TABLE IF NOT EXISTS variables (
    var_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_ticker TEXT,
    paradigm TEXT,
    speed TEXT,
    combo_slots TEXT,
    pctile_window TEXT,
    pctile_start TEXT
);

CREATE TABLE IF NOT EXISTS thresholds (
    threshold_id INTEGER PRIMARY KEY AUTOINCREMENT,
    var_id TEXT NOT NULL REFERENCES variables(var_id),
    tier TEXT NOT NULL,
    direction TEXT NOT NULL,
    value REAL,
    value_type TEXT,
    UNIQUE(var_id, tier, direction)
);

CREATE TABLE IF NOT EXISTS daily_readings (
    date TEXT NOT NULL,
    var_id TEXT NOT NULL REFERENCES variables(var_id),
    raw_value REAL,
    pctile_rank_3yr REAL,
    unconditional_pctile REAL,
    regime_pctile REAL,
    signal_tier TEXT,
    direction TEXT,
    meta_json TEXT,
    PRIMARY KEY (date, var_id)
);

CREATE TABLE IF NOT EXISTS pending_releases (
    release_id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_type TEXT NOT NULL,
    release_date TEXT NOT NULL,
    actual REAL,
    consensus REAL,
    surprise_pp REAL,
    source TEXT,
    applied INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(release_type, release_date)
);

CREATE TABLE IF NOT EXISTS combo_c_cancel (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    wti_potential_week INTEGER DEFAULT 0,
    last_check_date TEXT,
    cpi_leg_passed INTEGER DEFAULT 1,
    active INTEGER DEFAULT 0,
    cancel_date TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cftc_positioning (
    date TEXT PRIMARY KEY,
    fm_net REAL,
    rm_net REAL,
    fm_pctile REAL,
    rm_pctile REAL,
    status TEXT DEFAULT 'CONFIRMED',
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS data_pull_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    pulled_at TEXT NOT NULL,
    status TEXT NOT NULL,
    last_good_value TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS signal_fires (
    fire_id INTEGER PRIMARY KEY AUTOINCREMENT,
    var_id TEXT NOT NULL REFERENCES variables(var_id),
    date TEXT NOT NULL,
    tier TEXT NOT NULL,
    direction TEXT,
    weeks_in_tier INTEGER DEFAULT 1,
    UNIQUE(var_id, date, tier)
);

CREATE TABLE IF NOT EXISTS combo_fires (
    combo_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    var1_id TEXT,
    var2_id TEXT,
    var3_id TEXT,
    var1_direction TEXT,
    var2_direction TEXT,
    var3_direction TEXT,
    runic_combo TEXT,
    status TEXT DEFAULT 'ACTIVE',
    duration_weeks INTEGER,
    duration_bucket TEXT,
    gate_flag TEXT DEFAULT 'SIGNAL',
    macro_regime TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS forward_returns (
    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
    combo_id INTEGER NOT NULL REFERENCES combo_fires(combo_id),
    spx_1w REAL,
    spx_2w REAL,
    spx_1m REAL,
    spx_3m REAL,
    spx_6m REAL,
    spx_9m REAL,
    spx_12m REAL,
    UNIQUE(combo_id)
);

CREATE TABLE IF NOT EXISTS rule_library (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    signal_condition TEXT,
    n_obs INTEGER,
    hit_rate REAL,
    avg_return_3m REAL,
    regime_hit_rates TEXT
);

CREATE TABLE IF NOT EXISTS persistence_fires (
    persistence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_name TEXT NOT NULL,
    var_id TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT,
    weeks_count INTEGER,
    trigger_value REAL,
    active INTEGER DEFAULT 1,
    meta_json TEXT
);

CREATE TABLE IF NOT EXISTS macro_regime_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    combo_id INTEGER REFERENCES combo_fires(combo_id),
    regime_json TEXT NOT NULL,
    model TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS threshold_review_log (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_date TEXT NOT NULL,
    combo_key TEXT,
    suggestion_json TEXT,
    status TEXT DEFAULT 'PENDING',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_daily_readings_var ON daily_readings(var_id, date);
CREATE INDEX IF NOT EXISTS idx_combo_fires_date ON combo_fires(date);
CREATE INDEX IF NOT EXISTS idx_combo_fires_runic ON combo_fires(runic_combo);
CREATE INDEX IF NOT EXISTS idx_forward_returns_combo ON forward_returns(combo_id);
