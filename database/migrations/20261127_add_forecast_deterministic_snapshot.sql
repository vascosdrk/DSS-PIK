-- ============================================================================
-- Migration: 20261127_add_forecast_deterministic_snapshot.sql
-- Phase 1 — Database & Data Integrity (DSS-PIK ECMWF Multi-Vintage & ENSMEAN)
--
-- Purpose:
--   Creates the dedicated deterministic forecast table
--   `cews_forecast_deterministic_snapshot` for ECMWF ENSMEAN (mm) separated
--   from probabilistic forecasts (`cews_forecast_snapshot`, %).
--
-- Guarantees:
--   - 100% additive and idempotent (CREATE TABLE IF NOT EXISTS)
--   - Matches `stations.station_id` exactly: VARCHAR(20) utf8mb4_unicode_ci InnoDB
--   - Enforces multi-vintage uniqueness (uq_det_forecast_vintage)
--   - Enforces non-negative mm values, valid resolution, and adjustment status
--   - Supports isolated soft-void and audited reactivation after void
--   - Non-destructive: never modifies existing tables or historical data
-- ============================================================================

CREATE TABLE IF NOT EXISTS cews_forecast_deterministic_snapshot (
    id                  BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
    station_id          VARCHAR(20)       NOT NULL,
    forecast_resolution VARCHAR(20)       NOT NULL,
    issue_date          DATE              NOT NULL,
    target_year         SMALLINT UNSIGNED NOT NULL,
    target_month        TINYINT UNSIGNED  NOT NULL,
    target_dasarian     TINYINT UNSIGNED  NOT NULL DEFAULT 0,
    forecast_variable   VARCHAR(30)       NOT NULL DEFAULT 'ENSMEAN',
    value_mm            DECIMAL(8,2)      NOT NULL,
    unit                VARCHAR(10)       NOT NULL DEFAULT 'mm',
    adjustment_status   VARCHAR(20)       NOT NULL DEFAULT 'REGULAR',
    source_file         VARCHAR(255)      NOT NULL,
    source_sheet        VARCHAR(64)       NOT NULL DEFAULT 'EnsMean',
    source_column       VARCHAR(100)      NOT NULL,
    release_group_id    VARCHAR(64)       NULL,
    ingestion_batch_id  VARCHAR(64)       NULL,
    is_voided           TINYINT(1)        NOT NULL DEFAULT 0,
    void_reason         VARCHAR(255)      NULL,
    voided_by           VARCHAR(100)      NULL,
    voided_at           DATETIME          NULL,
    reactivation_count  SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    reactivated_at      DATETIME          NULL,
    created_at          DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_det_forecast_vintage (
        station_id,
        forecast_resolution,
        issue_date,
        target_year,
        target_month,
        target_dasarian,
        forecast_variable
    ),
    INDEX idx_det_res_target_issue (
        forecast_resolution,
        target_year,
        target_month,
        target_dasarian,
        issue_date
    ),
    INDEX idx_det_vintage_batch (
        issue_date,
        release_group_id,
        ingestion_batch_id
    ),
    INDEX idx_det_station_target (
        station_id,
        forecast_resolution,
        target_year,
        target_month,
        target_dasarian
    ),
    INDEX idx_det_active_lookup (
        is_voided,
        forecast_resolution,
        target_year,
        target_month,
        target_dasarian,
        issue_date
    ),
    CONSTRAINT fk_det_fc_station
        FOREIGN KEY (station_id) REFERENCES stations (station_id)
        ON UPDATE CASCADE,
    CONSTRAINT chk_det_val_nonneg
        CHECK (value_mm >= 0.00),
    CONSTRAINT chk_det_res_valid
        CHECK (forecast_resolution IN ('DASARIAN', 'BULANAN')),
    CONSTRAINT chk_det_adj_valid
        CHECK (adjustment_status IN ('REGULAR', 'ADJUSTED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
