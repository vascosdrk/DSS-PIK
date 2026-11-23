import os
import glob
import pandas as pd
import numpy as np
import logging
import traceback
import re

# 1. Konfigurasi Logging dan Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROB_DIR = os.path.join(BASE_DIR, "probabilitas")
LOG_FILE = os.path.join(BASE_DIR, "probability_processing_log.txt")
QC_FILE = os.path.join(BASE_DIR, "probability_qc_report.txt")
OUT_PARQUET = os.path.join(BASE_DIR, "probability_rainfall_dasarian_2025.parquet")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_target_dasarian(issue_date):
    """
    Menghitung target dasarian dengan asumsi issue_date adalah beberapa hari
    sebelum periode target (menggunakan offset + 5 hari).
    """
    target_dt = issue_date + pd.Timedelta(days=5)
    year = target_dt.year
    month = target_dt.month
    day = target_dt.day
    
    if day <= 10:
        dasarian = 1
        start_date = pd.Timestamp(year, month, 1)
        end_date = pd.Timestamp(year, month, 10)
    elif day <= 20:
        dasarian = 2
        start_date = pd.Timestamp(year, month, 11)
        end_date = pd.Timestamp(year, month, 20)
    else:
        dasarian = 3
        start_date = pd.Timestamp(year, month, 21)
        end_date = start_date + pd.offsets.MonthEnd(0)
        
    return year, month, dasarian, start_date, end_date

def parse_filename(filename):
    """
    Ekstrak tanggal issue dari pola: KEPRI_pch_ecmwf_perpos_ver_YYYY.MM.DD.xlsx
    """
    match = re.search(r'ver_(\d{4}\.\d{2}\.\d{2})', filename)
    if match:
        date_str = match.group(1).replace('.', '-')
        return pd.to_datetime(date_str)
    return None

def normalize_columns(df, target_col=None):
    """
    Menyeragamkan nama kolom Excel agar mudah di-parse.
    """
    col_map = {}
    for c in df.columns:
        c_str = str(c).strip()
        c_upper = c_str.upper()
        if any(x in c_upper for x in ['NOPOS', 'ID', 'KODE']): col_map[c] = 'raw_station_id'
        elif any(x in c_upper for x in ['NAMA', 'POSHUJAN', 'STASIUN']): col_map[c] = 'raw_station_name'
        elif any(x in c_upper for x in ['LON', 'BUJUR']): col_map[c] = 'raw_longitude'
        elif any(x in c_upper for x in ['LAT', 'LINTANG']): col_map[c] = 'raw_latitude'
        elif any(x in c_upper for x in ['PROV']): col_map[c] = 'raw_province'
        elif any(x in c_upper for x in ['KAB', 'KOTA']): col_map[c] = 'raw_kabupaten'
        elif target_col and c_str.lower() == target_col.lower(): col_map[c] = 'raw_probability'
        elif any(x in c_upper for x in ['PELUANG', 'PROB', 'VALUE']): col_map[c] = 'raw_probability'
    df.rename(columns=col_map, inplace=True)
    return df

def clean_probability(val):
    if pd.isna(val): return np.nan
    try:
        v = float(str(val).replace(',', '.'))
        return v
    except:
        return np.nan

def haversine(lat1, lon1, lat2, lon2):
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2): return np.nan
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        R = 6371
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
        return 2 * R * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return np.nan

def main():
    try:
        logging.info("=== START PIPELINE PROBABILITAS CURAH HUJAN DASARIAN ===")
        
        # 2. Muat Master Data & Mapping Tambahan
        logging.info("Memuat station_metadata.parquet dan mapping_tambahan.xlsx")
        master_path = os.path.join(BASE_DIR, "station_metadata.parquet")
        map_path = os.path.join(BASE_DIR, "mapping_tambahan.xlsx")
        
        if not os.path.exists(master_path):
            raise FileNotFoundError(f"Master metadata tidak ditemukan: {master_path}")
            
        master_df = pd.read_parquet(master_path)
        master_df['station_id_norm'] = master_df['station_id'].astype(str).str.strip().str.upper()
        master_dict = master_df.set_index('station_id_norm').to_dict('index')
        master_ids = set(master_df['station_id_norm'].unique())
        
        map_records = []
        if os.path.exists(map_path):
            map_df = pd.read_excel(map_path)
            map_df.columns = map_df.columns.astype(str).str.strip().str.lower()
            if 'usable_for_cews' in map_df.columns:
                map_df = map_df[map_df['usable_for_cews'].astype(str).str.upper().str.strip().isin(['TRUE', '1', 'YES', 'TRUE.0', 'T'])]
            if 'station_id' in map_df.columns:
                map_df = map_df[map_df['station_id'].notna()]
                map_df['station_id_norm'] = map_df['station_id'].astype(str).str.strip().str.upper()
                map_df = map_df[map_df['station_id_norm'].isin(master_ids)]
                map_records = map_df.to_dict(orient='records')
        
        def match_reference(sid_norm, sname):
            for r in map_records:
                snopos = str(r.get('source_nopos', '')).strip()
                if snopos.endswith('.0'): snopos = snopos[:-2]
                skey = str(r.get('source_key', '')).strip()
                if skey.endswith('.0'): skey = skey[:-2]
                if snopos.upper() == sid_norm: return r
                if skey.upper() == sid_norm: return r
            if sname:
                sname_norm = str(sname).strip().upper()
                for r in map_records:
                    if str(r.get('source_name', '')).strip().upper() == sname_norm: return r
                    variants = str(r.get('source_name_variants', '')).upper().split(',')
                    if sname_norm in [v.strip() for v in variants]: return r
            return None

        def resolve_station(raw_id, raw_name, slat, slon):
            sid_norm = str(raw_id).strip().upper()
            if sid_norm.endswith('.0'): sid_norm = sid_norm[:-2]
            sname = str(raw_name).strip().upper()
            
            # LEVEL 0 - DETERMINISTIC RESOLUTION (Untuk Kasus Ambigu)
            if sid_norm == '21010701A':
                if any(x in sname for x in ['BINTAN UTARA', 'SUNGAI JERAM', 'LANCANG KUNING']):
                    return '21010701A', 'RESOLVED_BY_NAME_COORDINATE', master_dict.get('21010701A')
                elif any(x in sname for x in ['KUNDUR UTARA', 'URUNG', 'KANTOR CAMAT KUNDUR', 'KUNDUR']):
                    return '21020701A', 'RESOLVED_BY_NAME_COORDINATE', master_dict.get('21020701A')
            elif sid_norm == '21010601A':
                if any(x in sname for x in ['BATU 18', 'KIJANG']):
                    return '21010601A', 'RESOLVED_BY_NAME_COORDINATE', master_dict.get('21010601A')
                elif any(x in sname for x in ['BURU']):
                    return '21020601A', 'RESOLVED_BY_NAME_COORDINATE', master_dict.get('21020601A')
            elif sid_norm == '21040203A':
                if any(x in sname for x in ['DINAS PERTANIAN', 'DAIK LINGGA', 'LINGGA']):
                    return '21040203A', 'RESOLVED_BY_NAME_COORDINATE', master_dict.get('21040203A')
                elif any(x in sname for x in ['DUARA']):
                    return '21040501A', 'RESOLVED_BY_NAME_COORDINATE', master_dict.get('21040501A')
            
            # LEVEL 1 - EXACT
            if sid_norm in master_dict:
                return sid_norm, "EXACT_MASTER", master_dict[sid_norm]
            
            # LEVEL 2 - REFERENCE
            match = match_reference(sid_norm, sname)
            if match:
                target_id = match['station_id_norm']
                if target_id in master_dict:
                    return target_id, "REFERENCE_TO_MASTER", master_dict[target_id]
            
            return sid_norm, "UNRESOLVED", None

        # 3. Looping File Excel
        excel_files = glob.glob(os.path.join(PROB_DIR, "2025", "*.xls*"), recursive=True)
        logging.info(f"Ditemukan {len(excel_files)} file Excel probabilitas.")
        
        all_records = []
        sheets_processed = 0
        
        for fpath in excel_files:
            fname = os.path.basename(fpath)
            issue_date = parse_filename(fname)
            
            if issue_date is None:
                logging.warning(f"Gagal mengekstrak tanggal dari nama file: {fname}. Dilewati.")
                continue
                
            t_year, t_month, t_dasarian, t_start, t_end = get_target_dasarian(issue_date)
            m_names = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'Mei', 6:'Jun', 7:'Jul', 8:'Agu', 9:'Sep', 10:'Okt', 11:'Nov', 12:'Des'}
            d_romans = {1:'I', 2:'II', 3:'III'}
            target_col = f"{m_names.get(t_month, '')}{d_romans.get(t_dasarian, '')}"
            
            try:
                xls = pd.ExcelFile(fpath)
                sheets = xls.sheet_names
            except Exception as e:
                logging.error(f"Gagal membaca Excel {fname}: {e}")
                continue
                
            for sheet in sheets:
                s_lower = sheet.strip().lower()
                
                prob_type = None
                threshold = None
                if s_lower.startswith('pb'):
                    prob_type = "BELOW"
                    threshold = s_lower.replace('pb', '')
                elif s_lower.startswith('pa'):
                    prob_type = "ABOVE"
                    threshold = s_lower.replace('pa', '')
                
                if prob_type is None or not threshold.isdigit():
                    # Bukan sheet probabilitas yang valid
                    continue
                    
                threshold_mm = int(threshold)
                
                try:
                    df_sheet = pd.read_excel(xls, sheet_name=sheet)
                    df_sheet = normalize_columns(df_sheet, target_col=target_col)
                    # Fallback jika target_col tidak cocok persis (ambil kolom dasarian pertama)
                    if 'raw_probability' not in df_sheet.columns:
                        for col in df_sheet.columns:
                            if any(col.lower().startswith(m.lower()) for m in ['jan', 'feb', 'mar', 'apr', 'mei', 'jun', 'jul', 'agu', 'sep', 'okt', 'nov', 'des']):
                                df_sheet.rename(columns={col: 'raw_probability'}, inplace=True)
                                break
                except Exception as e:
                    logging.warning(f"Gagal membaca sheet {sheet} di {fname}: {e}")
                    continue
                
                sheets_processed += 1
                
                if 'raw_station_id' not in df_sheet.columns:
                    logging.warning(f"Kolom ID tidak ditemukan di sheet {sheet} file {fname}. Dilewati.")
                    continue
                    
                for _, row in df_sheet.iterrows():
                    raw_id = row.get('raw_station_id')
                    if pd.isna(raw_id) or str(raw_id).strip() == '': continue
                    
                    raw_name = row.get('raw_station_name', '')
                    raw_prob = clean_probability(row.get('raw_probability'))
                    
                    master_id, mapping_status, master_data = resolve_station(raw_id, raw_name, row.get('raw_latitude'), row.get('raw_longitude'))
                    
                    def get_scalar(val):
                        if isinstance(val, pd.Series): return val.iloc[0]
                        if isinstance(val, np.ndarray): return val[0] if len(val) > 0 else np.nan
                        return val

                    final_lat = get_scalar(master_data['latitude'] if master_data else row.get('raw_latitude', np.nan))
                    final_lon = get_scalar(master_data['longitude'] if master_data else row.get('raw_longitude', np.nan))
                    final_prov = get_scalar(master_data['province'] if master_data else row.get('raw_province', ''))
                    final_kab = get_scalar(master_data['regency'] if master_data else row.get('raw_kabupaten', ''))
                    final_name = get_scalar(master_data['station_name'] if master_data else raw_name)
                    
                    all_records.append({
                        'station_id': str(get_scalar(master_id)),
                        'station_name': str(final_name),
                        'latitude': final_lat,
                        'longitude': final_lon,
                        'province': final_prov,
                        'kabupaten': final_kab,
                        'issue_date': issue_date,
                        'target_start_date': t_start,
                        'target_end_date': t_end,
                        'target_year': t_year,
                        'target_month': t_month,
                        'target_dasarian': t_dasarian,
                        'probability_type': prob_type,
                        'threshold_mm': threshold_mm,
                        'probability_percent': raw_prob,
                        'source_file': fname,
                        'source_sheet': sheet,
                        'station_mapping_status': mapping_status
                    })

        # 4. Membangun DataFrame Output
        if not all_records:
            logging.error("Tidak ada data probabilitas yang berhasil diekstrak!")
            return
            
        df_out = pd.DataFrame(all_records)
        df_out['latitude'] = pd.to_numeric(df_out['latitude'], errors='coerce')
        df_out['longitude'] = pd.to_numeric(df_out['longitude'], errors='coerce')
        for col in ['station_id', 'station_name', 'province', 'kabupaten', 'probability_type', 'source_file', 'source_sheet', 'station_mapping_status']:
            df_out[col] = df_out[col].astype(str)
        
        logging.info("Menyimpan dataset ke format Parquet...")
        df_out.to_parquet(OUT_PARQUET, index=False, compression='snappy')
        
        # 5. Quality Control (QC)
        logging.info("Menjalankan Quality Control...")
        with open(QC_FILE, "w", encoding='utf-8') as f:
            f.write("=== QUALITY CONTROL REPORT: PROBABILITAS HUJAN DASARIAN ===\n")
            f.write(f"1. Jumlah File Excel Terbaca: {len(excel_files)}\n")
            f.write(f"2. Jumlah Sheet Diproses: {sheets_processed}\n")
            f.write(f"3. Jumlah Record Baris Output: {len(df_out)}\n")
            f.write(f"4. Jumlah Stasiun Unik (Total): {df_out['station_id'].nunique()}\n")
            
            f.write("\n=== STATUS MAPPING STASIUN ===\n")
            f.write(df_out['station_mapping_status'].value_counts().to_string() + "\n")
            
            f.write("\n=== VALIDASI NILAI PROBABILITAS ===\n")
            prob_gt_100 = df_out[df_out['probability_percent'] > 100]
            prob_lt_0 = df_out[df_out['probability_percent'] < 0]
            f.write(f"Probability > 100%: {len(prob_gt_100)} records\n")
            f.write(f"Probability < 0%: {len(prob_lt_0)} records\n")
            if not prob_gt_100.empty:
                f.write(f"Contoh > 100:\n{prob_gt_100[['station_id', 'probability_percent']].head(3).to_string()}\n")
            
            f.write("\n=== VALIDASI SPASIAL ===\n")
            null_coords = df_out[df_out['latitude'].isna() | df_out['longitude'].isna()]
            f.write(f"Koordinat Kosong (NaN): {len(null_coords)} records\n")
            
            f.write("\n=== VALIDASI TEMPORAL ===\n")
            f.write(f"Periode Issue Date Minimum: {df_out['issue_date'].min()}\n")
            f.write(f"Periode Issue Date Maksimum: {df_out['issue_date'].max()}\n")
            
            f.write("\n=== DISTRIBUSI THRESHOLD ===\n")
            f.write(df_out.groupby(['probability_type', 'threshold_mm']).size().to_string() + "\n")
            
            f.write("\n=== CEK DUPLIKASI ===\n")
            dups = df_out.duplicated(subset=['station_id', 'target_year', 'target_month', 'target_dasarian', 'probability_type', 'threshold_mm'])
            f.write(f"Duplikasi Record Exact: {dups.sum()} records\n")
            
        logging.info("=== SELESAI ===")
        
        # 6. Menampilkan Hasil Akhir ke Console
        print("\n" + "="*50)
        print("PIPELINE BERHASIL DIJALANKAN")
        print("="*50)
        print(f"Jumlah file diproses : {len(excel_files)}")
        print(f"Jumlah sheet diproses: {sheets_processed}")
        print(f"Jumlah baris output  : {len(df_out)}")
        print(f"Jumlah stasiun unik  : {df_out['station_id'].nunique()}")
        print(f"Periode Waktu Target : {df_out['target_start_date'].dt.date.min()} sd {df_out['target_end_date'].dt.date.max()}")
        print("-" * 50)
        print("Distribusi Threshold:")
        print(df_out.groupby(['probability_type', 'threshold_mm']).size().to_string())
        print("-" * 50)
        print("CONTOH 10 BARIS OUTPUT:")
        cols_to_show = ['station_id', 'target_start_date', 'target_dasarian', 'probability_type', 'threshold_mm', 'probability_percent']
        print(df_out[cols_to_show].head(10).to_string(index=False))
        print("="*50)

    except Exception as e:
        logging.error(f"FATAL ERROR: {e}")
        with open(QC_FILE, "w", encoding='utf-8') as f:
            f.write(f"PIPELINE GAGAL. ERROR TRACEBACK:\n{traceback.format_exc()}")
        print("Script gagal dieksekusi. Periksa log.")

if __name__ == "__main__":
    main()
