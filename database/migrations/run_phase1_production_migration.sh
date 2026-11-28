#!/usr/bin/env bash
# ==============================================================================
# DSS-PIK — Phase 1 Production Migration Runner (2-Mode, Fail-Fast, SHA-256)
#
# Target: Coolify MariaDB 11.4 container (database: cews_db)
#
# MODE 1 — BACKUP ONLY (no schema changes):
#   bash /tmp/run_phase1_production_migration.sh --backup-only
#
# MODE 2 — MIGRATION ONLY (after user downloads backup via Coolify > Files
#          and confirms local SHA-256 matches container SHA-256):
#   bash /tmp/run_phase1_production_migration.sh --migrate-only \
#     --backup-file /tmp/cews_db_pre_phase1_<TS>.sql.gz \
#     --expected-sha256 <SHA256_CONFIRMED>
#
# Guarantees:
#   - Never modifies `compose.coolify.yaml` or `dss_pik_mariadb_data` volume
#   - Never runs DROP/TRUNCATE on operational tables or alters historical rows
#   - Exits immediately on any error (`set -euo pipefail`)
# ==============================================================================
set -euo pipefail

DB_NAME="${CEWS_DB_NAME:-cews_db}"
DB_USER="root"
DB_PASS="${MARIADB_ROOT_PASSWORD:?MARIADB_ROOT_PASSWORD is not set in container environment}"
TEMP_DB="cews_db_restore_verify"

MODE=""
BACKUP_FILE=""
EXPECTED_SHA256=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-only)
      MODE="BACKUP_ONLY"
      shift
      ;;
    --migrate-only)
      MODE="MIGRATE_ONLY"
      shift
      ;;
    --backup-file)
      BACKUP_FILE="${2:-}"
      shift 2
      ;;
    --expected-sha256)
      EXPECTED_SHA256="${2:-}"
      shift 2
      ;;
    *)
      echo "ERROR: Argumen tidak dikenal: $1"
      echo "Gunakan: --backup-only  ATAU  --migrate-only --backup-file <path> --expected-sha256 <sha256>"
      exit 1
      ;;
  esac
done

if [[ -z "${MODE}" ]]; then
  echo "ERROR: Mode wajib dipilih (--backup-only atau --migrate-only)."
  exit 1
fi

mysql_exec() {
  mariadb -u"${DB_USER}" -p"${DB_PASS}" --default-character-set=utf8mb4 "$@"
}

capture_baseline() {
  STN_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM stations;")"
  CH_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_rainfall_daily;")"
  PROB_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_forecast_snapshot;")"
  PROB_SUM="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COALESCE(ROUND(SUM(probability_value), 2), 0) FROM cews_forecast_snapshot;")"
  STN_COL_TYPE="$(mysql_exec -N -B -D information_schema -e "SELECT CONCAT(COLUMN_TYPE, ' ', COLLATION_NAME) FROM COLUMNS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='stations' AND COLUMN_NAME='station_id';")"
  if [[ "${STN_CNT}" -lt 57 ]]; then
    echo "FAIL: Jumlah master stations (${STN_CNT}) kurang dari 57."
    exit 1
  fi
}

apply_phase1_migrations() {
  local run_label="$1"
  echo "--- Menjalankan Migrasi Fase 1 (${run_label}) ---"
  mysql_exec -D "${DB_NAME}" <<'SQL'
-- Migration 1: 20261127_add_forecast_deterministic_snapshot.sql
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

-- Migration 2: 20261127_harden_forecast_snapshot_indexes.sql
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
SQL
}

# ==============================================================================
# MODE 1 — BACKUP ONLY
# ==============================================================================
if [[ "${MODE}" == "BACKUP_ONLY" ]]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  OUT_FILE="/tmp/cews_db_pre_phase1_${TS}.sql.gz"

  echo "========================================================================"
  echo "[MODE 1: BACKUP ONLY] PREFLIGHT & BASELINE (${DB_NAME})"
  echo "========================================================================"
  mysql_exec -e "SELECT VERSION() AS mariadb_version, NOW() AS server_time;"
  capture_baseline
  echo "Baseline Live ${DB_NAME}:"
  echo "  stations               : ${STN_CNT} (station_id = ${STN_COL_TYPE})"
  echo "  cews_rainfall_daily    : ${CH_CNT}"
  echo "  cews_forecast_snapshot : ${PROB_CNT} rows | SUM(probability_value) = ${PROB_SUM}"

  echo ""
  echo "[MODE 1] Membuat full compressed UTF-8 dump -> ${OUT_FILE}"
  mariadb-dump -u"${DB_USER}" -p"${DB_PASS}" \
    --single-transaction --routines --triggers --events \
    --default-character-set=utf8mb4 \
    "${DB_NAME}" | gzip -9 > "${OUT_FILE}"

  echo "[MODE 1] Validasi gzip, ukuran file, dan footer 'Dump completed'..."
  if [[ ! -s "${OUT_FILE}" ]]; then
    echo "FAIL: File backup kosong."
    exit 1
  fi
  gzip -t "${OUT_FILE}"
  if ! zcat "${OUT_FILE}" | tail -n 5 | grep -q "Dump completed"; then
    echo "FAIL: Footer 'Dump completed' tidak ditemukan pada ${OUT_FILE}."
    exit 1
  fi
  BACKUP_BYTES="$(wc -c < "${OUT_FILE}")"

  echo "[MODE 1] Uji restore ke database sementara (${TEMP_DB})..."
  trap 'mysql_exec -e "DROP DATABASE IF EXISTS \`${TEMP_DB}\`;" >/dev/null 2>&1 || true' EXIT
  mysql_exec -e "DROP DATABASE IF EXISTS \`${TEMP_DB}\`; CREATE DATABASE \`${TEMP_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  zcat "${OUT_FILE}" | mysql_exec -D "${TEMP_DB}"

  TMP_STN="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COUNT(*) FROM stations;")"
  TMP_CH="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COUNT(*) FROM cews_rainfall_daily;")"
  TMP_PROB_CNT="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COUNT(*) FROM cews_forecast_snapshot;")"
  TMP_PROB_SUM="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COALESCE(ROUND(SUM(probability_value), 2), 0) FROM cews_forecast_snapshot;")"

  echo "Hasil Restore ${TEMP_DB}:"
  echo "  stations               : ${TMP_STN} (expected ${STN_CNT})"
  echo "  cews_rainfall_daily    : ${TMP_CH} (expected ${CH_CNT})"
  echo "  cews_forecast_snapshot : ${TMP_PROB_CNT} (expected ${PROB_CNT}) | SUM = ${TMP_PROB_SUM} (expected ${PROB_SUM})"

  if [[ "${TMP_STN}" != "${STN_CNT}" || "${TMP_CH}" != "${CH_CNT}" || "${TMP_PROB_CNT}" != "${PROB_CNT}" || "${TMP_PROB_SUM}" != "${PROB_SUM}" ]]; then
    echo "FAIL: Ketidakcocokan hasil restore dengan baseline live!"
    exit 1
  fi
  mysql_exec -e "DROP DATABASE IF EXISTS \`${TEMP_DB}\`;"

  ACTUAL_SHA256="$(sha256sum "${OUT_FILE}" | awk '{print $1}')"

  echo ""
  echo "========================================================================"
  echo "STATUS MODE 1 (BACKUP ONLY): PASS — TIDAK ADA MIGRASI YANG DIJALANKAN"
  echo "========================================================================"
  echo "BACKUP_FILE   : ${OUT_FILE}"
  echo "BACKUP_BYTES  : ${BACKUP_BYTES} bytes"
  echo "SHA256        : ${ACTUAL_SHA256}"
  echo ""
  echo "LANGKAH SELANJUTNYA:"
  echo "1. Unduh ${OUT_FILE} ke laptop melalui Coolify > Files."
  echo "2. Verifikasi SHA-256 file lokal (PowerShell: Get-FileHash <file> -Algorithm SHA256)."
  echo "3. Setelah SHA-256 lokal IDENTIK, jalankan MODE 2 berikut:"
  echo ""
  echo "bash /tmp/run_phase1_production_migration.sh --migrate-only --backup-file ${OUT_FILE} --expected-sha256 ${ACTUAL_SHA256}"
  echo "========================================================================"
  exit 0
fi

# ==============================================================================
# MODE 2 — MIGRATION ONLY
# ==============================================================================
if [[ "${MODE}" == "MIGRATE_ONLY" ]]; then
  if [[ -z "${BACKUP_FILE}" || -z "${EXPECTED_SHA256}" ]]; then
    echo "FAIL: MODE 2 wajib menyertakan --backup-file <path> dan --expected-sha256 <sha256>."
    exit 1
  fi

  echo "========================================================================"
  echo "[MODE 2: MIGRATION ONLY] VERIFIKASI BACKUP & SHA-256"
  echo "========================================================================"
  if [[ ! -s "${BACKUP_FILE}" ]]; then
    echo "FAIL: File backup tidak ditemukan atau kosong: ${BACKUP_FILE}"
    exit 1
  fi

  ACTUAL_SHA256="$(sha256sum "${BACKUP_FILE}" | awk '{print $1}')"
  EXPECTED_NORM="$(echo "${EXPECTED_SHA256}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  if [[ "${ACTUAL_SHA256}" != "${EXPECTED_NORM}" ]]; then
    echo "FAIL: SHA-256 TIDAK COCOK!"
    echo "  Expected: ${EXPECTED_NORM}"
    echo "  Actual  : ${ACTUAL_SHA256}"
    exit 1
  fi

  gzip -t "${BACKUP_FILE}"
  if ! zcat "${BACKUP_FILE}" | tail -n 5 | grep -q "Dump completed"; then
    echo "FAIL: Footer 'Dump completed' tidak valid pada ${BACKUP_FILE}."
    exit 1
  fi
  echo "OK: Backup utuh & SHA-256 terverifikasi (${ACTUAL_SHA256})."

  echo ""
  echo "[MODE 2] Mencatat baseline live sebelum migrasi..."
  capture_baseline
  echo "  stations=${STN_CNT} | cews_rainfall_daily=${CH_CNT} | cews_forecast_snapshot=${PROB_CNT} (SUM=${PROB_SUM})"

  echo ""
  apply_phase1_migrations "RUN 1"
  apply_phase1_migrations "RUN 2 - IDEMPOTENCY"

  echo ""
  echo "[MODE 2] Verifikasi pasca-migrasi (skema, FK, UK, index, CHECK, data historis)..."
  POST_STN="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM stations;")"
  POST_CH="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_rainfall_daily;")"
  POST_PROB_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_forecast_snapshot;")"
  POST_PROB_SUM="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COALESCE(ROUND(SUM(probability_value), 2), 0) FROM cews_forecast_snapshot;")"
  DET_EXISTS="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM TABLES WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot';")"
  DET_FK="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM TABLE_CONSTRAINTS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot' AND CONSTRAINT_NAME='fk_det_fc_station';")"
  DET_UQ="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM TABLE_CONSTRAINTS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot' AND CONSTRAINT_NAME='uq_det_forecast_vintage';")"
  DET_CHK="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM TABLE_CONSTRAINTS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot' AND CONSTRAINT_TYPE='CHECK';")"
  DET_IDX="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(DISTINCT INDEX_NAME) FROM STATISTICS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot' AND INDEX_NAME IN ('idx_det_res_target_issue','idx_det_vintage_batch','idx_det_station_target','idx_det_active_lookup');")"
  PROB_COLS="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM COLUMNS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_snapshot' AND COLUMN_NAME IN ('release_group_id','ingestion_batch_id');")"
  PROB_IDX="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(DISTINCT INDEX_NAME) FROM STATISTICS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_snapshot' AND INDEX_NAME='idx_fc_res_target_issue';")"

  echo "Hasil Pemeriksaan Skema:"
  echo "  cews_forecast_deterministic_snapshot : ${DET_EXISTS} (expected 1)"
  echo "  fk_det_fc_station                    : ${DET_FK} (expected 1)"
  echo "  uq_det_forecast_vintage              : ${DET_UQ} (expected 1)"
  echo "  CHECK constraints                    : ${DET_CHK} (expected 3)"
  echo "  4 composite indexes                  : ${DET_IDX} (expected 4)"
  echo "  cews_forecast_snapshot new columns   : ${PROB_COLS} (expected 2)"
  echo "  idx_fc_res_target_issue              : ${PROB_IDX} (expected 1)"
  echo "Hasil Pemeriksaan Data Historis:"
  echo "  stations               : ${POST_STN} (baseline ${STN_CNT})"
  echo "  cews_rainfall_daily    : ${POST_CH} (baseline ${CH_CNT})"
  echo "  cews_forecast_snapshot : ${POST_PROB_CNT} (baseline ${PROB_CNT}) | SUM = ${POST_PROB_SUM} (baseline ${PROB_SUM})"

  if [[ "${DET_EXISTS}" != "1" || "${DET_FK}" != "1" || "${DET_UQ}" != "1" || "${DET_CHK}" != "3" || "${DET_IDX}" != "4" || "${PROB_COLS}" != "2" || "${PROB_IDX}" != "1" ]]; then
    echo "========================================================================"
    echo "STATUS MODE 2 (MIGRATION ONLY): FAIL — VALIDASI SKEMA TIDAK LENGKAP"
    echo "========================================================================"
    exit 1
  fi

  if [[ "${POST_STN}" != "${STN_CNT}" || "${POST_CH}" != "${CH_CNT}" || "${POST_PROB_CNT}" != "${PROB_CNT}" || "${POST_PROB_SUM}" != "${PROB_SUM}" ]]; then
    echo "========================================================================"
    echo "STATUS MODE 2 (MIGRATION ONLY): FAIL — DATA HISTORIS BERUBAH"
    echo "========================================================================"
    exit 1
  fi

  echo ""
  echo "========================================================================"
  echo "STATUS MODE 2 (MIGRATION ONLY): PASS — DATABASE PRODUKSI SIAP DEPLOY"
  echo "========================================================================"
  exit 0
fi
