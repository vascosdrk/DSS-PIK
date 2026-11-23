import os
import pandas as pd
import numpy as np
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROB_FILE = os.path.join(BASE_DIR, "probability_rainfall_dasarian_2025.parquet")
MASTER_FILE = os.path.join(BASE_DIR, "station_metadata.parquet")
HTH_FILE = os.path.join(BASE_DIR, "hth_monthly_snapshot_2021_2025.parquet")
SPI_FILE = os.path.join(BASE_DIR, "spi_cews_2021_2025.parquet")
OUT_REPORT = os.path.join(BASE_DIR, "probability_cews_qc_report_2025.txt")

def haversine(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2): return np.nan
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1-a))

def main():
    with open(OUT_REPORT, "w", encoding="utf-8") as rep:
        rep.write("=== PROBABILITY CEWS QC REPORT 2025 ===\n")
        
        # 1. AUDIT STRUKTUR DATA
        rep.write("\n=== 1. AUDIT STRUKTUR DATA ===\n")
        if not os.path.exists(PROB_FILE):
            rep.write(f"ERROR: {PROB_FILE} tidak ditemukan!\n")
            return
            
        df = pd.read_parquet(PROB_FILE)
        rep.write(f"Jumlah baris: {len(df)}\n")
        rep.write(f"Jumlah kolom: {len(df.columns)}\n")
        rep.write(f"Daftar kolom:\n{df.columns.tolist()}\n")
        rep.write(f"Tipe data:\n{df.dtypes.to_string()}\n")
        
        required_cols = ['station_id', 'station_name', 'latitude', 'longitude', 'province', 'kabupaten', 
                         'issue_date', 'target_start_date', 'target_end_date', 'target_year', 'target_month', 
                         'target_dasarian', 'probability_type', 'threshold_mm', 'probability_percent', 
                         'source_file', 'source_sheet']
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            rep.write(f"MISSING COLUMNS: {missing_cols}\n")
        else:
            rep.write("Semua kolom wajib (17 kolom) TERSEDIA.\n")
            
        rep.write("\nSample 10 baris:\n")
        rep.write(df[required_cols[:10]].head(10).to_string() + "\n")
        
        # 2. VALIDASI PERIODE DASARIAN
        rep.write("\n=== 2. VALIDASI PERIODE DASARIAN ===\n")
        invalid_dasarian = df[~df['target_dasarian'].isin([1, 2, 3])]
        rep.write(f"Jumlah Dasarian Invalid (bukan 1,2,3): {len(invalid_dasarian)}\n")
        
        df['issue_to_target_days'] = (pd.to_datetime(df['target_start_date']) - pd.to_datetime(df['issue_date'])).dt.days
        invalid_lead_time = df[df['issue_to_target_days'] < 0]
        rep.write(f"Jumlah record dengan issue_date setelah target_start_date: {len(invalid_lead_time)}\n")
        
        rep.write("\nTabel Issue Date vs Target Period:\n")
        summary_period = df.groupby(['issue_date', 'target_start_date', 'target_end_date']).agg({'station_id': 'nunique'}).reset_index()
        summary_period.rename(columns={'station_id': 'jumlah_station_unik'}, inplace=True)
        rep.write(summary_period.to_string() + "\n")
        
        # 3. AUDIT STASIUN TERHADAP MASTER
        rep.write("\n=== 3. AUDIT STASIUN TERHADAP MASTER CEWS ===\n")
        master = pd.read_parquet(MASTER_FILE)
        prob_stations = df[['station_id', 'station_name', 'latitude', 'longitude', 'kabupaten']].drop_duplicates('station_id')
        master_ids = set(master['station_id'].str.strip().str.upper())
        
        prob_stations['is_matched'] = prob_stations['station_id'].str.strip().str.upper().isin(master_ids)
        matched_count = prob_stations['is_matched'].sum()
        unmatched_count = len(prob_stations) - matched_count
        
        rep.write(f"Jumlah station unik probabilitas: {len(prob_stations)}\n")
        rep.write(f"Jumlah station unik metadata: {len(master)}\n")
        rep.write(f"Jumlah MATCHED: {matched_count}\n")
        rep.write(f"Jumlah UNMATCHED: {unmatched_count}\n")
        
        if unmatched_count > 0:
            rep.write("\nDaftar Stasiun UNMATCHED:\n")
            rep.write(prob_stations[~prob_stations['is_matched']].to_string() + "\n")
            
        # 4. VALIDASI KOORDINAT SPASIAL
        rep.write("\n=== 4. VALIDASI KOORDINAT SPASIAL ===\n")
        prob_spasial = prob_stations[prob_stations['is_matched']].copy()
        prob_spasial['station_id_norm'] = prob_spasial['station_id'].str.strip().str.upper()
        master['station_id_norm'] = master['station_id'].str.strip().str.upper()
        
        merged_spasial = pd.merge(prob_spasial, master[['station_id_norm', 'latitude', 'longitude']], on='station_id_norm', suffixes=('_prob', '_master'))
        merged_spasial['latitude_diff'] = (merged_spasial['latitude_prob'] - merged_spasial['latitude_master']).abs()
        merged_spasial['longitude_diff'] = (merged_spasial['longitude_prob'] - merged_spasial['longitude_master']).abs()
        
        merged_spasial['distance_km'] = merged_spasial.apply(lambda r: haversine(r['latitude_prob'], r['longitude_prob'], r['latitude_master'], r['longitude_master']), axis=1)
        
        mismatch = merged_spasial[(merged_spasial['latitude_diff'] > 0.01) | (merged_spasial['longitude_diff'] > 0.01)]
        rep.write(f"Jumlah SPATIAL MISMATCH (> 0.01 degree): {len(mismatch)}\n")
        if len(mismatch) > 0:
            rep.write(mismatch[['station_id', 'latitude_prob', 'latitude_master', 'longitude_prob', 'longitude_master', 'distance_km']].to_string() + "\n")
            
        # 5. VALIDASI THRESHOLD PROBABILITAS
        rep.write("\n=== 5. VALIDASI THRESHOLD PROBABILITAS ===\n")
        rep.write(f"Tipe Probabilitas unik: {df['probability_type'].unique()}\n")
        
        below_th = df[df['probability_type'] == 'BELOW']['threshold_mm'].unique()
        above_th = df[df['probability_type'] == 'ABOVE']['threshold_mm'].unique()
        rep.write(f"Threshold BELOW unik: {sorted([int(x) for x in below_th if str(x).isdigit()])}\n")
        rep.write(f"Threshold ABOVE unik: {sorted([int(x) for x in above_th if str(x).isdigit()])}\n")
        
        invalid_prob = df[(df['probability_percent'] < 0) | (df['probability_percent'] > 100)]
        rep.write(f"Jumlah record dengan probabilitas di luar 0-100: {len(invalid_prob)}\n")
        
        # 6. REGULASI BMKG NO 9 2019
        rep.write("\n=== 6. CROSS CHECK REGULASI BMKG NO 9 TAHUN 2019 ===\n")
        # probability curah hujan <20 mm/dasarian dan peluang >70%
        df['drought_probability_warning'] = ((df['probability_type'] == 'BELOW') & 
                                             (df['threshold_mm'].astype(str) == '20') & 
                                             (df['probability_percent'] > 70))
        drought_warnings = df[df['drought_probability_warning']]
        rep.write(f"Total Indikasi Kekeringan Dasarian (BELOW 20mm > 70%): {len(drought_warnings)}\n")
        
        # 7. INTEGRASI HTH
        rep.write("\n=== 7. INTEGRASI DENGAN HTH ===\n")
        if os.path.exists(HTH_FILE):
            hth = pd.read_parquet(HTH_FILE)
            # HTH snapshot biasanya per akhir bulan, kita ambil year dan month
            hth['target_year'] = hth['year']
            hth['target_month'] = hth['month']
            
            prob_b20 = df[(df['probability_type'] == 'BELOW') & (df['threshold_mm'].astype(str) == '20')].copy()
            prob_b20 = prob_b20.groupby(['station_id', 'target_year', 'target_month']).agg({'probability_percent': 'max'}).reset_index()
            
            merged_hth = pd.merge(prob_b20, hth[['station_id', 'target_year', 'target_month', 'hth_days']], on=['station_id', 'target_year', 'target_month'])
            
            kasus_A = merged_hth[(merged_hth['hth_days'] >= 21) & (merged_hth['probability_percent'] > 70)]
            kasus_B = merged_hth[(merged_hth['hth_days'] >= 31) & (merged_hth['probability_percent'] > 70)]
            
            rep.write(f"Jumlah kasus HTH >= 21 dan Prob BELOW 20 > 70%: {len(kasus_A)}\n")
            rep.write(f"Jumlah kasus HTH >= 31 dan Prob BELOW 20 > 70%: {len(kasus_B)}\n")
        else:
            rep.write("HTH file tidak ditemukan!\n")
            
        # 8. INTEGRASI SPI
        rep.write("\n=== 8. INTEGRASI DENGAN SPI ===\n")
        if os.path.exists(SPI_FILE):
            spi = pd.read_parquet(SPI_FILE)
            spi['target_year'] = spi['year']
            spi['target_month'] = spi['month']
            
            merged_spi = pd.merge(prob_b20, spi[['station_id', 'target_year', 'target_month', 'spi_value']], on=['station_id', 'target_year', 'target_month'])
            
            if os.path.exists(HTH_FILE):
                merged_spi_hth = pd.merge(merged_spi, hth[['station_id', 'target_year', 'target_month', 'hth_days']], on=['station_id', 'target_year', 'target_month'], how='left')
            else:
                merged_spi_hth = merged_spi
                merged_spi_hth['hth_days'] = np.nan
            
            def check_consistency(row):
                if pd.isna(row['spi_value']): return "UNKNOWN"
                if row['spi_value'] < 0 and row['probability_percent'] > 70: return "CONSISTENT_DRY"
                if row['spi_value'] > 0 and row['probability_percent'] > 70: return "INCONSISTENT"
                if row['spi_value'] < 0 and row['probability_percent'] < 50: return "INCONSISTENT"
                return "NEUTRAL"
                
            merged_spi_hth['consistency_status'] = merged_spi_hth.apply(check_consistency, axis=1)
            rep.write("\nTabel Analisis Konsistensi (Sample):\n")
            cols_show = ['station_id', 'target_year', 'target_month', 'spi_value', 'probability_percent', 'hth_days', 'consistency_status']
            rep.write(merged_spi_hth[cols_show].head(15).to_string() + "\n")
        else:
            rep.write("SPI file tidak ditemukan!\n")
            
        # 9. CEWS READINESS TEST
        rep.write("\n=== 9. CEWS READINESS TEST ===\n")
        is_ready = True
        if unmatched_count > 0: is_ready = False
        if len(missing_cols) > 0: is_ready = False
        if len(mismatch) > 0: is_ready = False
        if len(invalid_prob) > 0: is_ready = False
        
        if len(missing_cols) > 0 or len(invalid_prob) > 0:
            status = "RED"
        elif not is_ready:
            status = "YELLOW"
        else:
            status = "GREEN"
            
        rep.write(f"STATUS KESIAPAN: {status}\n")
        
        # 10. REKOMENDASI
        rep.write("\n=== 10. REKOMENDASI PERBAIKAN ===\n")
        if status == "GREEN":
            rep.write("- Dataset sangat matang dan terstandarisasi. Siap digabungkan ke Warning Engine.\n")
        else:
            rep.write("- Selesaikan mapping untuk stasiun yang UNMATCHED.\n")
            
    print(f"Laporan audit berhasil dibuat di: {OUT_REPORT}")

if __name__ == "__main__":
    main()
