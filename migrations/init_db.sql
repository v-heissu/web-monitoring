-- File: migrations/init_db.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects table
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    brand VARCHAR(255) NOT NULL,
    industry VARCHAR(255),
    market VARCHAR(10) DEFAULT 'IT',
    status VARCHAR(50) DEFAULT 'active',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Keywords table
CREATE TABLE keywords (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    is_ai_suggested BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, keyword)
);

-- Competitors table
CREATE TABLE competitors (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    is_ai_suggested BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, name)
);

-- Articles table (core)
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    source VARCHAR(255),
    published_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),

    -- Content
    snippet TEXT,
    content TEXT,
    summary TEXT,

    -- AI Analysis
    sentiment VARCHAR(50),
    sentiment_score FLOAT,
    topics JSONB,
    entities JSONB,

    -- Metadata
    query_source VARCHAR(255),
    relevance_score FLOAT DEFAULT 0,

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('italian', COALESCE(title, '')), 'A') ||
        setweight(to_tsvector('italian', COALESCE(snippet, '')), 'B')
    ) STORED
);

-- Indexes for articles
CREATE INDEX idx_articles_project_date ON articles(project_id, published_at DESC);
CREATE INDEX idx_articles_sentiment ON articles(project_id, sentiment);
CREATE INDEX idx_articles_fts ON articles USING GIN(search_vector);
CREATE INDEX idx_articles_scraped ON articles(scraped_at DESC);

-- Alerts table
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type VARCHAR(100) NOT NULL,

    -- Configuration
    threshold FLOAT NOT NULL,
    window_hours INTEGER DEFAULT 24,
    email_recipients TEXT[] NOT NULL,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMPTZ,
    trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scraping jobs tracking
CREATE TABLE scraping_jobs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Metrics
    articles_found INTEGER DEFAULT 0,
    new_articles INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0,

    -- Error tracking
    error_message TEXT,
    celery_task_id VARCHAR(255),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Schedules table
CREATE TABLE schedules (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    frequency VARCHAR(50) DEFAULT 'daily',
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(project_id)
);

-- API usage logs
CREATE TABLE api_logs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    api_name VARCHAR(100),
    endpoint VARCHAR(255),
    status_code INTEGER,
    response_time FLOAT,
    cost_usd DECIMAL(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for logs
CREATE INDEX idx_api_logs_project_date ON api_logs(project_id, created_at DESC);

-- Insert default admin user (password: changeme)
INSERT INTO users (username, password_hash, email, role) VALUES (
    'admin',
    'a4d3b5e1e8f3c2d1b4a5e6f7c8d9e0f1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7',
    'admin@example.com',
    'admin'
);
