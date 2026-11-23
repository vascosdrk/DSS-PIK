import pandas as pd
import os
import logging

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

file_chirps = os.path.join(base_dir, "final_rainfall_daily.parquet")
file_meta = os.path.join(base_dir, "station_metadata.parquet")
file_output = os.path.join(base_dir, "cews_integrated_2021_2025.parquet")

def prepare_cews_data():
    logging.info("Memuat data CHIRPS terkoreksi dan Metadata...")
    df_chirps = pd.read_parquet(file_chirps)
    df_meta = pd.read_parquet(file_meta)
    
    # 1. Filter Periode 2021 - 2025
    logging.info("Memfilter periode data (2021 - 2025)...")
    # Pastikan kolom date adalah datetime
    df_chirps['date'] = pd.to_datetime(df_chirps['date'])
    
    start_date = pd.to_datetime("2021-01-01")
    end_date = pd.to_datetime("2025-12-31")
    
    df_chirps_filtered = df_chirps[(df_chirps['date'] >= start_date) & (df_chirps['date'] <= end_date)].copy()
    logging.info(f"Sisa data setelah filter periode: {len(df_chirps_filtered)} baris.")

    # 2. Standarisasi station_id (Uppercase) pada Metadata
    logging.info("Menyesuaikan (uppercase) station_id pada metadata...")
    df_meta['station_id'] = df_meta['station_id'].str.upper()
    df_chirps_filtered['station_id'] = df_chirps_filtered['station_id'].str.upper()

    # 3. Penggabungan (Merge) Dataset
    logging.info("Menggabungkan data curah hujan dengan metadata spasial...")
    df_integrated = pd.merge(df_chirps_filtered, df_meta, on="station_id", how="left")
    
    # Cek stasiun yang tidak mendapat pasangan metadata
    missing_meta = df_integrated[df_integrated['latitude'].isnull()]['station_id'].unique()
    if len(missing_meta) > 0:
        logging.warning(f"Terdapat stasiun yang tidak memiliki metadata: {missing_meta}")
    else:
        logging.info("Semua stasiun berhasil dipetakan ke metadata!")

    # 4. Filter kolom-kolom yang relevan untuk Dashboard CEWS
    # Sesuaikan dengan kolom aktual yang ada dari hasil profiling
    cols_to_keep = [
        'station_id', 'station_name', 'date', 
        'latitude', 'longitude', 'elevation_m', 
        'region', 'province', 'regency', 
        'rainfall_mm', 'is_gap_filled', 'obs_status'
    ]
    
    # Ambil kolom yang benar-benar ada saja agar tidak error
    final_cols = [c for c in cols_to_keep if c in df_integrated.columns]
    df_final = df_integrated[final_cols]
    
    # 5. Simpan Hasil
    logging.info(f"Menyimpan dataset terintegrasi ke: {file_output}")
    df_final.to_parquet(file_output, index=False)
    logging.info(f"Berhasil! Dataset CEWS final memiliki {df_final.shape[0]} baris dan {df_final.shape[1]} kolom.")

if __name__ == "__main__":
    prepare_cews_data()
