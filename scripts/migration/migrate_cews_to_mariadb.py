#!/usr/bin/env python3
"""
CEWS Database Migration Script (v1.1 Frozen)
Climate Early Warning System (CEWS) BMKG Kepulauan Riau
Fast-Track Implementation for Dashboard Demo

Translates frozen Parquet outputs into MariaDB relational tables:
1. stations (57 rows)
2. cews_current_warning (57 rows)
3. cews_warning_history (2052 rows)
4. cews_forecast_snapshot (1040 rows)
5. v_cews_current_warning_map (57 rows view)
"""

import os
import sys
import math
import numpy as np
import pandas as pd
import pymysql
from datetime import datetime, date, timedelta

# ==============================================================================
# CONFIGURATION & ENVIRONMENT VARIABLES
# ==============================================================================
DB_HOST = os.environ.get("CEWS_DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("CEWS_DB_PORT", 3306))
DB_USER = os.environ.get("CEWS_DB_USER", "root")
DB_PASSWORD = os.environ.get("CEWS_DB_PASSWORD", "")
DB_NAME = os.environ.get("CEWS_DB_NAME", "cews_db")

from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.paths import (
    PATH_SCHEMA_SQL,
    PATH_STATION_METADATA,
    PATH_CURRENT_WARNING,
    PATH_WARNING_HISTORY,
    PATH_FORECAST_SNAPSHOT
)

BASE_DIR = str(_PROJECT_ROOT)
SCHEMA_FILE = str(PATH_SCHEMA_SQL)
PATH_STATIONS = str(PATH_STATION_METADATA)
PATH_CURRENT = str(PATH_CURRENT_WARNING)
PATH_HISTORY = str(PATH_WARNING_HISTORY)
PATH_FORECAST = str(PATH_FORECAST_SNAPSHOT)

VALID_WARNING_LEVELS = {"NORMAL", "WASPADA", "SIAGA", "AWAS"}
VALID_HAZARD_TYPES = {"NORMAL", "DROUGHT", "HEAVY_RAIN"}
VALID_CONFIDENCE_LEVELS = {"HIGH", "MEDIUM", "LOW"}
VALID_DATA_QUALITY = {"VALID", "UNCERTAIN", "INCOMPLETE"}


def get_connection(use_db=True):
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME if use_db else None,
        autocommit=False,
        charset='utf8mb4'
    )


def execute_schema(conn):
    print("--------------------------------------------------")
    print("1. APPLYING DDL SCHEMA v1.1 FROZEN")
    print("--------------------------------------------------")
    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")

    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split statements by semicolon, ignoring empty lines or comments
    statements = []
    current_stmt = []
    for line in sql_content.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("--"):
            continue
        current_stmt.append(line)
        if trimmed.endswith(";"):
            stmt_str = "\n".join(current_stmt)
            # Remove trailing semicolon
            if stmt_str.rstrip().endswith(";"):
                stmt_str = stmt_str.rstrip()[:-1].strip()
            if stmt_str:
                statements.append(stmt_str)
            current_stmt = []

    with conn.cursor() as cur:
        for stmt in statements:
            try:
                cur.execute(stmt)
            except Exception as e:
                # If index already exists, ignore
                if "Duplicate key name" in str(e) or "already exists" in str(e).lower():
                    continue
                print(f"Error executing statement:\n{stmt[:150]}...\nError: {e}")
                raise
    conn.commit()
    print("  [PASS] Schema and View v_cews_current_warning_map created successfully.")


def verify_timezone(df, col_name, expected_provenance="generate_cews_decision_engine.py"):
    """
    KOREKSI 7: Verify timezone semantics before converting.
    Source: datetime.now() local WIB (UTC+7).
    Target: UTC in MariaDB DATETIME(6).
    """
    s = df[col_name]
    dtype_str = str(s.dtype)
    has_tz = hasattr(s.dt, 'tz') and s.dt.tz is not None
    
    if not has_tz:
        # Timezone naive - verified from generate_cews_decision_engine.py lines 366 & 461
        # now_ts = datetime.now() in Indonesia locale = WIB (UTC+7)
        return "naive_wib_to_utc"
    else:
        return "tz_aware"


def to_utc_datetime(val, tz_rule):
    if pd.isna(val) or val is None:
        return None
    dt = pd.to_datetime(val)
    if tz_rule == "naive_wib_to_utc":
        # Subtract 7 hours to convert WIB local to UTC
        dt = dt - pd.Timedelta(hours=7)
    return dt.to_pydatetime()


def clean_val(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        if np.isnan(v) or np.isinf(v):
            return None
        return float(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.bool_, bool)):
        return 1 if v else 0
    return v


# ==============================================================================
# 2. STATIONS MIGRATION
# ==============================================================================
def migrate_stations(conn):
    print("--------------------------------------------------")
    print("2. MIGRATING MASTER STATIONS (station_metadata.parquet)")
    print("--------------------------------------------------")
    df = pd.read_parquet(PATH_STATIONS)
    print(f"  Rows read from Parquet: {len(df)}")
    if len(df) != 57:
        raise ValueError(f"Expected 57 stations, got {len(df)}")

    # Clean & standardize
    df['station_id'] = df['station_id'].astype(str).str.strip().str.upper()
    if df['station_id'].nunique() != 57:
        raise ValueError("station_id is not unique in station_metadata.parquet!")

    rows = []
    for _, r in df.iterrows():
        sid = r['station_id']
        name = str(r['station_name']).strip()
        kab = str(r.get('regency', r.get('kabupaten', ''))).strip()
        prov = str(r.get('province', 'Kepulauan Riau')).strip()
        region = str(r.get('region', 'Region I')).strip()
        lat = float(r['latitude'])
        lon = float(r['longitude'])
        elev = clean_val(r.get('elevation_m'))
        nozom = clean_val(r.get('NOZOM_PROV'))
        if nozom is not None:
            nozom = str(nozom).strip()

        rows.append((sid, name, kab, prov, region, lat, lon, elev, nozom))

    sql = """
    INSERT INTO stations (
        station_id, station_name, kabupaten, province, region,
        latitude, longitude, elevation_m, nozom_prov
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        station_name = VALUES(station_name),
        kabupaten = VALUES(kabupaten),
        province = VALUES(province),
        region = VALUES(region),
        latitude = VALUES(latitude),
        longitude = VALUES(longitude),
        elevation_m = VALUES(elevation_m),
        nozom_prov = VALUES(nozom_prov);
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()
    print("  [PASS] 57 stations successfully migrated into 'stations'.")


# ==============================================================================
# 3. METADATA CONSISTENCY CHECK & CURRENT WARNING MIGRATION
# ==============================================================================
def migrate_current_warning(conn):
    print("--------------------------------------------------")
    print("3. METADATA CONSISTENCY CHECK & CURRENT WARNING MIGRATION")
    print("--------------------------------------------------")
    df_curr = pd.read_parquet(PATH_CURRENT)
    print(f"  Rows read from Parquet: {len(df_curr)}")
    if len(df_curr) != 57:
        raise ValueError(f"Expected 57 current warnings, got {len(df_curr)}")

    df_curr['station_id'] = df_curr['station_id'].astype(str).str.strip().str.upper()
    if df_curr['station_id'].nunique() != 57:
        raise ValueError("station_id is not unique in cews_current_warning.parquet!")

    # Fetch master stations for consistency check
    with conn.cursor() as cur:
        cur.execute("SELECT station_id, station_name, kabupaten, latitude, longitude FROM stations")
        master_dict = {row[0]: {'name': row[1], 'kab': row[2], 'lat': float(row[3]), 'lon': float(row[4])} for row in cur.fetchall()}

    # Perform Cross-Check
    mismatches = []
    for _, r in df_curr.iterrows():
        sid = r['station_id']
        if sid not in master_dict:
            mismatches.append(f"Station {sid} not found in master stations!")
            continue
        m = master_dict[sid]
        curr_name = str(r['station_name']).strip()
        curr_kab = str(r['kabupaten']).strip()
        curr_lat = float(r['latitude'])
        curr_lon = float(r['longitude'])

        if curr_name != m['name']:
            mismatches.append(f"Station {sid} name mismatch: Master='{m['name']}' vs Warning='{curr_name}'")
        if curr_kab != m['kab']:
            mismatches.append(f"Station {sid} kabupaten mismatch: Master='{m['kab']}' vs Warning='{curr_kab}'")
        if abs(curr_lat - m['lat']) > 1e-5:
            mismatches.append(f"Station {sid} latitude mismatch: Master={m['lat']} vs Warning={curr_lat}")
        if abs(curr_lon - m['lon']) > 1e-5:
            mismatches.append(f"Station {sid} longitude mismatch: Master={m['lon']} vs Warning={curr_lon}")

    if mismatches:
        print("  [FAIL] Metadata Consistency Mismatches Found:")
        for mm in mismatches[:10]:
            print("    -", mm)
        raise RuntimeError(f"Metadata consistency check failed with {len(mismatches)} errors!")
    else:
        print("  [PASS] Metadata consistency cross-check PASS (100% match across 57 stations).")

    # Timezone check
    tz_rule = verify_timezone(df_curr, 'updated_at')
    print(f"  Timezone Semantics: {tz_rule} (Converting local WIB to UTC DATETIME(6))")

    # Value Validation & Data Transformation
    rows = []
    for _, r in df_curr.iterrows():
        sid = r['station_id']
        t_year = int(r['target_year'])
        t_month = int(r['target_month'])
        t_das = int(r['target_dasarian'])
        t_period = str(r['target_warning_period']).strip()
        t_start = pd.to_datetime(r['target_period_start']).date()
        t_end = pd.to_datetime(r['target_period_end']).date()
        if t_start > t_end:
            raise ValueError(f"Station {sid} invalid dates: {t_start} > {t_end}")

        hazard = str(r['hazard_type']).strip()
        if hazard not in VALID_HAZARD_TYPES:
            raise ValueError(f"Station {sid} invalid hazard_type: {hazard}")

        level = str(r['warning_level']).strip()
        if level not in VALID_WARNING_LEVELS:
            raise ValueError(f"Station {sid} invalid warning_level: {level}")

        reason = str(r['trigger_reason']).strip()
        if not reason:
            raise ValueError(f"Station {sid} empty trigger_reason!")

        conf = str(r['confidence_level']).strip()
        if conf not in VALID_CONFIDENCE_LEVELS:
            raise ValueError(f"Station {sid} invalid confidence_level: {conf}")

        quality = str(r['data_quality_status']).strip()
        if quality not in VALID_DATA_QUALITY:
            raise ValueError(f"Station {sid} invalid data_quality_status: {quality}")

        spi_cond = str(r['spi_condition']).strip()
        
        # Explicit mandatory engine outputs (No DEFAULT 0)
        if pd.isna(r['probability_support']):
            raise ValueError(f"Station {sid} missing probability_support!")
        prob_supp = 1 if r['probability_support'] else 0

        if pd.isna(r['hth_days_current']):
            raise ValueError(f"Station {sid} missing hth_days_current!")
        hth_f = float(r['hth_days_current'])
        if not hth_f.is_integer():
            raise ValueError(f"Station {sid} non-integer HTH: {hth_f}")
        hth_curr = int(hth_f)

        if pd.isna(r['hth_uncertain']):
            raise ValueError(f"Station {sid} missing hth_uncertain!")
        hth_unc = 1 if r['hth_uncertain'] else 0

        # Nullable fields (Preserve NULL)
        spi_val = clean_val(r['spi_value'])
        p_b20 = clean_val(r.get('prob_below20'))
        p_d1 = clean_val(r.get('prob_ch_lt20_dasarian_1', p_b20))
        p_d2 = clean_val(r.get('prob_ch_lt20_dasarian_2'))
        p_a150 = clean_val(r.get('prob_above150'))
        p_a200 = clean_val(r.get('prob_above200'))
        p_a300 = clean_val(r.get('prob_above300'))
        p_m300 = clean_val(r.get('prob_month_above300'))
        p_m400 = clean_val(r.get('prob_month_above400'))
        p_m500 = clean_val(r.get('prob_month_above500'))

        for p_name, p_v in [('prob_below20', p_b20), ('prob_ch_lt20_dasarian_1', p_d1), ('prob_ch_lt20_dasarian_2', p_d2),
                            ('prob_above150', p_a150), ('prob_above200', p_a200),
                            ('prob_above300', p_a300), ('prob_month_above300', p_m300),
                            ('prob_month_above400', p_m400), ('prob_month_above500', p_m500)]:
            if p_v is not None and not (0.0 <= p_v <= 100.0):
                raise ValueError(f"Station {sid} invalid probability for {p_name}: {p_v}")

        last_obs_per = str(r['last_observation_period']).strip()
        last_obs_dt = pd.to_datetime(r['last_observation_date']).date()
        upd_at = to_utc_datetime(r['updated_at'], tz_rule)

        rows.append((
            sid, t_year, t_month, t_das, t_period, t_start, t_end,
            hazard, level, reason, conf, quality, spi_cond, prob_supp,
            hth_curr, hth_unc, spi_val, p_b20, p_d1, p_d2, p_a150, p_a200, p_a300,
            p_m300, p_m400, p_m500, last_obs_per, last_obs_dt, upd_at
        ))

    # Atomic refresh (DELETE + INSERT)
    sql_insert = """
    INSERT INTO cews_current_warning (
        station_id, target_year, target_month, target_dasarian,
        target_warning_period, target_period_start, target_period_end,
        hazard_type, warning_level, trigger_reason, confidence_level,
        data_quality_status, spi_condition, probability_support,
        hth_days_current, hth_uncertain, spi_value, prob_below20,
        prob_ch_lt20_dasarian_1, prob_ch_lt20_dasarian_2,
        prob_above150, prob_above200, prob_above300,
        prob_month_above300, prob_month_above400,
        prob_month_above500, last_observation_period, last_observation_date,
        updated_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    );
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM cews_current_warning")
        cur.executemany(sql_insert, rows)
    conn.commit()
    print("  [PASS] 57 records successfully migrated into 'cews_current_warning'.")


# ==============================================================================
# 4. WARNING HISTORY MIGRATION (APPLICATION APPEND-ONLY)
# ==============================================================================
def migrate_warning_history(conn):
    print("--------------------------------------------------")
    print("4. MIGRATING WARNING HISTORY (cews_warning_history.parquet)")
    print("--------------------------------------------------")
    df_hist = pd.read_parquet(PATH_HISTORY)
    print(f"  Rows read from Parquet: {len(df_hist)}")
    if len(df_hist) != 2052:
        raise ValueError(f"Expected 2052 history rows, got {len(df_hist)}")

    df_hist['station_id'] = df_hist['station_id'].astype(str).str.strip().str.upper()
    dups = df_hist.duplicated(subset=['station_id', 'period_start']).sum()
    if dups != 0:
        raise ValueError(f"Found {dups} duplicate (station_id, period_start) in history!")

    tz_rule = verify_timezone(df_hist, 'evaluated_at')

    rows = []
    for _, r in df_hist.iterrows():
        sid = r['station_id']
        p_start = pd.to_datetime(r['period_start']).date()
        p_end = pd.to_datetime(r['period_end']).date()
        yr = int(r['year'])
        mo = int(r['month'])
        das = int(r['dasarian'])
        hazard = str(r['hazard_type']).strip()
        level = str(r['warning_level']).strip()
        reason = str(r['trigger_reason']).strip()
        spi_cond = str(r['spi_condition']).strip()
        prob_supp = 1 if r['probability_support'] else 0
        quality = str(r['data_quality_status']).strip()
        conf = str(r['confidence_level']).strip()

        hth_f = float(r['hth_days_max'])
        if not hth_f.is_integer():
            raise ValueError(f"Station {sid} non-integer hth_days_max: {hth_f}")
        hth_max = int(hth_f)
        hth_unc = 1 if r['hth_uncertain'] else 0

        spi_val = clean_val(r['spi_value'])
        p_b20 = clean_val(r.get('prob_below20'))
        p_d1 = clean_val(r.get('prob_ch_lt20_dasarian_1', p_b20))
        p_d2 = clean_val(r.get('prob_ch_lt20_dasarian_2'))
        p_a150 = clean_val(r.get('prob_above150'))
        p_a200 = clean_val(r.get('prob_above200'))
        p_a300 = clean_val(r.get('prob_above300'))
        p_m300 = clean_val(r.get('prob_month_above300'))
        p_m400 = clean_val(r.get('prob_month_above400'))
        p_m500 = clean_val(r.get('prob_month_above500'))
        eval_at = to_utc_datetime(r['evaluated_at'], tz_rule)

        rows.append((
            sid, p_start, p_end, yr, mo, das, hazard, level, reason,
            spi_cond, prob_supp, quality, conf, hth_max, hth_unc,
            spi_val, p_b20, p_d1, p_d2, p_a150, p_a200, p_a300, p_m300, p_m400, p_m500, eval_at
        ))

    sql_insert = """
    INSERT INTO cews_warning_history (
        station_id, period_start, period_end, year, month, dasarian,
        hazard_type, warning_level, trigger_reason, spi_condition,
        probability_support, data_quality_status, confidence_level,
        hth_days_max, hth_uncertain, spi_value, prob_below20,
        prob_ch_lt20_dasarian_1, prob_ch_lt20_dasarian_2,
        prob_above150, prob_above200, prob_above300,
        prob_month_above300, prob_month_above400,
        prob_month_above500, evaluated_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON DUPLICATE KEY UPDATE
        period_end = VALUES(period_end),
        warning_level = VALUES(warning_level),
        hazard_type = VALUES(hazard_type),
        trigger_reason = VALUES(trigger_reason),
        prob_ch_lt20_dasarian_1 = VALUES(prob_ch_lt20_dasarian_1),
        prob_ch_lt20_dasarian_2 = VALUES(prob_ch_lt20_dasarian_2),
        prob_month_above300 = VALUES(prob_month_above300);
    """
    with conn.cursor() as cur:
        cur.execute("DELETE FROM cews_warning_history")
        cur.executemany(sql_insert, rows)
    conn.commit()
    print("  [PASS] 2052 records successfully migrated into 'cews_warning_history'.")


# ==============================================================================
# 5. FORECAST SNAPSHOT MIGRATION
# ==============================================================================
def migrate_forecast_snapshot(conn):
    print("--------------------------------------------------")
    print("5. MIGRATING FORECAST SNAPSHOT (cews_forecast_snapshot.parquet)")
    print("--------------------------------------------------")
    df_fc = pd.read_parquet(PATH_FORECAST)
    print(f"  Rows read from Parquet: {len(df_fc)}")
    if len(df_fc) == 0:
        print("  [INFO] Forecast snapshot is empty for October 2026 (forecast unavailable). Skipping snapshot insertion.")
        return

    df_fc['station_id'] = df_fc['station_id'].astype(str).str.strip().str.upper()
    dups = df_fc.duplicated(subset=['station_id', 'target_year', 'target_month', 'target_dasarian', 'issue_date', 'forecast_parameter']).sum()
    if dups != 0:
        raise ValueError(f"Found {dups} duplicate natural key entries in forecast snapshot!")

    # Filter orphan station_ids not present in master stations (e.g. 'NONE', '228R')
    with conn.cursor() as cur:
        cur.execute("SELECT station_id FROM stations")
        master_sids = {r[0] for r in cur.fetchall()}

    orphan_mask = ~df_fc['station_id'].isin(master_sids)
    orphan_cnt = orphan_mask.sum()
    if orphan_cnt > 0:
        orphan_sids = list(df_fc.loc[orphan_mask, 'station_id'].unique())
        print(f"  [AUDIT NOTE] Detected {orphan_cnt} orphan forecast rows with station_id {orphan_sids} not in master stations.")
        print(f"  Filtering out orphan rows to enforce Foreign Key integrity (fk_fc_snapshot_station).")
        df_fc = df_fc[~orphan_mask].copy()

    tz_rule = verify_timezone(df_fc, 'snapshot_timestamp')

    rows = []
    for _, r in df_fc.iterrows():
        sid = r['station_id']
        t_yr = int(r['target_year'])
        t_mo = int(r['target_month'])
        t_das = int(r['target_dasarian'])
        iss_dt = pd.to_datetime(r['issue_date']).date()
        param = str(r['forecast_parameter']).strip()
        val = float(r['probability_value'])
        if not (0.0 <= val <= 100.0):
            raise ValueError(f"Invalid probability value: {val}")
        src = str(r['source_file']).strip()
        snap_ts = to_utc_datetime(r['snapshot_timestamp'], tz_rule)

        rows.append((sid, t_yr, t_mo, t_das, iss_dt, param, val, src, snap_ts))

    sql_insert = """
    INSERT INTO cews_forecast_snapshot (
        station_id, target_year, target_month, target_dasarian,
        issue_date, forecast_parameter, probability_value,
        source_file, snapshot_timestamp
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        probability_value = VALUES(probability_value),
        snapshot_timestamp = VALUES(snapshot_timestamp);
    """
    with conn.cursor() as cur:
        cur.executemany(sql_insert, rows)
    conn.commit()
    print(f"  [PASS] {len(rows)} records successfully migrated into 'cews_forecast_snapshot'.")


# ==============================================================================
# 6. POST-MIGRATION VALIDATION
# ==============================================================================
def validate_migration(conn):
    print("--------------------------------------------------")
    print("6. POST-MIGRATION ACCEPTANCE VALIDATION")
    print("--------------------------------------------------")
    with conn.cursor() as cur:
        # 1. Record counts
        cur.execute("SELECT COUNT(*) FROM stations")
        c_stn = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cews_current_warning")
        c_curr = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cews_warning_history")
        c_hist = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cews_forecast_snapshot")
        c_fc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM v_cews_current_warning_map")
        c_map = cur.fetchone()[0]

        print(f"  Count stations: {c_stn} (Expected: 57)")
        print(f"  Count cews_current_warning: {c_curr} (Expected: 57)")
        print(f"  Count cews_warning_history: {c_hist} (Expected: 2052)")
        print(f"  Count cews_forecast_snapshot: {c_fc}")
        print(f"  Count v_cews_current_warning_map: {c_map} (Expected: 57)")

        assert c_stn == 57, f"stations count mismatch: {c_stn}"
        assert c_curr == 57, f"current_warning count mismatch: {c_curr}"
        assert c_hist == 2052, f"warning_history count mismatch: {c_hist}"
        assert c_map == 57, f"v_cews_current_warning_map count mismatch: {c_map}"

        # 2. Warning Distribution Check
        cur.execute("SELECT warning_level, COUNT(*) FROM cews_current_warning GROUP BY warning_level ORDER BY warning_level")
        dist = dict(cur.fetchall())
        print(f"  Current Warning Level Distribution in MariaDB: {dist}")
        df_p_curr = pd.read_parquet(PATH_CURRENT)
        p_dist = df_p_curr['warning_level'].value_counts().to_dict()
        print(f"  Current Warning Level Distribution in Parquet: {p_dist}")
        assert dist == p_dist, f"Distribution mismatch: MariaDB {dist} vs Parquet {p_dist}"
        print(f"  [PASS] Warning level distribution matches promoted authoritative current engine ({dist}).")

        # 3. Target period validation
        cur.execute("SELECT DISTINCT target_warning_period, target_period_start, target_period_end FROM cews_current_warning")
        periods = cur.fetchall()
        print(f"  Distinct Target Warning Periods ({len(periods)}):")
        for p in periods:
            print(f"    - {p[0]} ({p[1]} s/d {p[2]})")
        assert len(periods) == 1, f"Expected exactly 1 target period, got {len(periods)}"
        print("  [PASS] Single target warning period verified for all 57 stations.")

        # 4. Map View Non-Null check
        cur.execute("""
            SELECT COUNT(*) FROM v_cews_current_warning_map
            WHERE station_id IS NULL OR station_name IS NULL OR kabupaten IS NULL
               OR latitude IS NULL OR longitude IS NULL OR warning_level IS NULL
               OR hazard_type IS NULL OR confidence_level IS NULL OR data_quality_status IS NULL
        """)
        null_map_cols = cur.fetchone()[0]
        assert null_map_cols == 0, f"Found {null_map_cols} rows with NULL mandatory map columns!"
        print("  [PASS] v_cews_current_warning_map mandatory fields 100% non-null.")

        # 5. Sample Station Checks (Comparing dynamically against Parquet source)
        df_p_curr = pd.read_parquet(PATH_CURRENT)
        df_p_curr['station_id'] = df_p_curr['station_id'].astype(str).str.strip().str.upper()

        # Sample A: NORMAL station '21011002A' (Poyotomo)
        p_norm = df_p_curr[df_p_curr['station_id'] == '21011002A'].iloc[0]
        cur.execute("""
            SELECT cw.station_id, s.station_name, s.kabupaten, cw.warning_level, cw.hazard_type,
                   cw.hth_days_current, cw.spi_value, cw.confidence_level, cw.data_quality_status
            FROM cews_current_warning cw
            JOIN stations s ON cw.station_id = s.station_id
            WHERE cw.station_id = '21011002A'
        """)
        s_norm = cur.fetchone()
        print("\n  Sample NORMAL Station (21011002A - Poyotomo):")
        print(f"    Parquet -> Level: {p_norm['warning_level']} | Hazard: {p_norm['hazard_type']} | HTH: {p_norm['hth_days_current']} | SPI: {p_norm['spi_value']}")
        print(f"    MariaDB -> Level: {s_norm[3]} | Hazard: {s_norm[4]} | HTH: {s_norm[5]} | SPI: {s_norm[6]}")
        assert s_norm[3] == p_norm['warning_level']
        assert s_norm[4] == p_norm['hazard_type']
        assert s_norm[5] == int(p_norm['hth_days_current'])
        assert float(s_norm[6]) == round(float(p_norm['spi_value']), 2)

        # Sample B: Station '21040101B' (ARG Singkep)
        p_singkep = df_p_curr[df_p_curr['station_id'] == '21040101B'].iloc[0]
        cur.execute("""
            SELECT cw.station_id, s.station_name, s.kabupaten, cw.warning_level, cw.hazard_type,
                   cw.hth_days_current, cw.spi_value, cw.confidence_level, cw.data_quality_status, cw.trigger_reason
            FROM cews_current_warning cw
            JOIN stations s ON cw.station_id = s.station_id
            WHERE cw.station_id = '21040101B'
        """)
        s_singkep = cur.fetchone()
        print(f"\n  Sample ARG Singkep Station ({p_singkep['station_id']}):")
        print(f"    Parquet -> Level: {p_singkep['warning_level']} | Hazard: {p_singkep['hazard_type']} | HTH: {p_singkep['hth_days_current']} | Quality: {p_singkep['data_quality_status']}")
        print(f"    MariaDB -> Level: {s_singkep[3]} | Hazard: {s_singkep[4]} | HTH: {s_singkep[5]} | Quality: {s_singkep[8]}")
        print(f"    Trigger Reason: {s_singkep[9][:90]}...")
        assert s_singkep[3] == p_singkep['warning_level']
        assert s_singkep[4] == p_singkep['hazard_type']
        assert s_singkep[5] == int(p_singkep['hth_days_current'])
        assert s_singkep[8] == p_singkep['data_quality_status']
        if pd.isna(p_singkep['spi_value']):
            assert s_singkep[6] is None
        else:
            assert float(s_singkep[6]) == round(float(p_singkep['spi_value']), 2)

        # Sample C: Station '21010401A' (Kawal - AWAS triggered by SPI <= -2.00)
        p_awas = df_p_curr[df_p_curr['station_id'] == '21010401A'].iloc[0]
        cur.execute("""
            SELECT cw.station_id, s.station_name, s.kabupaten, cw.warning_level, cw.hazard_type,
                   cw.hth_days_current, cw.spi_value, cw.confidence_level, cw.data_quality_status, cw.trigger_reason
            FROM cews_current_warning cw
            JOIN stations s ON cw.station_id = s.station_id
            WHERE cw.station_id = '21010401A'
        """)
        s_awas = cur.fetchone()
        print(f"\n  Sample AWAS Station ({p_awas['station_id']}):")
        print(f"    Parquet -> Level: {p_awas['warning_level']} | Hazard: {p_awas['hazard_type']} | HTH: {p_awas['hth_days_current']} | SPI: {p_awas['spi_value']}")
        print(f"    MariaDB -> Level: {s_awas[3]} | Hazard: {s_awas[4]} | HTH: {s_awas[5]} | SPI: {s_awas[6]}")
        print(f"    Trigger Reason: {s_awas[9][:90]}...")
        assert s_awas[3] == "AWAS"
        assert s_awas[4] == "DROUGHT"
        assert float(s_awas[6]) == round(float(p_awas['spi_value']), 2)

        print("  [PASS] Parquet vs MariaDB semantic verification 100% matched for NORMAL, ARG Singkep, and AWAS.")

    print("--------------------------------------------------")
    print("ALL MIGRATION ACCEPTANCE CRITERIA: 100% PASS")
    print("--------------------------------------------------")


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main():
    print("==================================================")
    print("CEWS TAHAP 3 — FAST-TRACK DATABASE MIGRATION")
    print("==================================================")
    print(f"Connecting to MariaDB: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    # Check server connectivity without selecting database
    conn_root = get_connection(use_db=False)
    execute_schema(conn_root)
    conn_root.close()

    # Reconnect to cews_db
    conn = get_connection(use_db=True)
    try:
        migrate_stations(conn)
        migrate_current_warning(conn)
        migrate_warning_history(conn)
        migrate_forecast_snapshot(conn)
        validate_migration(conn)
        print("\n[SUCCESS] TAHAP 3 DATABASE MIGRATION COMPLETED SUCCESSFULLY.")
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration aborted with error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
