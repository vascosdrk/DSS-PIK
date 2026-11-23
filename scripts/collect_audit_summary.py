import os
import sys
sys.path.insert(0, '.')
import pymysql
import pandas as pd
from datetime import datetime

from backend.ingestion_service import get_master_station_lookup

master = get_master_station_lookup()

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', database='cews_db', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT station_id, MIN(observation_date) as min_d, MAX(observation_date) as max_d, COUNT(*) as cnt FROM cews_rainfall_daily GROUP BY station_id")
    ch_db_stats = {r['station_id']: r for r in cur.fetchall()}
    
    # Check forecast snapshot
    cur.execute("""
        SELECT target_year, target_month, target_dasarian, issue_date, source_file, COUNT(*) as cnt 
        FROM cews_forecast_snapshot 
        WHERE (target_year = 2026 AND target_month >= 9) OR target_year > 2026
        GROUP BY target_year, target_month, target_dasarian, issue_date, source_file
        ORDER BY target_year DESC, target_month DESC, target_dasarian DESC, issue_date DESC
    """)
    fc_db_stats = cur.fetchall()
conn.close()

# SPI status
spi_30d = pd.read_parquet('data/raw/spi/dasarian/SPI_all_30d.parquet')
spi_90d = pd.read_parquet('data/raw/spi/dasarian/SPI_all_90d.parquet')
spi_mon = pd.read_parquet('data/raw/spi/bulanan/SPI_monthly.parquet')

print("Summary counts collected.")
print(f"Master stations: {len(master)}")
print(f"SPI 30D max date: {spi_30d.index.max()}, shape: {spi_30d.shape}")
print(f"SPI 90D max date: {spi_90d.index.max()}, shape: {spi_90d.shape}")
print(f"SPI Monthly max date: {spi_mon.index.max()}, shape: {spi_mon.shape}")
print("Forecast snapshot rows for >= Sep 2026:", len(fc_db_stats))

