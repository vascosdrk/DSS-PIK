import pandas as pd

hth = pd.read_parquet('hth_daily_2021_2025.parquet')
s_b = hth[(hth['station_id'] == '21040101B') & (hth['date'] >= '2025-12-20') & (hth['date'] <= '2025-12-31')][['date', 'rainfall_mm', 'hth_days', 'last_rain_date']]
s_a = hth[(hth['station_id'] == '21040101A') & (hth['date'] >= '2025-12-20') & (hth['date'] <= '2025-12-31')][['date', 'rainfall_mm', 'hth_days', 'last_rain_date']]

merged = pd.merge(s_b, s_a, on='date', suffixes=('_ARG_Singkep', '_Stamet_Dabo'))
pd.set_option('display.max_columns', None)
print(merged[['date', 'rainfall_mm_ARG_Singkep', 'hth_days_ARG_Singkep', 'rainfall_mm_Stamet_Dabo', 'hth_days_Stamet_Dabo']])

