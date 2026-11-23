import pandas as pd
import os

files = [
    'station_metadata.parquet',
    'cews_current_warning.parquet',
    'hth_daily.parquet',
    'hth_daily_2021_2025.parquet',
    'final_rainfall_daily.parquet',
    'observation_daily.parquet',
    'cews_indicator_dataset.parquet',
]

for f in files:
    if os.path.exists(f):
        try:
            df = pd.read_parquet(f)
            print(f"=== {f} ===")
            print(f"Shape: {df.shape}")
            print(f"Columns: {list(df.columns)}")
            if 'station_id' in df.columns:
                unique_stns = df['station_id'].nunique()
                print(f"Unique stations: {unique_stns}")
                has_singkep = '21040101B' in df['station_id'].unique()
                print(f"Contains 21040101B (Singkep): {has_singkep}")
            print()
        except Exception as e:
            print(f"Error reading {f}: {e}")

