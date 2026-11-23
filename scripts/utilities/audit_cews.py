import pandas as pd
import numpy as np
import os
import json

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
files = [f for f in os.listdir(base_dir) if f.endswith('.parquet')]

results = {}

for f in files:
    filepath = os.path.join(base_dir, f)
    try:
        df = pd.read_parquet(filepath)
        f_res = {
            "rows": len(df),
            "cols": len(df.columns),
            "columns": {str(c): str(df[c].dtype) for c in df.columns},
            "sample": df.head(2).to_dict(orient='records')
        }
        
        # Temporal
        date_cols = [c for c in df.columns if 'date' in c.lower() or c == 'waktu']
        if date_cols and np.issubdtype(df[date_cols[0]].dtype, np.datetime64):
            dc = date_cols[0]
            f_res['temporal'] = {
                "col": dc,
                "min": str(df[dc].min()),
                "max": str(df[dc].max()),
                "dups": int(df.duplicated(subset=['station_id', dc]).sum()) if 'station_id' in df.columns else 0
            }
        
        # Spatial
        if 'station_id' in df.columns:
            f_res['spatial'] = {
                "unique_stations": int(df['station_id'].nunique())
            }
            if 'latitude' in df.columns and 'longitude' in df.columns:
                f_res['spatial']['null_coords'] = int(df['latitude'].isna().sum() + df['longitude'].isna().sum())
        
        # HTH Validation if present
        if f in ['hth_daily_2021_2025.parquet', 'hth_daily.parquet']:
            hth_res = {}
            if 'rainfall_mm' in df.columns and 'hth_days' in df.columns:
                hth_res['negative_hth'] = int((df['hth_days'] < 0).sum())
                hth_res['rain_but_hth_not_0'] = int(((df['rainfall_mm'] >= 1.0) & (df['hth_days'] > 0)).sum())
                hth_res['dry_but_hth_0'] = int(((df['rainfall_mm'] < 1.0) & (df['hth_days'] == 0)).sum())
                
                # Missing validation
                if 'is_missing' in df.columns and 'hth_valid' in df.columns:
                    missing_mask = (df['is_missing'] == True) | df['rainfall_mm'].isna()
                    hth_res['missing_but_valid'] = int((missing_mask & (df['hth_valid'] == True)).sum())
            if 'hth_status' in df.columns:
                err_normal = int(((df['hth_days'] >= 0) & (df['hth_days'] <= 20) & (df['hth_status'] != 'NORMAL')).sum())
                err_waspada = int(((df['hth_days'] >= 21) & (df['hth_days'] <= 30) & (df['hth_status'] != 'WASPADA')).sum())
                err_siaga = int(((df['hth_days'] >= 31) & (df['hth_days'] <= 60) & (df['hth_status'] != 'SIAGA')).sum())
                err_awas = int(((df['hth_days'] >= 61) & (df['hth_status'] != 'AWAS')).sum())
                hth_res['status_errors'] = {"normal": err_normal, "waspada": err_waspada, "siaga": err_siaga, "awas": err_awas}
            f_res['hth_validation'] = hth_res
            
        results[f] = f_res
    except Exception as e:
        results[f] = {"error": str(e)}

# Cross validation HTH vs SPI
cv = {}
if 'hth_daily_2021_2025.parquet' in files and 'spi_cews_2021_2025.parquet' in files:
    try:
        hth = pd.read_parquet(os.path.join(base_dir, 'hth_daily_2021_2025.parquet'))
        spi = pd.read_parquet(os.path.join(base_dir, 'spi_cews_2021_2025.parquet'))
        if 'year' in hth.columns and 'month' in hth.columns:
            hth_agg = hth.groupby(['station_id', 'year', 'month'])['hth_days'].max().reset_index()
            # assume spi has year, month, spi_1 or something
            if 'year' in spi.columns and 'month' in spi.columns and 'spi_1' in spi.columns:
                merged = hth_agg.merge(spi, on=['station_id', 'year', 'month'], how='inner')
                anomaly = merged[(merged['hth_days'] > 30) & (merged['spi_1'] > 0)]
                cv['hth_gt_30_spi_positive'] = int(len(anomaly))
                cv['sample'] = anomaly[['station_id', 'year', 'month', 'hth_days', 'spi_1']].head(3).to_dict('records') if len(anomaly) > 0 else []
    except Exception as e:
        cv['error'] = str(e)
        
results['cross_validation'] = cv

with open(os.path.join(base_dir, "audit_results.json"), "w") as f:
    json.dump(results, f, indent=2)
