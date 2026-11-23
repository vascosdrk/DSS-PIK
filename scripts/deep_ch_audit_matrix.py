import os
import sys
sys.path.insert(0, '.')
import openpyxl
import pandas as pd
import pymysql
from backend.ingestion_service import parse_rainfall_excel, get_master_station_lookup

master_stations = get_master_station_lookup()

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', database='cews_db', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT station_id, MAX(observation_date) as max_date, COUNT(*) as cnt FROM cews_rainfall_daily GROUP BY station_id")
    db_station_stats = {r['station_id']: (str(r['max_date']), r['cnt']) for r in cur.fetchall()}
conn.close()

ch_files = [
    'Kota Batam.xlsx',
    'Kabupaten Tarempa.xlsx',
    'Kabupaten Karimun.xlsx',
    'Kabupaten Dabo Singkep.xlsx',
    'Kabupaten Natuna.xlsx',
    'Kota Tanjungpinang.xlsx',
]

results = {}

for f in ch_files:
    fp = os.path.join('scratch/inspect_ch', f)
    if not os.path.exists(fp):
        continue
    fbytes = open(fp, 'rb').read()
    try:
        res = parse_rainfall_excel(fbytes, f, target_date_limit='2026-10-01')
        summ = res['summary']
        results[f] = {
            'total_rows': summ['total_rows'],
            'recognized_sheets': len(summ['sheets_recognized']),
            'unrecognized_sheets': len(summ['sheets_unrecognized']),
            'stations': [s['station_id'] for s in summ['sheets_recognized']],
            'station_names': [s['sheet_name'] for s in summ['sheets_recognized']],
            'new_records': summ['total_new'],
            'identical_records': summ['total_identical'],
            'updated_records': summ['total_updated'],
            'missing_records': summ['total_missing'],
            'damaged_records': summ['total_damaged'],
            'date_range': summ['date_range'],
        }
    except Exception as e:
        results[f] = {'error': str(e)}

print("=== CH FILE AUDIT SUMMARY ===")
for f, info in results.items():
    print(f"\nFile: {f}")
    if 'error' in info:
        print(f"  Error: {info['error']}")
    else:
        print(f"  Stations Recognized: {info['recognized_sheets']} ({info['stations']})")
        print(f"  Date Range: {info['date_range']}")
        print(f"  NEW Records: {info['new_records']}")
        print(f"  IDENTICAL Records: {info['identical_records']}")
        print(f"  UPDATED Records: {info['updated_records']}")
        print(f"  MISSING Records: {info['missing_records']}")
        print(f"  DAMAGED Records: {info['damaged_records']}")

