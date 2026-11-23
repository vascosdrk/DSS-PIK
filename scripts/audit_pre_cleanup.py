import os
import hashlib
import json
import pymysql

def hash_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

files = [
    'data/raw/rainfall/final_rainfall_daily.parquet',
    'data/raw/rainfall/observation_daily.parquet',
    'data/raw/spi/bulanan/SPI_monthly.parquet',
    'data/raw/spi/dasarian/SPI_all_30d.parquet',
    'data/raw/spi/dasarian/SPI_all_90d.parquet',
    'data/raw/spi/harian/SPI_all_30d.parquet',
    'data/raw/spi/harian/SPI_all_90d.parquet',
    'data/reference/stations/station_metadata.parquet',
    'data/reference/boundaries/kepri_kabkot.geojson',
    'data/reference/boundaries/kepri_kecamatan.geojson',
    'data/reference/boundaries/kepri_zom.geojson',
    'data/reference/map_templates/01. Peta Lampiran PDCI_Das II Jan 25.jpg',
    'data/reference/map_templates/04. Peta PDKM_Agustus II 26.jpg',
    'data/reference/PETA/KEPRI.shp',
    'data/reference/PETA/KEPRI.shx',
    'data/reference/PETA/KEPRI.dbf',
    'data/reference/PETA/KEPRI.prj',
]

results = {}
for f in files:
    if os.path.exists(f):
        results[f] = {'size': os.path.getsize(f), 'sha256': hash_file(f)}
        print(f"[OK] {f}: {results[f]['size']} bytes, SHA: {results[f]['sha256'][:16]}...")
    else:
        print(f"[MISSING] {f}")

os.makedirs('reports/maintenance', exist_ok=True)
with open('reports/maintenance/canonical_baseline_sha256.json', 'w') as out:
    json.dump(results, out, indent=2)

print("\n--- MariaDB Verification ---")
try:
    conn = pymysql.connect(
        host=os.environ.get("CEWS_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("CEWS_DB_PORT", 3306)),
        user=os.environ.get("CEWS_DB_USER", "root"),
        password=os.environ.get("CEWS_DB_PASSWORD", ""),
        database=os.environ.get("CEWS_DB_NAME", "cews_db"),
        cursorclass=pymysql.cursors.DictCursor
    )
    with conn.cursor() as cursor:
        tables = [
            "cews_rainfall_daily",
            "stations",
            "cews_period_snapshot",
            "cews_forecast_snapshot",
            "staging_rainfall_import"
        ]
        db_counts = {}
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {t}")
            cnt = cursor.fetchone()['cnt']
            db_counts[t] = cnt
            print(f"Table {t}: {cnt} rows")
        with open('reports/maintenance/canonical_db_counts.json', 'w') as out:
            json.dump(db_counts, out, indent=2)
    conn.close()
except Exception as e:
    print(f"DB Error: {e}")
