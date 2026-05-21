-- ============================================================
-- EA AI Intelligence — Supabase Schema
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- 1. Application Portfolio
CREATE TABLE IF NOT EXISTS applications (
  id            UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  name          TEXT        NOT NULL,
  vendor        TEXT,
  category      TEXT,
  description   TEXT,
  business_unit TEXT,
  deployment    TEXT,                        -- Cloud | On-Prem | Hybrid
  annual_cost   NUMERIC(14,2),
  user_count    INTEGER,
  criticality   TEXT        DEFAULT 'Medium', -- Critical | High | Medium | Low
  business_value        NUMERIC(4,2),
  adoption_rate         NUMERIC(4,2),
  integration_depth     NUMERIC(4,2),
  vendor_support        NUMERIC(4,2),
  cost_efficiency       NUMERIC(4,2),
  technical_health      NUMERIC(4,2),
  risk_score            NUMERIC(4,2),
  composite_score       NUMERIC(4,2),
  time_classification   TEXT,               -- TOLERATE | INVEST | MIGRATE | ELIMINATE
  rationalization_action TEXT,              -- 6R value
  confidence_level      TEXT,
  integrations          JSONB,
  age_years             NUMERIC(5,2),
  end_of_life           BOOLEAN DEFAULT FALSE,
  compliance_required   BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Architecture Decisions (agent memory — all agents write here)
CREATE TABLE IF NOT EXISTS architecture_decisions (
  id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  agent       TEXT        NOT NULL,          -- ARB | TIME | MAPPING | MATURITY | INSIGHTS
  input_data  JSONB,
  output_data JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_decisions_agent      ON architecture_decisions (agent);
CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON architecture_decisions (created_at DESC);

-- 3. Application Dependencies
CREATE TABLE IF NOT EXISTS dependencies (
  id                  UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  source_app_id       TEXT  NOT NULL,        -- app name or UUID
  target_app_id       TEXT  NOT NULL,
  dependency_type     TEXT,                  -- API | DB | Event | File | UI | Other
  integration_pattern TEXT,                  -- REST | SOAP | Kafka | etc.
  direction           TEXT  DEFAULT 'OUTBOUND', -- OUTBOUND | INBOUND | BIDIRECTIONAL
  criticality         TEXT  DEFAULT 'Medium',
  description         TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dep_source ON dependencies (source_app_id);

-- 4. Enterprise Architecture Standards & Governance Rules
CREATE TABLE IF NOT EXISTS standards_rules (
  id               UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  rule_name        TEXT  NOT NULL,
  category         TEXT,                     -- Technology | Security | Data | Integration | Cloud
  description      TEXT,
  enforcement_level TEXT DEFAULT 'RECOMMENDED', -- MANDATORY | RECOMMENDED | ADVISORY
  rationale        TEXT,
  examples         TEXT[],
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Seed a few starter rules
INSERT INTO standards_rules (rule_name, category, description, enforcement_level) VALUES
  ('API-First Design', 'Integration', 'All new integrations must expose REST or GraphQL APIs; no point-to-point database links.', 'MANDATORY'),
  ('Cloud-Native by Default', 'Technology', 'New workloads must be deployed on approved cloud platforms unless a technical exception is granted.', 'MANDATORY'),
  ('Single Source of Truth', 'Data', 'Each data domain must have one authoritative system of record; data duplication requires governance approval.', 'RECOMMENDED'),
  ('Zero-Trust Security', 'Security', 'All service-to-service communication must be authenticated; no implicit trust on the internal network.', 'MANDATORY'),
  ('Vendor Lock-in Mitigation', 'Technology', 'Prefer open standards and portable architectures; proprietary lock-in must be justified with a risk waiver.', 'ADVISORY')
ON CONFLICT DO NOTHING;

-- 5. EA Maturity Assessment History
CREATE TABLE IF NOT EXISTS maturity_scores (
  id                UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  assessment_date   DATE  DEFAULT CURRENT_DATE,
  overall_score     NUMERIC(3,2),            -- 1.0 – 5.0
  maturity_level    TEXT,                    -- Initial | Developing | Defined | Managed | Optimising
  strategy_score    NUMERIC(3,2),
  governance_score  NUMERIC(3,2),
  technology_score  NUMERIC(3,2),
  information_score NUMERIC(3,2),
  security_score    NUMERIC(3,2),
  portfolio_size    INTEGER,
  eliminate_pct     NUMERIC(5,2),
  notes             TEXT,
  raw_assessment    JSONB,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Known Integration Patterns (reference data for Mapping agent)
CREATE TABLE IF NOT EXISTS integration_patterns (
  id           UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  pattern_name TEXT  NOT NULL,
  pattern_type TEXT,                         -- Synchronous | Asynchronous | Batch | Event-Driven
  description  TEXT,
  pros         TEXT[],
  cons         TEXT[],
  use_cases    JSONB,
  example_apps TEXT[],
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO integration_patterns (pattern_name, pattern_type, description, use_cases) VALUES
  ('REST API', 'Synchronous', 'HTTP-based request/response integration using RESTful conventions.', '["CRUD operations","mobile backends","third-party SaaS connectors"]'),
  ('Event Streaming (Kafka)', 'Asynchronous', 'High-throughput, ordered event streaming with durable replay capability.', '["real-time analytics","audit trails","microservice decoupling"]'),
  ('ETL / Batch File', 'Batch', 'Scheduled file-based data exchange (CSV, JSON, XML) via SFTP or cloud storage.', '["overnight data syncs","legacy system integration","bulk data migration"]'),
  ('Webhook', 'Asynchronous', 'Push-based HTTP callbacks triggered by events in source system.', '["payment notifications","CI/CD triggers","CRM updates"]'),
  ('GraphQL', 'Synchronous', 'Flexible query language allowing clients to request exactly the fields needed.', '["complex frontend queries","multi-source data aggregation","developer portals"]')
ON CONFLICT DO NOTHING;

-- 7. Questionnaire Responses (per-application scoring evidence)
CREATE TABLE IF NOT EXISTS questionnaire_responses (
  id             UUID  DEFAULT gen_random_uuid() PRIMARY KEY,
  application_id TEXT  NOT NULL,             -- app name or UUID
  dimension      TEXT,                       -- business_value | technical_health | etc.
  question       TEXT,
  answer         TEXT,
  score          NUMERIC(3,2),               -- 0 – 10
  answered_by    TEXT,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_qr_app ON questionnaire_responses (application_id);

-- ============================================================
-- Enable Row Level Security (RLS) — recommended for production
-- Uncomment and configure policies once your auth is set up
-- ============================================================
-- ALTER TABLE applications          ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE architecture_decisions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE dependencies           ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE standards_rules        ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE maturity_scores        ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE integration_patterns   ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE questionnaire_responses ENABLE ROW LEVEL SECURITY;
