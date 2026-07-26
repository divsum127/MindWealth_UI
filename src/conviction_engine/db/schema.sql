-- Conviction Engine auxiliary tables (SQLite; PostgreSQL-compatible DDL in prod).

CREATE TABLE IF NOT EXISTS ma_activity (
    ticker VARCHAR(20) NOT NULL,
    bidder VARCHAR(100),
    bid_price DECIMAL(10, 2),
    bid_date DATE NOT NULL,
    board_response VARCHAR(20),
    note TEXT,
    last_updated TIMESTAMP,
    active BOOLEAN DEFAULT 1,
    PRIMARY KEY (ticker, bid_date)
);

CREATE INDEX IF NOT EXISTS idx_ma_activity_active ON ma_activity (active, ticker);
