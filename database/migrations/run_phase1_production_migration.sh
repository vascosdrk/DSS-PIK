#!/usr/bin/env bash
# ==============================================================================
# DSS-PIK — Phase 1 Production Migration Runner (Self-Contained & Fail-Fast)
#
# Target: Coolify MariaDB 11.4 container (database: cews_db)
#
# What this script does automatically (exits immediately on ANY error):
#   1. Preflight check: verifies MariaDB connection, database `cews_db`,
#      `stations` (57 rows), `cews_forecast_snapshot`, and persistent backup mount.
#   2. Full UTF-8 backup (`mariadb-dump --single-transaction --routines --triggers --events`).
#   3. Backup file integrity check (non-empty + valid SQL footer `Dump completed`).
#   4. Isolated restore verification into temporary DB `cews_db_restore_verify`,
#      comparing exact row counts & `SUM(probability_value)` against live `cews_db`,
#      then dropping ONLY the temporary DB.
#   5. Applies BOTH Phase 1 additive migrations verbatim (Run 1):
#      - 20261127_add_forecast_deterministic_snapshot.sql
#      - 20261127_harden_forecast_snapshot_indexes.sql
#   6. Re-applies BOTH migrations verbatim (Run 2 — Idempotency Verification).
#   7. Post-migration verification: table, columns, FK, unique key, indexes,
#      CHECK constraints, and exact preservation of historical data.
#
# Usage inside Coolify MariaDB Container Terminal:
#   BACKUP_DIR=/backups bash run_phase1_production_migration.sh
#
# Notes:
#   - Uses $MARIADB_ROOT_PASSWORD already set in the MariaDB container env.
#   - Refuses to write backup to ephemeral container rootfs unless BACKUP_DIR
#     is on a verified persistent mount (or ALLOW_EPHEMERAL_BACKUP=1 is set
#     ONLY after taking a Coolify-managed database backup first).
#   - Never runs DROP TABLE / DROP COLUMN on `cews_db` or modifies historical rows.
# ==============================================================================
set -euo pipefail

DB_NAME="${CEWS_DB_NAME:-cews_db}"
DB_USER="root"
DB_PASS="${MARIADB_ROOT_PASSWORD:?MARIADB_ROOT_PASSWORD is not set in container environment}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
TEMP_DB="cews_db_restore_verify"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/cews_db_pre_phase1_${TS}.sql"

mysql_exec() {
  mariadb -u"${DB_USER}" -p"${DB_PASS}" --default-character-set=utf8mb4 "$@"
}

echo "========================================================================"
echo "[1/7] PREFLIGHT CHECK — Database: ${DB_NAME}"
echo "========================================================================"
mysql_exec -e "SELECT VERSION() AS mariadb_version, NOW() AS server_time;"

# Verify backup directory is persistent (never silently write to /var/lib/mysql or ephemeral /)
if [[ "${BACKUP_DIR}" == /var/lib/mysql* ]]; then
  echo "ERROR: BACKUP_DIR (${BACKUP_DIR}) tidak boleh berada di dalam /var/lib/mysql (datadir InnoDB)."
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
if command -v mountpoint >/dev/null 2>&1; then
  if ! mountpoint -q "${BACKUP_DIR}"; then
    if [[ "${ALLOW_EPHEMERAL_BACKUP:-0}" != "1" ]]; then
      echo "ERROR: ${BACKUP_DIR} BUKAN persistent volume mount!"
      echo "Tambahkan volume persisten (mis. dss_pik_db_backups:/backups pada compose.coolify.yaml),"
      echo "ATAU buat backup melalui Coolify Backup terlebih dahulu lalu jalankan dengan ALLOW_EPHEMERAL_BACKUP=1."
      exit 1
    else
      echo "WARNING: ALLOW_EPHEMERAL_BACKUP=1 aktif — pastikan backup Coolify eksternal sudah tersimpan."
    fi
  else
    echo "OK: ${BACKUP_DIR} terkonfirmasi sebagai persistent mount."
  fi
fi

# Capture exact live baseline before any operation
STN_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM stations;")"
CH_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_rainfall_daily;")"
PROB_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_forecast_snapshot;")"
PROB_SUM="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COALESCE(ROUND(SUM(probability_value), 2), 0) FROM cews_forecast_snapshot;")"
STN_COL_TYPE="$(mysql_exec -N -B -D information_schema -e "SELECT CONCAT(COLUMN_TYPE, ' ', COLLATION_NAME) FROM COLUMNS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='stations' AND COLUMN_NAME='station_id';")"

echo "Baseline Live ${DB_NAME}:"
echo "  stations               : ${STN_CNT} (station_id = ${STN_COL_TYPE})"
echo "  cews_rainfall_daily    : ${CH_CNT}"
echo "  cews_forecast_snapshot : ${PROB_CNT} rows | SUM(probability_value) = ${PROB_SUM}"

if [[ "${STN_CNT}" -lt 57 ]]; then
  echo "ERROR: Jumlah master stations (${STN_CNT}) kurang dari 57. Menghentikan migrasi."
  exit 1
fi

echo ""
echo "========================================================================"
echo "[2/7] FULL UTF-8 BACKUP -> ${BACKUP_FILE}"
echo "========================================================================"
mariadb-dump -u"${DB_USER}" -p"${DB_PASS}" \
  --single-transaction --routines --triggers --events \
  --default-character-set=utf8mb4 \
  "${DB_NAME}" > "${BACKUP_FILE}"

echo ""
echo "========================================================================"
echo "[3/7] VERIFIKASI INTEGRITAS FILE BACKUP"
echo "========================================================================"
if [[ ! -s "${BACKUP_FILE}" ]]; then
  echo "ERROR: File backup kosong atau tidak ditemukan."
  exit 1
fi
BACKUP_BYTES="$(wc -c < "${BACKUP_FILE}")"
if ! tail -n 5 "${BACKUP_FILE}" | grep -q "Dump completed"; then
  echo "ERROR: Footer 'Dump completed' tidak ditemukan pada ${BACKUP_FILE}. Backup tidak utuh."
  exit 1
fi
echo "OK: Backup valid (${BACKUP_BYTES} bytes, footer 'Dump completed' terverifikasi)."

echo ""
echo "========================================================================"
echo "[4/7] VERIFIKASI RESTORE KE DATABASE SEMENTARA (${TEMP_DB})"
echo "========================================================================"
trap 'mysql_exec -e "DROP DATABASE IF EXISTS \`${TEMP_DB}\`;" >/dev/null 2>&1 || true' EXIT

mysql_exec -e "DROP DATABASE IF EXISTS \`${TEMP_DB}\`; CREATE DATABASE \`${TEMP_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql_exec -D "${TEMP_DB}" < "${BACKUP_FILE}"

TMP_STN="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COUNT(*) FROM stations;")"
TMP_CH="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COUNT(*) FROM cews_rainfall_daily;")"
TMP_PROB_CNT="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COUNT(*) FROM cews_forecast_snapshot;")"
TMP_PROB_SUM="$(mysql_exec -N -B -D "${TEMP_DB}" -e "SELECT COALESCE(ROUND(SUM(probability_value), 2), 0) FROM cews_forecast_snapshot;")"

echo "Hasil Restore ${TEMP_DB}:"
echo "  stations               : ${TMP_STN} (expected ${STN_CNT})"
echo "  cews_rainfall_daily    : ${TMP_CH} (expected ${CH_CNT})"
echo "  cews_forecast_snapshot : ${TMP_PROB_CNT} rows (expected ${PROB_CNT}) | SUM = ${TMP_PROB_SUM} (expected ${PROB_SUM})"

if [[ "${TMP_STN}" != "${STN_CNT}" || "${TMP_CH}" != "${CH_CNT}" || "${TMP_PROB_CNT}" != "${PROB_CNT}" || "${TMP_PROB_SUM}" != "${PROB_SUM}" ]]; then
  echo "ERROR: Ketidakcocokan hasil restore dengan baseline live! Migrasi DIBATALKAN."
  exit 1
fi

mysql_exec -e "DROP DATABASE IF EXISTS \`${TEMP_DB}\`;"
echo "OK: Restore 100% identik dengan baseline live; database sementara dibersihkan."

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

echo ""
echo "========================================================================"
echo "[5/7] EKSEKUSI MIGRASI FASE 1 (RUN 1)"
echo "========================================================================"
apply_phase1_migrations "RUN 1"
echo "OK: Run 1 selesai tanpa error."

echo ""
echo "========================================================================"
echo "[6/7] UJI IDEMPOTENCY MIGRASI FASE 1 (RUN 2)"
echo "========================================================================"
apply_phase1_migrations "RUN 2 - IDEMPOTENCY"
echo "OK: Run 2 idempotency berhasil tanpa error."

echo ""
echo "========================================================================"
echo "[7/7] POST-MIGRATION VERIFICATION"
echo "========================================================================"
POST_STN="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM stations;")"
POST_CH="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_rainfall_daily;")"
POST_PROB_CNT="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COUNT(*) FROM cews_forecast_snapshot;")"
POST_PROB_SUM="$(mysql_exec -N -B -D "${DB_NAME}" -e "SELECT COALESCE(ROUND(SUM(probability_value), 2), 0) FROM cews_forecast_snapshot;")"
DET_EXISTS="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM TABLES WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot';")"
PROB_NEW_COLS="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM COLUMNS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_snapshot' AND COLUMN_NAME IN ('release_group_id','ingestion_batch_id');")"
PROB_IDX="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(DISTINCT INDEX_NAME) FROM STATISTICS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_snapshot' AND INDEX_NAME='idx_fc_res_target_issue';")"
DET_FK="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM TABLE_CONSTRAINTS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot' AND CONSTRAINT_NAME='fk_det_fc_station';")"
DET_UQ="$(mysql_exec -N -B -D information_schema -e "SELECT COUNT(*) FROM TABLE_CONSTRAINTS WHERE TABLE_SCHEMA='${DB_NAME}' AND TABLE_NAME='cews_forecast_deterministic_snapshot' AND CONSTRAINT_NAME='uq_det_forecast_vintage';")"

echo "Verifikasi Skema:"
echo "  cews_forecast_deterministic_snapshot : ${DET_EXISTS} (expected 1)"
echo "  fk_det_fc_station                    : ${DET_FK} (expected 1)"
echo "  uq_det_forecast_vintage              : ${DET_UQ} (expected 1)"
echo "  cews_forecast_snapshot new columns   : ${PROB_NEW_COLS} (expected 2)"
echo "  idx_fc_res_target_issue              : ${PROB_IDX} (expected 1)"
echo "Verifikasi Data Historis:"
echo "  stations               : ${POST_STN} (baseline ${STN_CNT})"
echo "  cews_rainfall_daily    : ${POST_CH} (baseline ${CH_CNT})"
echo "  cews_forecast_snapshot : ${POST_PROB_CNT} (baseline ${PROB_CNT}) | SUM = ${POST_PROB_SUM} (baseline ${PROB_SUM})"

if [[ "${DET_EXISTS}" != "1" || "${DET_FK}" != "1" || "${DET_UQ}" != "1" || "${PROB_NEW_COLS}" != "2" || "${PROB_IDX}" != "1" ]]; then
  echo "ERROR: Validasi struktur pasca-migrasi gagal!"
  exit 1
fi

if [[ "${POST_STN}" != "${STN_CNT}" || "${POST_CH}" != "${CH_CNT}" || "${POST_PROB_CNT}" != "${PROB_CNT}" || "${POST_PROB_SUM}" != "${PROB_SUM}" ]]; then
  echo "ERROR: Data historis berubah pasca-migrasi!"
  exit 1
fi

echo ""
echo "========================================================================"
echo "MIGRASI PRODUKSI FASE 1 SUKSES 100% — SIAP UNTUK GIT PUSH & COOLIFY DEPLOY"
echo "File backup tersimpan di: ${BACKUP_FILE}"
echo "========================================================================"
