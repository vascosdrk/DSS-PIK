import pandas as pd
import os

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

def print_cols(fname):
    p = os.path.join(base_dir, fname)
    if os.path.exists(p):
        df = pd.read_parquet(p)
        print(f"--- {fname} ---")
        print(df.columns.tolist())
        if 'threshold_mm' in df.columns:
            print("Thresholds:", df['threshold_mm'].unique())
    else:
        print(f"NOT FOUND: {p}")

print_cols("hth_daily_2021_2025.parquet")
print_cols("spi_cews_2021_2025.parquet")
print_cols("probability_rainfall_dasarian_2025.parquet")
print_cols("probability_rainfall_monthly_2021_2025.parquet")
