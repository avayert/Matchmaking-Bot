PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS aliases (
    abbreviation TEXT PRIMARY KEY,
    game TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS default_platforms (
    channel_id INTEGER PRIMARY KEY,
    platform TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS default_games (
    channel_id INTEGER PRIMARY KEY,
    game TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pinglists (
    name TEXT PRIMARY KEY,
    owner_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pinglist_subscriptions (
    subscriber INTEGER NOT NULL,
    subscription TEXT NOT NULL,
    FOREIGN KEY (subscription) REFERENCES pinglists(name) ON DELETE CASCADE
);
