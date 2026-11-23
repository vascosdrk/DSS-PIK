import pandas as pd
import numpy as np
import os

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

file_obs = os.path.join(base_dir, "observation_daily.parquet")
file_chirps = os.path.join(base_dir, "final_rainfall_daily.parquet")
file_meta = os.path.join(base_dir, "station_metadata.parquet")

report_path = os.path.join(base_dir, "audit_report.txt")

with open(report_path, "w", encoding="utf-8") as f:
    try:
        df_obs = pd.read_parquet(file_obs)
        df_chirps = pd.read_parquet(file_chirps)
        df_meta = pd.read_parquet(file_meta)
        
        f.write("=== A. Identifikasi File ===\n")
        f.write(f"- CH Observasi: {file_obs}\n")
        f.write(f"- CH Terkoreksi CHIRPS: {file_chirps}\n")
        f.write(f"- Metadata: {file_meta}\n\n")

        def profile(df, name):
            f.write(f"=== B. Data Profiling: {name} ===\n")
            f.write(f"Shape: {df.shape[0]} baris, {df.shape[1]} kolom\n")
            f.write(f"Kolom: {list(df.columns)}\n")
            f.write(f"Tipe Data:\n{df.dtypes.to_string()}\n")
            f.write(f"Sample:\n{df.head(5).to_string()}\n")
            f.write(f"Missing Values:\n{df.isnull().sum().to_string()}\n")
            f.write(f"Duplikasi Total: {df.duplicated().sum()}\n")
            
            # Identify columns
            date_col = next((c for c in df.columns if 'date' in c.lower() or 'tanggal' in c.lower() or 'time' in c.lower()), None)
            station_col = next((c for c in df.columns if 'station' in c.lower() or 'stasiun' in c.lower() or 'pos' in c.lower() or 'id' in c.lower()), None)
            rain_col = next((c for c in df.columns if 'rain' in c.lower() or 'ch' in c.lower() or 'obs' in c.lower() or 'val' in c.lower() or 'hujan' in c.lower()), None)
            
            if date_col:
                f.write(f"Rentang Tanggal ({date_col}): {df[date_col].min()} sd {df[date_col].max()}\n")
            if station_col:
                f.write(f"Stasiun Unik ({station_col}): {df[station_col].nunique()}\n")
            
            if name != "Metadata" and rain_col and pd.api.types.is_numeric_dtype(df[rain_col]):
                f.write(f"Statistik Curah Hujan ({rain_col}):\n{df[rain_col].describe().to_string()}\n")
                negatives = df[df[rain_col] < 0]
                if len(negatives) > 0:
                    f.write(f"NILAI NEGATIF DITEMUKAN: {len(negatives)} baris\n")
            f.write("\n")
            return date_col, station_col, rain_col

        date_obs, st_obs, r_obs = profile(df_obs, "CH Observasi")
        date_chrp, st_chrp, r_chrp = profile(df_chirps, "CH Terkoreksi CHIRPS")
        _, st_meta, _ = profile(df_meta, "Metadata")

        f.write("=== C. Identifikasi Key ===\n")
        f.write(f"Kolom Obs: {list(df_obs.columns)}\n")
        f.write(f"Kolom CHIRPS: {list(df_chirps.columns)}\n")
        f.write(f"Kolom Meta: {list(df_meta.columns)}\n")
        f.write(f"Irisan Obs & CHIRPS: {set(df_obs.columns).intersection(set(df_chirps.columns))}\n")
        f.write(f"Irisan Obs & Meta: {set(df_obs.columns).intersection(set(df_meta.columns))}\n\n")

        f.write("=== D. Pemeriksaan Temporal ===\n")
        if date_obs and st_obs:
            df_obs['date_parsed'] = pd.to_datetime(df_obs[date_obs])
            res = df_obs.groupby(st_obs)['date_parsed'].apply(lambda x: x.sort_values().diff().mode())
            f.write(f"Resolusi Waktu Dominan Obs:\n{res.head().to_string()}\n")
            dup_obs = df_obs.duplicated(subset=[st_obs, date_obs]).sum()
            f.write(f"Duplikasi station+date Obs: {dup_obs}\n")
            
        if date_chrp and st_chrp:
            df_chirps['date_parsed'] = pd.to_datetime(df_chirps[date_chrp])
            dup_chrp = df_chirps.duplicated(subset=[st_chrp, date_chrp]).sum()
            f.write(f"Duplikasi station+date CHIRPS: {dup_chrp}\n\n")

        f.write("=== E. Perbandingan CH ===\n")
        if st_obs and date_obs and st_chrp and date_chrp:
            # Asumsi nama kolom sama untuk merge
            if st_obs == st_chrp and date_obs == date_chrp:
                merged = pd.merge(df_obs, df_chirps, on=[st_obs, date_obs], suffixes=('_obs', '_chrp'))
                if not merged.empty:
                    # Cari kolom curah hujan di merged
                    r_o = r_obs + '_obs' if r_obs + '_obs' in merged.columns else r_obs
                    r_c = r_chrp + '_chrp' if r_chrp + '_chrp' in merged.columns else r_chrp
                    
                    merged['delta_ch'] = merged[r_c] - merged[r_o]
                    merged['abs_delta_ch'] = merged['delta_ch'].abs()
                    
                    f.write("Top 5 Perbedaan Terbesar:\n")
                    f.write(merged.sort_values('abs_delta_ch', ascending=False).head(5)[[st_obs, date_obs, r_o, r_c, 'delta_ch']].to_string() + "\n")
                    
                    stats = merged.groupby(st_obs).apply(lambda x: pd.Series({
                        'mean_obs': x[r_o].mean(),
                        'mean_chrp': x[r_c].mean(),
                        'mean_bias': x['delta_ch'].mean(),
                        'mae': x['abs_delta_ch'].mean(),
                        'corr': x[r_o].corr(x[r_c]) if len(x) > 1 else np.nan
                    }))
                    f.write("Statistik Perbandingan per Stasiun (Top 5):\n")
                    f.write(stats.head().to_string() + "\n\n")
                else:
                    f.write("Data tidak dapat di-join (kosong). Periksa kecocokan format value stasiun dan tanggal.\n\n")

        f.write("=== F. Integrasi Metadata Spasial ===\n")
        if st_obs and st_meta:
            obs_stations = set(df_obs[st_obs].unique())
            meta_stations = set(df_meta[st_meta].unique())
            missing_in_meta = obs_stations - meta_stations
            f.write(f"Stasiun di Obs yang tidak ada di Meta ({len(missing_in_meta)} stasiun): {missing_in_meta}\n")
            
        f.write("DONE\n")
    except Exception as e:
        f.write(f"ERROR: {e}\n")
