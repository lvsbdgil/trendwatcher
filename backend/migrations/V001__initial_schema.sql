-- Users and session authentication
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT    NOT NULL UNIQUE,
    password_hash  TEXT    NOT NULL,
    role           TEXT    NOT NULL DEFAULT 'user',
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login_at  TEXT,
    last_seen_at   TEXT
);
