-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Raw signals table (append-only event store)
CREATE TABLE IF NOT EXISTS raw_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(50) NOT NULL,
    source_category VARCHAR(50) NOT NULL,
    source_url TEXT,
    raw_content JSONB NOT NULL,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    signal_date DATE,
    geography VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_signals_collected ON raw_signals(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_signals_source ON raw_signals(source_type, source_category);
CREATE INDEX IF NOT EXISTS idx_raw_signals_geography ON raw_signals(geography);

-- Processed signals table
CREATE TABLE IF NOT EXISTS processed_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_signal_id UUID REFERENCES raw_signals(id),
    signal_type VARCHAR(50),
    signal_subtype VARCHAR(100),
    title TEXT,
    summary TEXT,
    entities JSONB,
    keywords TEXT[],
    embedding vector(1536),
    score_ai_leverage INTEGER,
    score_trust_scarcity INTEGER,
    score_physical_digital INTEGER,
    score_incumbent_decay INTEGER,
    score_speed_advantage INTEGER,
    score_execution_fit INTEGER,
    thesis_reasoning TEXT,
    novelty_score FLOAT,
    velocity_score FLOAT,
    geography VARCHAR(10),
    timing_stage VARCHAR(20),
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_signals_embedding ON processed_signals
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_processed_signals_type ON processed_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_processed_signals_timing ON processed_signals(timing_stage);

-- Pattern matches table
CREATE TABLE IF NOT EXISTS pattern_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern_type VARCHAR(50),
    signal_ids UUID[],
    signal_count INTEGER,
    title TEXT,
    description TEXT,
    hypothesis TEXT,
    confidence_score FLOAT,
    opportunity_score FLOAT,
    primary_thesis_alignment VARCHAR(50),
    thesis_scores JSONB,
    status VARCHAR(20) DEFAULT 'new',
    user_notes TEXT,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patterns_status ON pattern_matches(status);
CREATE INDEX IF NOT EXISTS idx_patterns_score ON pattern_matches(opportunity_score DESC);

-- Opportunities table
CREATE TABLE IF NOT EXISTS opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    summary TEXT,
    detailed_analysis TEXT,
    pattern_ids UUID[],
    signal_ids UUID[],
    opportunity_type VARCHAR(50),
    industries TEXT[],
    geographies TEXT[],
    thesis_scores JSONB,
    primary_thesis VARCHAR(50),
    execution_fit_reasoning TEXT,
    timing_stage VARCHAR(20),
    time_sensitivity TEXT,
    existing_players TEXT[],
    incumbent_weakness TEXT,
    estimated_complexity VARCHAR(20),
    key_requirements TEXT[],
    potential_moats TEXT[],
    risks TEXT[],
    status VARCHAR(20) DEFAULT 'new',
    user_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_timing ON opportunities(timing_stage);

-- Collection runs tracking
CREATE TABLE IF NOT EXISTS collection_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running',
    signals_collected INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Analysis runs tracking
CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_type VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'running',
    patterns_detected INTEGER DEFAULT 0,
    opportunities_generated INTEGER DEFAULT 0,
    summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    context_type VARCHAR(50),
    related_opportunity_id UUID REFERENCES opportunities(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    context_signals UUID[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Vector similarity search function
CREATE OR REPLACE FUNCTION match_signals(
    query_embedding vector(1536),
    match_threshold float,
    match_count int
)
RETURNS TABLE (
    id UUID,
    raw_signal_id UUID,
    signal_type VARCHAR(50),
    signal_subtype VARCHAR(100),
    title TEXT,
    summary TEXT,
    entities JSONB,
    keywords TEXT[],
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ps.id,
        ps.raw_signal_id,
        ps.signal_type,
        ps.signal_subtype,
        ps.title,
        ps.summary,
        ps.entities,
        ps.keywords,
        1 - (ps.embedding <=> query_embedding) AS similarity
    FROM processed_signals ps
    WHERE ps.embedding IS NOT NULL
    AND 1 - (ps.embedding <=> query_embedding) > match_threshold
    ORDER BY ps.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
