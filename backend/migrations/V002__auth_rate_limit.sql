-- Per-IP rate limiting for authentication endpoints
CREATE TABLE IF NOT EXISTS auth_rate_limit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ip          TEXT    NOT NULL,
    attempt_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_ip ON auth_rate_limit (ip, attempt_at);
