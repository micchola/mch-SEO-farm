-- Schema pSEO MCH
-- Database: data.db

CREATE TABLE IF NOT EXISTS tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    category TEXT,
    saas_url TEXT,
    pricing_model TEXT,   -- 'free', 'freemium', 'paid', 'enterprise'
    price_from REAL,
    price_to REAL,
    target_sectors TEXT,  -- JSON array of sectors
    features TEXT,        -- JSON array of feature strings
    pros TEXT,            -- JSON array
    cons TEXT,            -- JSON array
    affiliate_url TEXT,
    affiliate_program TEXT,  -- 'amazon', 'impact', 'shareasale', 'direct'
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS oss_alternatives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    saas_tool_id INTEGER NOT NULL REFERENCES tools(id),
    repo_name TEXT NOT NULL,   -- 'owner/repo'
    repo_url TEXT,
    stars INTEGER,
    license TEXT,
    description TEXT,
    last_push TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_a_id INTEGER NOT NULL REFERENCES tools(id),
    tool_b_id INTEGER NOT NULL REFERENCES tools(id),
    slug TEXT NOT NULL UNIQUE,
    winner_context TEXT,      -- 'best for small teams', 'best value', etc.
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,       -- 'oss_alt', 'sector', 'comparison'
    tool_id INTEGER,
    sector TEXT,
    category TEXT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT,
    content_md TEXT,
    generated_at TEXT DEFAULT (datetime('now')),
    published INTEGER DEFAULT 0,
    page_views INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS etl_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);
