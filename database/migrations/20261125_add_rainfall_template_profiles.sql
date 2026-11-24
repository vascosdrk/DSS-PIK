-- ==============================================================================
-- DSS-PIK Additive Migration: Rainfall Template Profiles & Station Aliases
-- Date: 2026-11-25
-- Safe / Non-destructive: Uses CREATE TABLE IF NOT EXISTS only.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS cews_rainfall_template_profiles (
    profile_id              VARCHAR(64)     NOT NULL,
    profile_name            VARCHAR(150)    NOT NULL,
    regency_code            VARCHAR(32)     NOT NULL,
    template_kind           VARCHAR(50)     NOT NULL DEFAULT 'CUSTOM_MAPPED',
    structure_fingerprint   VARCHAR(64)     NOT NULL,
    sheet_rules_json        LONGTEXT        NULL,
    header_config_json      LONGTEXT        NULL,
    date_config_json        LONGTEXT        NULL,
    value_config_json       LONGTEXT        NULL,
    station_config_json     LONGTEXT        NULL,
    ignored_columns_json    LONGTEXT        NULL,
    symbol_mapping_json     LONGTEXT        NULL,
    version                 VARCHAR(20)     NOT NULL DEFAULT '1.0.0',
    created_by              VARCHAR(100)    NOT NULL DEFAULT 'OPERATOR_BMKG',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id),
    INDEX idx_regency_fp (regency_code, structure_fingerprint),
    INDEX idx_fingerprint (structure_fingerprint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cews_rainfall_station_aliases (
    id                      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    regency_code            VARCHAR(32)     NOT NULL,
    source_code             VARCHAR(64)     NULL,
    source_name_norm        VARCHAR(150)    NOT NULL,
    station_id              VARCHAR(50)     NOT NULL,
    created_by              VARCHAR(100)    NOT NULL DEFAULT 'OPERATOR_BMKG',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_regency_alias (regency_code, source_name_norm),
    INDEX idx_station_id (station_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
