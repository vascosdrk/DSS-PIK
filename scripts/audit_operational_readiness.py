import os
import sys
sys.path.insert(0, os.path.abspath('.'))

import pymysql
import pandas as pd
import openpyxl
from datetime import datetime, date
import json

from backend.ingestion_service import (
    parse_rainfall_excel,
    parse_spi_parquet,
    parse_spi_bulanan_excel,
    parse_probability_excel,
    get_master_station_lookup,
)

print("======================================================================", flush=True)
print("  DSS-PIK PHASE 2: OPERATIONAL DATA READINESS & PRE-INGESTION AUDIT  ", flush=True)
print("======================================================================", flush=True)

master_stations = get_master_station_lookup()
print(f"Total Master Stations: {len(master_stations)}", flush=True)
pos_manual_sids = [sid for sid, s in master_stations.items() if not (s.get('is_arg') or 'arg' in s.get('station_name', '').lower())]
arg_sids = [sid for sid, s in master_stations.items() if sid not in pos_manual_sids]
print(f"  Pos Manual: {len(pos_manual_sids)} stations", flush=True)
print(f"  ARG: {len(arg_sids)} stations: {arg_sids}", flush=True)

# --------------------------------------------------------------------
# A. AUDIT CURAH HUJAN (CH)
# --------------------------------------------------------------------
print("\n" + "="*50, flush=True)
print("A. AUDIT CURAH HUJAN HARIAN (CH)", flush=True)
print("="*50, flush=True)

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', database='cews_db', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT MIN(observation_date) as min_d, MAX(observation_date) as max_d, COUNT(*) as cnt, COUNT(DISTINCT station_id) as n_st FROM cews_rainfall_daily")
    db_ch = cur.fetchone()
    print(f"Tersimpan di MariaDB (cews_rainfall_daily):", flush=True)
    print(f"  Total Baris: {db_ch['cnt']:,}", flush=True)
    print(f"  Jumlah Stasiun: {db_ch['n_st']}", flush=True)
    print(f"  Rentang Tanggal: {db_ch['min_d']} s/d {db_ch['max_d']}", flush=True)
    
    cur.execute("SELECT observation_date, COUNT(*) as cnt FROM cews_rainfall_daily WHERE observation_date >= '2026-10-01' GROUP BY observation_date ORDER BY observation_date")
    oct_db = cur.fetchall()
    print(f"  Data Oktober 2026 di MariaDB:", flush=True)
    for r in oct_db:
        print(f"    {r['observation_date']}: {r['cnt']} stasiun", flush=True)

df_final = pd.read_parquet('data/raw/rainfall/final_rainfall_daily.parquet')
print(f"\nParquet Kanonikal final_rainfall_daily.parquet:", flush=True)
print(f"  Total Baris: {len(df_final):,}", flush=True)
print(f"  Jumlah Stasiun: {df_final['station_id'].nunique()}", flush=True)
print(f"  Rentang Tanggal: {str(df_final['date'].min())[:10]} s/d {str(df_final['date'].max())[:10]}", flush=True)

df_obs = pd.read_parquet('data/raw/rainfall/observation_daily.parquet')
print(f"\nParquet Kanonikal observation_daily.parquet:", flush=True)
print(f"  Total Baris: {len(df_obs):,}", flush=True)
print(f"  Jumlah Stasiun: {df_obs['station_id'].nunique()}", flush=True)
print(f"  Rentang Tanggal: {str(df_obs['date'].min())[:10]} s/d {str(df_obs['date'].max())[:10]}", flush=True)

ch_source_dir = 'scratch/inspect_ch'
ch_files = [
    'Kabupaten Dabo Singkep.xlsx',
    'Kabupaten Karimun.xlsx',
    'Kabupaten Natuna.xlsx',
    'Kabupaten Tarempa.xlsx',
    'Kota Batam.xlsx',
    'Kota Tanjungpinang.xlsx',
    'Pos Hujan Tanjungpinang Oktober IiI 2026.xlsx',
    'Entry Data Pos Hujan Bintan.xlsm'
]

print(f"\nAudit File Sumber Curah Hujan (Uji Ingestion Parser):", flush=True)
for fname in ch_files:
    fpath = os.path.join(ch_source_dir, fname)
    if not os.path.exists(fpath):
        continue
    sz = os.path.getsize(fpath)
    print(f"\n- File: {fname} ({sz:,} bytes)", flush=True)
    try:
        with open(fpath, 'rb') as fb:
            f_bytes = fb.read()
        res = parse_rainfall_excel(f_bytes, fname, target_date_limit="2026-10-01")
        summ = res['summary']
        print(f"  Parsed Entries (>= 2026-10-01): {summ['total_entries']}", flush=True)
        print(f"  Recognized Sheets ({len(summ['sheets_recognized'])}): {[s['sheet_name'] for s in summ['sheets_recognized']]}", flush=True)
        print(f"  Unrecognized Sheets ({len(summ['sheets_unrecognized'])}): {summ['sheets_unrecognized']}", flush=True)
        print(f"  New Records (NEW): {summ['total_new']}", flush=True)
        print(f"  Identical Records (IDENTICAL): {summ['total_identical']}", flush=True)
        print(f"  Updated/Conflict Records (UPDATED): {summ['total_updated']}", flush=True)
        print(f"  Missing (MISSING): {summ['total_missing']}", flush=True)
        print(f"  Damaged (DAMAGED): {summ['total_damaged']}", flush=True)
    except Exception as e:
        print(f"  Parser Exception: {e}", flush=True)

conn.close()
