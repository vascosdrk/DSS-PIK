-- ==============================================================================
-- DSS-PIK Additive Migration: Persistent MariaDB-Backed SPI Generation Jobs
-- Date: 2026-11-26
-- Safe / Non-destructive / Idempotent: Uses CREATE TABLE IF NOT EXISTS only.
-- Rollback: DROP TABLE IF EXISTS cews_spi_generation_jobs;
-- ==============================================================================

CREATE TABLE IF NOT EXISTS cews_spi_generation_jobs (
    job_id                VARCHAR(64)     NOT NULL,
    job_key               VARCHAR(128)    NOT NULL,
    status                VARCHAR(20)     NOT NULL DEFAULT 'QUEUED',
    resolution            VARCHAR(20)     NOT NULL,
    timescale             INT             NOT NULL,
    request_params_json   LONGTEXT        NULL,
    total_stations        INT             NOT NULL DEFAULT 0,
    completed_stations    INT             NOT NULL DEFAULT 0,
    success_count         INT             NOT NULL DEFAULT 0,
    error_count           INT             NOT NULL DEFAULT 0,
    progress_pct          DECIMAL(5,2)    NOT NULL DEFAULT 0.00,
    current_station       VARCHAR(50)     NULL,
    stage_message         VARCHAR(255)    NULL,
    session_token         VARCHAR(64)     NULL,
    staged_parquet_path   VARCHAR(512)    NULL,
    target_parquet_path   VARCHAR(512)    NULL,
    result_summary_json   LONGTEXT        NULL,
    results_detail_json   LONGTEXT        NULL,
    sample_preview_json   LONGTEXT        NULL,
    error_message         TEXT            NULL,
    operator              VARCHAR(100)    NOT NULL DEFAULT 'OPERATOR_BMKG',
    attempt_count         INT             NOT NULL DEFAULT 1,
    heartbeat_at          DATETIME        NULL,
    started_at            DATETIME        NULL,
    finished_at           DATETIME        NULL,
    created_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (job_id),
    INDEX idx_spi_job_status (status, created_at),
    INDEX idx_spi_job_key_status (job_key, status),
    INDEX idx_spi_job_token (session_token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
