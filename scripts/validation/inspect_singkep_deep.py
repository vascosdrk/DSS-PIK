import pandas as pd

sm = pd.read_parquet('station_metadata.parquet')
print("--- Searching 'Singkep' in station_metadata.parquet ---")
print(sm[sm['station_name'].str.contains('Singkep', case=False, na=False)][['station_id', 'station_name', 'regency', 'latitude', 'longitude']])

cw = pd.read_parquet('cews_current_warning.parquet')
print("\n--- Searching 'Singkep' in cews_current_warning.parquet ---")
print(cw[cw['station_name'].str.contains('Singkep', case=False, na=False)][['station_id', 'station_name', 'kabupaten', 'hth_days_current', 'warning_level', 'latitude', 'longitude']])

hth = pd.read_parquet('hth_daily_2021_2025.parquet')
singkep_hth = hth[hth['station_id'] == '21040101B'].sort_values('date', ascending=False)
print("\n--- Latest 10 days HTH in hth_daily_2021_2025 for 21040101B ---")
print(singkep_hth[['date', 'rainfall_mm', 'hth_days', 'last_rain_date', 'days_since_last_rain', 'hth_uncertain', 'is_missing']].head(10))
