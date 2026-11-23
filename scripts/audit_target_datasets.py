import os
import pymysql
import pandas as pd
import openpyxl
from datetime import datetime

print("=== 1. AUDIT CURAH HUJAN (CH) ===")
# MariaDB check
conn = pymysql.connect(
    host=os.environ.get("CEWS_DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("CEWS_DB_PORT", 3306)),
    user=os.environ.get("CEWS_DB_USER", "root"),
    password=os.environ.get("CEWS_DB_PASSWORD", ""),
    database=os.environ.get("CEWS_DB_NAME", "cews_db"),
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    cur.execute("SELECT MIN(observation_date) as min_date, MAX(observation_date) as max_date, COUNT(*) as cnt, COUNT(DISTINCT station_id) as n_stations FROM cews_rainfall_daily")
    ch_db = cur.fetchone()
    print("Database cews_rainfall_daily:")
    print(f"  Rows: {ch_db['cnt']}, Stations: {ch_db['n_stations']}, Range: {ch_db['min_date']} to {ch_db['max_date']}")

    cur.execute("SELECT observation_date, COUNT(*) as cnt FROM cews_rainfall_daily GROUP BY observation_date ORDER BY observation_date DESC LIMIT 10")
    print("  Latest 10 observation_dates in DB:")
    for r in cur.fetchall():
        print(f"    {r['observation_date']}: {r['cnt']} stations")

# Parquet check
final_rf = pd.read_parquet('data/raw/rainfall/final_rainfall_daily.parquet')
print("\nParquet final_rainfall_daily.parquet:")
print(f"  Shape: {final_rf.shape}, Columns: {list(final_rf.columns)}")
date_col = 'observation_date' if 'observation_date' in final_rf.columns else 'date'
if date_col in final_rf.columns:
    print(f"  Range: {final_rf[date_col].min()} to {final_rf[date_col].max()}, Stations: {final_rf['station_id'].nunique()}")

obs_rf = pd.read_parquet('data/raw/rainfall/observation_daily.parquet')
print("\nParquet observation_daily.parquet:")
print(f"  Shape: {obs_rf.shape}, Columns: {list(obs_rf.columns)}")
date_col = 'observation_date' if 'observation_date' in obs_rf.columns else 'date'
if date_col in obs_rf.columns:
    print(f"  Range: {obs_rf[date_col].min()} to {obs_rf[date_col].max()}, Stations: {obs_rf['station_id'].nunique()}")

print("\n=== 2. AUDIT SPI ===")
spi_das_30 = pd.read_parquet('data/raw/spi/dasarian/SPI_all_30d.parquet')
print("SPI Dasarian 30D (data/raw/spi/dasarian/SPI_all_30d.parquet):")
print(f"  Shape: {spi_das_30.shape}, Columns: {list(spi_das_30.columns)[:10]}...")
print("  Index type:", type(spi_das_30.index), "Index name:", spi_das_30.index.name)
print(f"  Index Range: {spi_das_30.index.min()} to {spi_das_30.index.max()}")
print("  Columns count (stations):", len(spi_das_30.columns))

spi_das_90 = pd.read_parquet('data/raw/spi/dasarian/SPI_all_90d.parquet')
print("\nSPI Dasarian 90D:")
print(f"  Shape: {spi_das_90.shape}, Index Range: {spi_das_90.index.min()} to {spi_das_90.index.max()}")

spi_mon = pd.read_parquet('data/raw/spi/bulanan/SPI_monthly.parquet')
print("\nSPI Monthly:")
print(f"  Shape: {spi_mon.shape}, Index Range: {spi_mon.index.min()} to {spi_mon.index.max()}")

print("\n=== 3. AUDIT ECMWF FORECAST ===")
with conn.cursor() as cur:
    cur.execute("""
        SELECT target_year, target_month, target_dasarian, issue_date, source_file, COUNT(*) as cnt 
        FROM cews_forecast_snapshot 
        GROUP BY target_year, target_month, target_dasarian, issue_date, source_file 
        ORDER BY target_year DESC, target_month DESC, target_dasarian DESC, issue_date DESC 
        LIMIT 15
    """)
    print("Stored in cews_forecast_snapshot:")
    for r in cur.fetchall():
        print(f"  Target: {r['target_year']}-{r['target_month']:02d}-D{r['target_dasarian']} | Issue: {r['issue_date']} | File: {r['source_file']} | Rows: {r['cnt']}")

conn.close()
