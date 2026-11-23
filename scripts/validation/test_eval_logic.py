import pandas as pd
import numpy as np

# Load hth_daily_2021_2025
hth_df = pd.read_parquet('hth_daily_2021_2025.parquet')
cw_df = pd.read_parquet('cews_current_warning.parquet')

# Precompute latest date records
latest_date = '2025-12-31'
hth_latest = hth_df[hth_df['date'] == latest_date].set_index('station_id')

def get_evaluation(station_id):
    # Lookup in current_warning
    cw_rows = cw_df[cw_df['station_id'] == station_id]
    if len(cw_rows) == 0:
        return None
    stn_cw = cw_rows.iloc[0]
    
    # Lookup in pipeline HTH
    has_pipeline = station_id in hth_latest.index
    pipe_row = hth_latest.loc[station_id] if has_pipeline else None
    
    pipe_hth = int(pipe_row['hth_days']) if has_pipeline and pd.notnull(pipe_row['hth_days']) else None
    last_rain = str(pipe_row['last_rain_date'])[:10] if has_pipeline and pd.notnull(pipe_row['last_rain_date']) else None
    
    # Recent 30 days rainfall observations (2025-12-02 to 2025-12-31)
    stn_history = hth_df[(hth_df['station_id'] == station_id) & (hth_df['date'] >= '2025-12-01') & (hth_df['date'] <= latest_date)].sort_values('date')
    missing_days = int(stn_history['is_missing'].sum()) if len(stn_history) > 0 else 0
    
    # Recent rainfall series (last 30 days)
    recent_rainfall = []
    for _, r in stn_history.iterrows():
        recent_rainfall.append({
            'date': str(r['date'])[:10],
            'rainfall_mm': float(r['rainfall_mm']) if pd.notnull(r['rainfall_mm']) else 0.0,
            'is_missing': bool(r['is_missing']),
            'hth_days': int(r['hth_days']) if pd.notnull(r['hth_days']) else 0
        })
    
    # Evaluation status logic
    reasons = []
    if not has_pipeline:
        eval_status = "INSUFFICIENT_DATA"
        reasons.append("Data pipeline HTH tidak ditemukan untuk stasiun ini.")
    else:
        # Check HTH consistency between Decision Engine and Pipeline
        if pipe_hth == stn_cw['hth_days_current']:
            reasons.append(f"Nilai HTH Decision Engine ({stn_cw['hth_days_current']} hari) identik dengan HTH pipeline harian ({pipe_hth} hari).")
            if missing_days == 0:
                reasons.append("Tidak ditemukan missing data observasi pada deret 30 hari terakhir.")
            else:
                reasons.append(f"Terdapat {missing_days} hari observasi missing dalam 30 hari terakhir.")
            eval_status = "CONSISTENT"
        else:
            reasons.append(f"Ketidaksesuaian nilai: HTH Engine={stn_cw['hth_days_current']} hari vs HTH Pipeline={pipe_hth} hari.")
            eval_status = "REVIEW_REQUIRED"

    # Haversine nearest stations (3-5 stations)
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        p1, p2 = np.radians(lat1), np.radians(lat2)
        dp = np.radians(lat2 - lat1)
        dl = np.radians(lon2 - lon1)
        a = np.sin(dp/2.0)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2.0)**2
        return 2.0 * R * np.arcsin(np.sqrt(a))
    
    lat = float(stn_cw['latitude'])
    lon = float(stn_cw['longitude'])
    
    cw_df['distance_km'] = haversine(lat, lon, cw_df['latitude'], cw_df['longitude'])
    neighbors = cw_df[cw_df['station_id'] != station_id].sort_values('distance_km').head(5)
    
    nearest_list = []
    for _, n in neighbors.iterrows():
        n_id = n['station_id']
        n_last_rain = None
        if n_id in hth_latest.index:
            n_lr = hth_latest.loc[n_id]['last_rain_date']
            if pd.notnull(n_lr):
                n_last_rain = str(n_lr)[:10]
        
        nearest_list.append({
            'station_id': n_id,
            'station_name': n['station_name'],
            'kabupaten': n['kabupaten'],
            'distance_km': round(float(n['distance_km']), 2),
            'hth_days_current': int(n['hth_days_current']) if pd.notnull(n['hth_days_current']) else None,
            'warning_level': n['warning_level'],
            'hazard_type': n['hazard_type'],
            'data_quality_status': n['data_quality_status'],
            'last_rain_date': n_last_rain
        })
        
    return {
        'station': {
            'station_id': station_id,
            'station_name': stn_cw['station_name'],
            'kabupaten': stn_cw['kabupaten'],
            'latitude': lat,
            'longitude': lon
        },
        'current_state': {
            'warning_level': stn_cw['warning_level'],
            'hazard_type': stn_cw['hazard_type'],
            'hth_days_current': int(stn_cw['hth_days_current']),
            'hth_uncertain': bool(stn_cw['hth_uncertain']),
            'data_quality_status': stn_cw['data_quality_status'],
            'confidence_level': stn_cw['confidence_level'],
            'last_observation_date': str(stn_cw['last_observation_date'])
        },
        'observation_diagnostics': {
            'latest_hth_pipeline_value': pipe_hth,
            'last_rain_date': last_rain,
            'missing_observation_days': missing_days,
            'source_available': True,
            'recent_rainfall': recent_rainfall
        },
        'evaluation': {
            'status': eval_status,
            'reasons': reasons
        },
        'nearest_stations': nearest_list
    }

# Test with 21040101B
eval_singkep = get_evaluation('21040101B')
print("Status:", eval_singkep['evaluation']['status'])
print("Reasons:", eval_singkep['evaluation']['reasons'])
print("Nearest stations:")
for n in eval_singkep['nearest_stations']:
    print(f"  - {n['station_name']} ({n['distance_km']} km): HTH={n['hth_days_current']} ({n['warning_level']}), Last Rain={n['last_rain_date']}")
