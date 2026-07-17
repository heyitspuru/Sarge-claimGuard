CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS claims (
  record_id text PRIMARY KEY, status text NOT NULL, package jsonb,
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS audit_log (
  id bigserial PRIMARY KEY, record_id text NOT NULL, step text NOT NULL,
  status text NOT NULL, detail jsonb, created_at timestamptz DEFAULT now());
CREATE TABLE IF NOT EXISTS icd_codes (
  code text PRIMARY KEY, description text NOT NULL, embedding vector(768));
CREATE TABLE IF NOT EXISTS policy_clauses (
  clause_id text PRIMARY KEY, insurer_id text NOT NULL, plan_id text NOT NULL,
  clause_type text NOT NULL, clause_text text NOT NULL, structured jsonb,
  embedding vector(768));
CREATE TABLE IF NOT EXISTS handoff_timestamps (
  id bigserial PRIMARY KEY, record_id text NOT NULL, handoff text NOT NULL,
  at timestamptz DEFAULT now());
-- ponytail: consent/erasure are no-op interfaces on synthetic data; real DPDP impl is product-stage
CREATE TABLE IF NOT EXISTS consents (
  record_id text PRIMARY KEY, granted boolean NOT NULL DEFAULT true, withdrawn_at timestamptz);
