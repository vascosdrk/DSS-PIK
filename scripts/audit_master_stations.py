import pandas as pd
import pymysql

df_meta = pd.read_parquet('data/reference/stations/station_metadata.parquet')
print(f"Station Metadata Shape: {df_meta.shape}")
print(f"Columns: {list(df_meta.columns)}")
print(f"Total Stations: {len(df_meta)}")
if 'station_type' in df_meta.columns or 'type' in df_meta.columns:
    col = 'station_type' if 'station_type' in df_meta.columns else 'type'
    print("By Type:\n", df_meta[col].value_counts())
else:
    # check manual vs arg
    arg_mask = df_meta['station_name'].str.contains('ARG', case=False) | df_meta['station_id'].str.contains('ARG', case=False)
    print("ARG count:", arg_mask.sum())
    print("Manual/Pos count:", len(df_meta) - arg_mask.sum())
    print("ARG Stations:\n", df_meta[arg_mask][['station_id', 'station_name']])

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='', database='cews_db', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) as cnt, COUNT(DISTINCT station_id) as n_st FROM stations")
    print("\nDatabase 'stations' table:", cur.fetchone())
    cur.execute("SELECT station_id, station_name, kabupaten FROM stations WHERE station_name LIKE '%ARG%' OR station_id LIKE '%ARG%'")
    print("ARG in DB:", cur.fetchall())
conn.close()

