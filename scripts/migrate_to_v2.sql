-- Migration script for Solo SaaS Finder v2.0
-- Migrates from old thesis scoring (6 factors) to new SaaS-focused scoring (6 new factors)

-- =====================================================
-- PROCESSED SIGNALS TABLE MIGRATION
-- =====================================================

-- Drop old thesis score columns if they exist
ALTER TABLE processed_signals
  DROP COLUMN IF EXISTS score_ai_leverage,
  DROP COLUMN IF EXISTS score_trust_scarcity,
  DROP COLUMN IF EXISTS score_physical_digital,
  DROP COLUMN IF EXISTS score_incumbent_decay,
  DROP COLUMN IF EXISTS score_speed_advantage,
  DROP COLUMN IF EXISTS score_execution_fit;

-- Add new thesis score columns for Solo SaaS Finder v2.0
ALTER TABLE processed_signals
  ADD COLUMN IF NOT EXISTS score_demand_evidence INTEGER,
  ADD COLUMN IF NOT EXISTS score_competition_gap INTEGER,
  ADD COLUMN IF NOT EXISTS score_trend_timing INTEGER,
  ADD COLUMN IF NOT EXISTS score_solo_buildability INTEGER,
  ADD COLUMN IF NOT EXISTS score_clear_monetisation INTEGER,
  ADD COLUMN IF NOT EXISTS score_regulatory_simplicity INTEGER;

-- Add disqualification tracking
ALTER TABLE processed_signals
  ADD COLUMN IF NOT EXISTS is_disqualified BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS disqualification_reason TEXT;

-- Add new SaaS-focused fields
ALTER TABLE processed_signals
  ADD COLUMN IF NOT EXISTS problem_summary TEXT,
  ADD COLUMN IF NOT EXISTS demand_evidence_level VARCHAR(20);

-- Create index for filtering disqualified signals
CREATE INDEX IF NOT EXISTS idx_processed_signals_disqualified
  ON processed_signals(is_disqualified);

-- Create index for demand evidence filtering
CREATE INDEX IF NOT EXISTS idx_processed_signals_demand_evidence
  ON processed_signals(score_demand_evidence);

-- =====================================================
-- OPPORTUNITIES TABLE MIGRATION
-- =====================================================

-- Add new SaaS-focused columns to opportunities
ALTER TABLE opportunities
  ADD COLUMN IF NOT EXISTS business_name TEXT,
  ADD COLUMN IF NOT EXISTS one_liner TEXT,
  ADD COLUMN IF NOT EXISTS problem_description TEXT,
  ADD COLUMN IF NOT EXISTS target_customer TEXT,
  ADD COLUMN IF NOT EXISTS current_solutions TEXT,
  ADD COLUMN IF NOT EXISTS proposed_solution TEXT,
  ADD COLUMN IF NOT EXISTS core_features JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS demand_evidence TEXT,
  ADD COLUMN IF NOT EXISTS demand_strength VARCHAR(20),
  ADD COLUMN IF NOT EXISTS competitors JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS competition_weakness TEXT,
  ADD COLUMN IF NOT EXISTS tech_stack_recommendation TEXT,
  ADD COLUMN IF NOT EXISTS build_time_estimate TEXT,
  ADD COLUMN IF NOT EXISTS technical_challenges JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS can_ship_in_4_weeks BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS pricing_model TEXT,
  ADD COLUMN IF NOT EXISTS suggested_price_points TEXT,
  ADD COLUMN IF NOT EXISTS who_pays TEXT,
  ADD COLUMN IF NOT EXISTS customer_channels JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS first_customers_strategy TEXT,
  ADD COLUMN IF NOT EXISTS seo_potential TEXT,
  ADD COLUMN IF NOT EXISTS overall_score INTEGER,
  ADD COLUMN IF NOT EXISTS verdict VARCHAR(20),
  ADD COLUMN IF NOT EXISTS first_steps JSONB DEFAULT '[]'::jsonb;

-- Create index for verdict filtering
CREATE INDEX IF NOT EXISTS idx_opportunities_verdict
  ON opportunities(verdict);

-- Create index for opportunity type filtering
CREATE INDEX IF NOT EXISTS idx_opportunities_type
  ON opportunities(opportunity_type);

-- =====================================================
-- FUNCTION UPDATES
-- =====================================================

-- Update the match_signals function if needed (for vector similarity search)
-- This function should already exist from initial setup

-- =====================================================
-- DATA CLEANUP (Optional - Run manually if needed)
-- =====================================================

-- To clear old processed signals and start fresh with new scoring:
-- TRUNCATE processed_signals CASCADE;

-- To clear old patterns:
-- TRUNCATE pattern_matches CASCADE;

-- To clear old opportunities:
-- TRUNCATE opportunities CASCADE;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify new columns exist on processed_signals:
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'processed_signals'
-- AND column_name LIKE 'score_%';

-- Verify new columns exist on opportunities:
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'opportunities'
-- AND column_name IN ('business_name', 'one_liner', 'verdict', 'first_steps');

-- Check index creation:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'processed_signals';
-- SELECT indexname FROM pg_indexes WHERE tablename = 'opportunities';
