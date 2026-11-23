import pandas as pd
import numpy as np
import os
import logging
import traceback

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

f_int = os.path.join(base_dir, "cews_integrated_2021_2025.parquet")
f_chirps = os.path.join(base_dir, "final_rainfall_daily.parquet")
f_meta = os.path.join(base_dir, "station_metadata.parquet")
f_out = os.path.join(base_dir, "hth_daily_2021_2025.parquet")
f_qc = os.path.join(base_dir, "hth_qc_report.txt")
f_err = os.path.join(base_dir, "hth_error.txt")

def calc_hth_vectorized(group):
    group = group.sort_values('date')
    n = len(group)
    
    hth_days = np.full(n, np.nan)
    hth_valid = np.full(n, True, dtype=bool)
    hth_uncertain = np.full(n, False, dtype=bool)
    last_rain = np.empty(n, dtype='datetime64[ns]')
    last_rain.fill(np.datetime64('NaT'))
    days_since_rain = np.full(n, np.nan)
    hth_source_list = [""] * n
    
    current_hth = 0
    uncertain = False
    last_rain_d = np.datetime64('NaT')
    current_sources = set()
    
    for i in range(n):
        row = group.iloc[i]
        r = row['rainfall_mm']
        is_miss = pd.isna(r) or row.get('is_missing', False)
        
        is_gf = row.get('is_gap_filled', False)
        if pd.isna(is_gf): is_gf = False
        
        source_val = "MISSING" if is_miss else ( "GAP_FILLED" if is_gf else "OBSERVED" )
        
        if is_miss:
            uncertain = True
            current_hth += 1
            hth_valid[i] = False
            hth_uncertain[i] = True
            hth_days[i] = np.nan
            dsr = np.nan if np.isnat(last_rain_d) else (row['date'] - pd.Timestamp(last_rain_d)).days
            days_since_rain[i] = dsr
            last_rain[i] = last_rain_d
            current_sources.add("MISSING")
            hth_source_list[i] = "MISSING"
        elif r >= 1.0:
            uncertain = False
            current_hth = 0
            last_rain_d = np.datetime64(row['date'])
            current_sources = {source_val}
            hth_valid[i] = True
            hth_uncertain[i] = False
            hth_days[i] = 0
            days_since_rain[i] = 0
            last_rain[i] = last_rain_d
            hth_source_list[i] = source_val
        else:
            current_hth += 1
            hth_valid[i] = True
            hth_uncertain[i] = uncertain
            hth_days[i] = current_hth
            dsr = np.nan if np.isnat(last_rain_d) else (row['date'] - pd.Timestamp(last_rain_d)).days
            days_since_rain[i] = dsr
            last_rain[i] = last_rain_d
            current_sources.add(source_val)
            
            if "MISSING" in current_sources:
                hth_source_list[i] = "MISSING"
            elif "GAP_FILLED" in current_sources and "OBSERVED" in current_sources:
                hth_source_list[i] = "MIXED"
            elif "GAP_FILLED" in current_sources:
                hth_source_list[i] = "GAP_FILLED"
            else:
                hth_source_list[i] = "OBSERVED"
                
    group['hth_days'] = hth_days
    group['hth_valid'] = hth_valid
    group['hth_uncertain'] = hth_uncertain
    group['last_rain_date'] = last_rain
    group['days_since_last_rain'] = days_since_rain
    group['hth_source'] = hth_source_list
    return group

def classify_hth(h):
    if pd.isna(h): return "UNKNOWN"
    if h <= 20: return "NORMAL"
    if h <= 30: return "WASPADA"
    if h <= 60: return "SIAGA"
    return "AWAS"

def color_hth(s):
    return {"NORMAL":"GREEN", "WASPADA":"YELLOW", "SIAGA":"ORANGE", "AWAS":"RED"}.get(s, "GREY")

def main():
    try:
        logging.info("Memuat data CEWS integrated...")
        df = pd.read_parquet(f_int)

        with open(f_qc, "w", encoding='utf-8') as f:
            f.write("=== 1. Audit Struktur File Input ===\n")
            f.write(f"Baris: {len(df)}, Kolom: {len(df.columns)}\n")
            f.write(f"Stasiun Unik: {df['station_id'].nunique()}\n")
            f.write(f"Rentang Tanggal: {df['date'].min()} sd {df['date'].max()}\n")
            f.write(f"Duplikasi (station_id+date): {df.duplicated(subset=['station_id', 'date']).sum()}\n\n")
            
        cols_needed = ['rainfall_source', 'data_quality', 'is_observed', 'is_gap_filled', 'is_missing', 'operational_source', 'calibration_method', 'calibration_level', 'obs_status']
        missing_cols = [c for c in cols_needed if c not in df.columns]

        if missing_cols:
            logging.info("Mengembalikan kolom provenance asal yang hilang dari file final_rainfall...")
            df_chirps = pd.read_parquet(f_chirps)
            df_chirps['station_id'] = df_chirps['station_id'].str.upper()
            df_chirps['date'] = pd.to_datetime(df_chirps['date'])
            missing_cols_safe = [c for c in missing_cols if c in df_chirps.columns]
            df = df.merge(df_chirps[['station_id', 'date'] + missing_cols_safe], on=['station_id', 'date'], how='left')

        if 'NOZOM_PROV' not in df.columns:
            df_meta = pd.read_parquet(f_meta)
            df_meta['station_id'] = df_meta['station_id'].str.upper()
            df = df.merge(df_meta[['station_id', 'NOZOM_PROV']], on='station_id', how='left')

        df['station_id'] = df['station_id'].str.upper()
        df['date'] = pd.to_datetime(df['date'])

        logging.info("Menghitung HTH berdasarkan BMKG No 9 Tahun 2019...")
        df = df.groupby('station_id', group_keys=False).apply(calc_hth_vectorized)

        logging.info("Membangun kolom penunjang (year, month, dasarian)...")
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        df['day'] = df['date'].dt.day
        df['dasarian'] = df['day'].apply(lambda d: 1 if d <= 10 else (2 if d <= 20 else 3))
        df['dry_day'] = df['rainfall_mm'].apply(lambda x: True if pd.notna(x) and x < 1.0 else (False if pd.notna(x) and x >= 1.0 else np.nan))

        df['hth_status'] = df['hth_days'].apply(classify_hth)
        df['warning_color'] = df['hth_status'].apply(color_hth)

        final_cols = [
            'station_id', 'station_name', 'date', 'region', 'province', 'regency', 
            'latitude', 'longitude', 'elevation_m', 'NOZOM_PROV',
            'rainfall_mm', 'rainfall_source', 'data_quality', 'is_observed', 
            'is_gap_filled', 'is_missing', 'operational_source', 'calibration_method', 
            'calibration_level', 'obs_status',
            'dry_day', 'hth_days', 'hth_status', 'warning_color', 'last_rain_date', 
            'days_since_last_rain', 'hth_valid', 'hth_uncertain', 'hth_source',
            'year', 'month', 'day', 'dasarian'
        ]

        for c in final_cols:
            if c not in df.columns:
                df[c] = np.nan
                
        df = df[final_cols]

        logging.info("Menyimpan dataset HTH final...")
        df.to_parquet(f_out, index=False, compression='snappy')

        logging.info("Menjalankan Quality Control...")
        with open(f_qc, "a", encoding='utf-8') as f:
            f.write("=== 12. Quality Control ===\n")
            f.write(f"Jumlah stasiun output: {df['station_id'].nunique()}\n")
            f.write(f"Rentang tanggal output: {df['date'].min()} sd {df['date'].max()}\n")
            f.write(f"Duplikasi station+date: {df.duplicated(subset=['station_id', 'date']).sum()}\n")
            
            neg_hth = df[df['hth_days'] < 0]
            f.write(f"HTH < 0: {len(neg_hth)}\n")
            
            rain_hth = df[(df['rainfall_mm'] >= 1) & (df['hth_days'] != 0)]
            f.write(f"Rain >= 1 tapi HTH != 0: {len(rain_hth)}\n")
            
            err_awas = df[(df['hth_days'] >= 61) & (df['hth_status'] != 'AWAS')]
            err_siaga = df[(df['hth_days'] >= 31) & (df['hth_days'] <= 60) & (df['hth_status'] != 'SIAGA')]
            err_waspada = df[(df['hth_days'] >= 21) & (df['hth_days'] <= 30) & (df['hth_status'] != 'WASPADA')]
            f.write(f"Error status AWAS: {len(err_awas)}\n")
            f.write(f"Error status SIAGA: {len(err_siaga)}\n")
            f.write(f"Error status WASPADA: {len(err_waspada)}\n")
            
            f.write("\nContoh Transisi Reset HTH:\n")
            resets = df[(df['rainfall_mm'] >= 1.0) & (df['date'] > df['date'].min())].head(20)
            f.write(resets[['station_id', 'date', 'rainfall_mm', 'hth_days', 'hth_status']].to_string() + "\n")
            
            f.write("\nContoh Periode Gap-Filled:\n")
            gf = df[df['is_gap_filled'] == True].head(20)
            if not gf.empty:
                f.write(gf[['station_id', 'date', 'rainfall_mm', 'hth_days', 'hth_source']].to_string() + "\n")
            else:
                f.write("Tidak ada gap-filled data dalam rentang waktu ini.\n")
                
            f.write("\nContoh Periode Missing:\n")
            miss = df[df['is_missing'] == True].head(20)
            if not miss.empty:
                f.write(miss[['station_id', 'date', 'rainfall_mm', 'hth_valid', 'hth_uncertain', 'hth_days']].to_string() + "\n")
            else:
                f.write("Tidak ada missing data dalam rentang waktu ini.\n")
                
            f.write("\n=== 13. Ringkasan Hasil ===\n")
            f.write(f"Jumlah Record: {len(df)}\n")
            f.write(f"Jumlah Stasiun: {df['station_id'].nunique()}\n")
            f.write(f"Hari NORMAL: {len(df[df['hth_status'] == 'NORMAL'])}\n")
            f.write(f"Hari WASPADA: {len(df[df['hth_status'] == 'WASPADA'])}\n")
            f.write(f"Hari SIAGA: {len(df[df['hth_status'] == 'SIAGA'])}\n")
            f.write(f"Hari AWAS: {len(df[df['hth_status'] == 'AWAS'])}\n")
            
            max_hth = df.groupby('station_name')['hth_days'].max()
            f.write(f"\nHTH Maksimum per stasiun (Top 5):\n{max_hth.sort_values(ascending=False).head(5).to_string()}\n")
            
            f.write(f"\nRecord dengan Gap-Filled HTH Source: {len(df[df['hth_source'].isin(['GAP_FILLED', 'MIXED'])])}\n")
            f.write(f"Record HTH Uncertain: {len(df[df['hth_uncertain'] == True])}\n")
            
            def station_summary(g):
                max_hth_val = g['hth_days'].max()
                if pd.isna(max_hth_val):
                    max_date = pd.NaT
                else:
                    max_date = g.loc[g['hth_days'].idxmax(), 'date']
                    
                return pd.Series({
                    'max_hth': max_hth_val,
                    'max_hth_date': max_date,
                    'total_waspada_days': (g['hth_status'] == 'WASPADA').sum(),
                    'total_siaga_days': (g['hth_status'] == 'SIAGA').sum(),
                    'total_awas_days': (g['hth_status'] == 'AWAS').sum(),
                    'gap_filled_percentage': (g['is_gap_filled'] == True).sum() / len(g) * 100,
                    'uncertain_hth_days': g['hth_uncertain'].sum()
                })
            summary_df = df.groupby(['station_id', 'station_name']).apply(station_summary).reset_index()
            f.write("\nRingkasan per stasiun:\n")
            f.write(summary_df.to_string() + "\n")

        logging.info("Selesai!")

    except Exception as e:
        import traceback
        logging.error(f"Error occurred: {e}")
        with open(f_err, "w", encoding='utf-8') as fe:
            fe.write(traceback.format_exc())

if __name__ == "__main__":
    main()
