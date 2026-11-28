-- ============================================================================
-- Migration: 20261127_harden_forecast_snapshot_indexes.sql
-- Phase 1 — Database & Data Integrity (DSS-PIK ECMWF Multi-Vintage & ENSMEAN)
--
-- Purpose:
--   Non-destructively hardens `cews_forecast_snapshot` for multi-file dasarian
--   release grouping, batch auditability, longer filenames, and fast
--   cutoff-aware vintage queries.
--
-- Guarantees:
--   - 100% additive and idempotent (MariaDB ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS)
--   - Preserves `uq_forecast_evidence`, `fk_fc_snapshot_station`, `chk_fc_prob_val`
--   - Never modifies or deletes any existing probability records (including legacy rows)
-- ============================================================================

ALTER TABLE cews_forecast_snapshot
    MODIFY COLUMN source_file VARCHAR(255) NOT NULL,
    ADD COLUMN IF NOT EXISTS release_group_id VARCHAR(64) NULL AFTER source_file,
    ADD COLUMN IF NOT EXISTS ingestion_batch_id VARCHAR(64) NULL AFTER release_group_id;

CREATE INDEX IF NOT EXISTS idx_fc_res_target_issue
    ON cews_forecast_snapshot (
        forecast_resolution,
        target_year,
        target_month,
        target_dasarian,
        issue_date
    );
