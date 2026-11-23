import pandas as pd
import numpy as np

hth = pd.read_parquet('hth_daily_2021_2025.parquet')
singkep_hth = hth[hth['station_id'] == '21040101B'].sort_values('date', ascending=False)
latest_singkep = singkep_hth.iloc[0]
print("=== Latest HTH record for 21040101B (ARG Singkep) ===")
for col in ['station_id', 'station_name', 'date', 'rainfall_mm', 'hth_days', 'last_rain_date', 'days_since_last_rain', 'hth_valid', 'hth_uncertain', 'is_missing']:
    print(f"  {col}: {latest_singkep[col]}")

print("\n=== Observations for 21040101B in December 2025 ===")
dec_obs = singkep_hth[(singkep_hth['date'] >= '2025-12-01') & (singkep_hth['date'] <= '2025-12-31')].sort_values('date')
print(dec_obs[['date', 'rainfall_mm', 'hth_days', 'last_rain_date', 'is_missing', 'is_observed']])

# Also check Stamet Dabo Singkep (21040101A)
dabo_hth = hth[hth['station_id'] == '21040101A'].sort_values('date', ascending=False)
if len(dabo_hth) > 0:
    latest_dabo = dabo_hth.iloc[0]
    print("\n=== Latest HTH record for 21040101A (Stamet Dabo Singkep) ===")
    for col in ['station_id', 'station_name', 'date', 'rainfall_mm', 'hth_days', 'last_rain_date', 'days_since_last_rain', 'hth_valid', 'hth_uncertain', 'is_missing']:
        print(f"  {col}: {latest_dabo[col]}")

# Nearest stations to ARG Singkep (-0.486056, 104.571937)
cw = pd.read_parquet('cews_current_warning.parquet')
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi/2.0)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2.0)**2
    return 2.0 * R * np.arcsin(np.sqrt(a))

cw['dist_km'] = haversine(-0.486056, 104.571937, cw['latitude'], cw['longitude'])
nearest = cw[cw['station_id'] != '21040101B'].sort_values('dist_km').head(5)
print("\n=== Nearest 5 Stations to ARG Singkep ===")
print(nearest[['station_id', 'station_name', 'kabupaten', 'dist_km', 'hth_days_current', 'warning_level', 'data_quality_status']])
