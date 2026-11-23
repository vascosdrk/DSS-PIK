import os
import glob
import re
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# ==========================================
# KONFIGURASI PATH
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, 'PROBABILITAS_BULANAN')
META_FILE = os.path.join(BASE_DIR, 'station_metadata.parquet')
MAP_FILE = os.path.join(BASE_DIR, 'mapping_tambahan.xlsx')

OUT_PARQUET = os.path.join(BASE_DIR, 'probability_rainfall_monthly_2021_2025.parquet')
OUT_REPORT = os.path.join(BASE_DIR, 'probability_monthly_qc_report.txt')
OUT_LOG = os.path.join(BASE_DIR, 'probability_monthly_processing_log.txt')

# ==========================================
# SETUP LOGGING
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(OUT_LOG, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ==========================================
# FUNGSI HAVERSINE DISTANCE
# ==========================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# ==========================================
# FUNGSI HELPER UNTUK MENDAPATKAN SKALAR
# ==========================================
def get_scalar(val):
    if isinstance(val, pd.Series):
        return val.iloc[0] if not val.empty else None
    return val

def normalize_columns(df):
    df.columns = df.columns.astype(str).str.strip().str.upper()
    col_map = {}
    mapped_targets = set()
    for c in df.columns:
        if 'raw_station_id' not in mapped_targets and any(x in c for x in ['NOPOS', 'ID', 'KODE']):
            col_map[c] = 'raw_station_id'
            mapped_targets.add('raw_station_id')
        elif 'raw_station_name' not in mapped_targets and any(x in c for x in ['NAMA', 'POSHUJAN', 'STASIUN', 'STATION']):
            col_map[c] = 'raw_station_name'
            mapped_targets.add('raw_station_name')
        elif 'raw_longitude' not in mapped_targets and any(x in c for x in ['LON', 'BUJUR']):
            col_map[c] = 'raw_longitude'
            mapped_targets.add('raw_longitude')
        elif 'raw_latitude' not in mapped_targets and any(x in c for x in ['LAT', 'LINTANG']):
            col_map[c] = 'raw_latitude'
            mapped_targets.add('raw_latitude')
        elif 'raw_province' not in mapped_targets and any(x in c for x in ['PROV']):
            col_map[c] = 'raw_province'
            mapped_targets.add('raw_province')
        elif 'raw_kabupaten' not in mapped_targets and any(x in c for x in ['KAB', 'KOTA']):
            col_map[c] = 'raw_kabupaten'
            mapped_targets.add('raw_kabupaten')
            
    df.rename(columns=col_map, inplace=True)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    return df

# ==========================================
# MAIN PIPELINE
# ==========================================
def main():
    logging.info("=== START PIPELINE PROBABILITAS CURAH HUJAN BULANAN ===")
    
    # 1. Load Metadata & Mapping
    logging.info(f"Memuat {os.path.basename(META_FILE)} dan {os.path.basename(MAP_FILE)}")
    
    try:
        master_df = pd.read_parquet(META_FILE)
        master_df['station_id_norm'] = master_df['station_id'].astype(str).str.strip().str.upper()
        master_dict = master_df.set_index('station_id_norm').to_dict('index')
        master_ids = set(master_df['station_id_norm'].unique())
    except Exception as e:
        logging.error(f"Gagal memuat metadata: {e}")
        return

    map_records = []
    try:
        map_df = pd.read_excel(MAP_FILE)
        map_df.columns = map_df.columns.astype(str).str.strip().str.lower()
        if 'usable_for_cews' in map_df.columns:
            map_df = map_df[map_df['usable_for_cews'].astype(str).str.upper().str.strip().isin(['TRUE', '1', 'YES', 'TRUE.0', 'T'])]
        if 'station_id' in map_df.columns:
            map_df = map_df[map_df['station_id'].notna()]
            map_df['station_id_norm'] = map_df['station_id'].astype(str).str.strip().str.upper()
            map_df = map_df[map_df['station_id_norm'].isin(master_ids)]
            map_records = map_df.to_dict(orient='records')
    except Exception as e:
        logging.error(f"Gagal memuat mapping tambahan: {e}")
        
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
            return sid_norm, "MATCHED", master_dict[sid_norm]
            
        # LEVEL 2 - REFERENCE / DICTIONARY
        ref = match_reference(sid_norm, sname)
        if ref:
            master_rec = master_dict.get(ref['station_id_norm'])
            if master_rec:
                return ref['station_id_norm'], "MAPPED_ADDITIONAL", master_rec
                
        # LEVEL 3 - HAVERSINE MATCHING
        if pd.notna(slat) and pd.notna(slon):
            try:
                slat_f, slon_f = float(slat), float(slon)
                best_id = None
                best_dist = float('inf')
                for mid, mrec in master_dict.items():
                    mlat, mlon = mrec.get('latitude'), mrec.get('longitude')
                    if pd.notna(mlat) and pd.notna(mlon):
                        dist = haversine(slat_f, slon_f, float(mlat), float(mlon))
                        if dist < 0.1 and dist < best_dist:
                            best_id = mid
                            best_dist = dist
                if best_id:
                    return best_id, "MAPPED_ADDITIONAL", master_dict[best_id]
            except:
                pass
                
        return None, "UNMATCHED", None

    # 2. Cari File Excel
    file_pattern = os.path.join(INPUT_DIR, '**', '*.xlsx')
    excel_files = glob.glob(file_pattern, recursive=True)
    
    # Filter file yang open sementara (~$)
    excel_files = [f for f in excel_files if not os.path.basename(f).startswith('~$')]
    logging.info(f"Ditemukan {len(excel_files)} file Excel probabilitas bulanan.")
    
    if not excel_files:
        logging.error("Tidak ada data probabilitas yang berhasil ditemukan!")
        return

    # Pemetaan kolom bulan ke angka
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4,
        'May': 5, 'Jun': 6, 'Jul': 7, 'Aug': 8,
        'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    all_data = []
    
    # 3. Proses setiap file
    for file_path in excel_files:
        fname = os.path.basename(file_path)
        logging.info(f"Memproses file: {fname}")
        
        # Ekstrak informasi dari nama file: KEPRI_pch_ecmwf_perpos_ver_2025.01.01.xlsx
        match = re.search(r'([A-Z]+)_([a-z]+)_([a-z]+)_([a-z]+)_ver_(\d{4}\.\d{2}\.\d{2})\.xlsx', fname)
        if not match:
            logging.warning(f"Format nama file tidak sesuai: {fname}")
            continue
            
        region = match.group(1)
        product = match.group(2)
        model = match.group(3)
        product_type = match.group(4)
        issue_date_str = match.group(5)
        
        try:
            issue_date = pd.to_datetime(issue_date_str, format='%Y.%m.%d')
        except:
            logging.warning(f"Gagal parse issue_date dari {fname}")
            continue
            
        # Buka Excel
        try:
            xl = pd.ExcelFile(file_path)
        except Exception as e:
            logging.error(f"Gagal membaca Excel {fname}: {e}")
            continue
            
        sheets = xl.sheet_names
        
        for sheet in sheets:
            # Tentukan tipe dan threshold
            prob_type = None
            threshold = None
            
            m_below = re.match(r'^pb(\d+)$', sheet)
            m_above = re.match(r'^pa(\d+)$', sheet)
            
            if m_below:
                prob_type = 'BELOW'
                threshold = int(m_below.group(1))
            elif m_above:
                prob_type = 'ABOVE'
                threshold = int(m_above.group(1))
            else:
                continue # Skip sheet lain
                
            logging.info(f"  Membaca sheet: {sheet} -> {prob_type} {threshold}mm")
            
            df_sheet = pd.read_excel(xl, sheet_name=sheet)
            df_sheet = normalize_columns(df_sheet)
            
            # Melt dataframe
            # Columns could be JAN, FEB, MAR... or Jan, Feb, Mar... because we upper() them!
            month_map_upper = {k.upper(): v for k, v in month_map.items()}
            
            id_vars = [c for c in df_sheet.columns if c in ['raw_station_id', 'raw_station_name', 'raw_latitude', 'raw_longitude', 'raw_province', 'raw_kabupaten']]
            val_vars = [c for c in df_sheet.columns if str(c).strip().upper() in month_map_upper.keys()]
            
            if not val_vars:
                logging.warning(f"Kolom bulan (Jan, Feb, ...) tidak ditemukan di {sheet}")
                continue
                
            df_melt = pd.melt(df_sheet, id_vars=id_vars, value_vars=val_vars, var_name='month_str', value_name='probability_percent')
            df_melt = df_melt.dropna(subset=['probability_percent'])
            
            # Tambahkan metadata
            df_melt['issue_date'] = issue_date
            df_melt['target_year'] = issue_date.year
            df_melt['target_month'] = df_melt['month_str'].apply(lambda x: month_map_upper.get(str(x).strip().upper()))
            
            df_melt['probability_type'] = prob_type
            df_melt['threshold_mm'] = threshold
            df_melt['source_file'] = fname
            df_melt['source_sheet'] = sheet
            
            # Ambil identitas
            for idx, row in df_melt.iterrows():
                # Extract scalars
                id_raw = get_scalar(row.get('raw_station_id'))
                nama_raw = get_scalar(row.get('raw_station_name'))
                lat_raw = get_scalar(row.get('raw_latitude'))
                lon_raw = get_scalar(row.get('raw_longitude'))
                kab_raw = get_scalar(row.get('raw_kabupaten', ''))
                
                # Gunakan fungsi resolusi stasiun yang sama dengan dasarian
                final_id, status, master_rec = resolve_station(id_raw, nama_raw, lat_raw, lon_raw)
                
                if master_rec:
                    s_id = master_rec['station_id']
                    s_name = master_rec['station_name']
                    lat_m = master_rec['latitude']
                    lon_m = master_rec['longitude']
                    prov_m = master_rec['province']
                else:
                    s_id = None
                    s_name = None
                    lat_m = None
                    lon_m = None
                    prov_m = None
                    
                # Spatial check
                haversine_dist = np.nan
                spatial_flag = 'UNKNOWN'
                
                if status in ['MATCHED', 'MAPPED_ADDITIONAL', 'RESOLVED_BY_NAME_COORDINATE'] and pd.notna(lat_raw) and pd.notna(lon_raw) and pd.notna(lat_m) and pd.notna(lon_m):
                    try:
                        dist = haversine(float(lat_raw), float(lon_raw), float(lat_m), float(lon_m))
                        haversine_dist = dist
                        if dist > 1.0:
                            spatial_flag = 'SPATIAL_WARNING'
                        else:
                            spatial_flag = 'SPATIAL_MATCH'
                    except:
                        pass

                # Handle Series conversion for probability
                prob_val = get_scalar(row['probability_percent'])
                try:
                    prob_val = float(str(prob_val).replace(',', '.'))
                except:
                    prob_val = np.nan

                all_data.append({
                    'station_id': s_id,
                    'station_name': s_name,
                    'latitude': lat_m,
                    'longitude': lon_m,
                    'province': prov_m,
                    'kabupaten': kab_raw,
                    'issue_date': row['issue_date'],
                    'target_year': row['target_year'],
                    'target_month': row['target_month'],
                    'probability_type': row['probability_type'],
                    'threshold_mm': row['threshold_mm'],
                    'probability_percent': float(get_scalar(row['probability_percent'])),
                    'source_file': row['source_file'],
                    'source_sheet': row['source_sheet'],
                    'station_mapping_status': status,
                    'haversine_distance_km': haversine_dist,
                    'spatial_flag': spatial_flag,
                    'source_station_name_raw': nama_raw
                })
                
    if not all_data:
        logging.error("Tidak ada data probabilitas yang berhasil diekstrak!")
        return
        
    logging.info("Menyusun DataFrame akhir...")
    df_final = pd.DataFrame(all_data)
    
    # 5. Tambahkan CEWS Indicators
    df_final['monthly_heavy_rain_indicator'] = False
    mask_heavy = (df_final['probability_type'] == 'ABOVE') & (df_final['threshold_mm'].isin([400, 500])) & (df_final['probability_percent'] > 70)
    df_final.loc[mask_heavy, 'monthly_heavy_rain_indicator'] = True
    
    df_final['monthly_dryness_indicator'] = False
    mask_dry = (df_final['probability_type'] == 'BELOW') & (df_final['threshold_mm'].isin([50, 100, 150])) & (df_final['probability_percent'] > 70)
    df_final.loc[mask_dry, 'monthly_dryness_indicator'] = True
    
    # 6. Save Parquet
    logging.info("Menyimpan dataset ke format Parquet...")
    
    # Sort and reorder columns
    cols_order = [
        'station_id', 'station_name', 'latitude', 'longitude', 'province', 'kabupaten',
        'issue_date', 'target_year', 'target_month',
        'probability_type', 'threshold_mm', 'probability_percent',
        'monthly_heavy_rain_indicator', 'monthly_dryness_indicator',
        'source_file', 'source_sheet', 'station_mapping_status', 'haversine_distance_km', 'spatial_flag', 'source_station_name_raw'
    ]
    df_final = df_final[[c for c in cols_order if c in df_final.columns]]
    
    try:
        df_final.to_parquet(OUT_PARQUET, index=False)
    except Exception as e:
        logging.error(f"FATAL ERROR: {e}")
        return
        
    # 7. Generate QC Report
    logging.info("Membuat Laporan QC...")
    with open(OUT_REPORT, 'w', encoding='utf-8') as f:
        f.write("=== PROBABILITY MONTHLY CEWS QC REPORT ===\n\n")
        
        f.write("=== A. FILE PROCESSING ===\n")
        f.write(f"Jumlah file Excel diproses: {len(excel_files)}\n")
        f.write(f"Jumlah sheet diproses: {df_final[['source_file','source_sheet']].drop_duplicates().shape[0]}\n\n")
        
        f.write("=== B. DATA VOLUME ===\n")
        f.write(f"Jumlah baris output: {len(df_final)}\n")
        f.write(f"Jumlah station unik: {df_final['station_id'].nunique(dropna=True)}\n")
        f.write(f"Tahun Target: {df_final['target_year'].unique().tolist()}\n")
        f.write(f"Bulan Target: sorted {sorted(df_final['target_month'].unique().tolist())}\n\n")
        
        f.write("=== C. THRESHOLD VALIDATION ===\n")
        valid_below = [50, 100, 150]
        valid_above = [50, 100, 150, 200, 300, 400, 500]
        
        below_th = df_final[df_final['probability_type'] == 'BELOW']['threshold_mm'].unique()
        above_th = df_final[df_final['probability_type'] == 'ABOVE']['threshold_mm'].unique()
        
        f.write(f"BELOW Thresholds di data: {sorted(below_th)}\n")
        f.write(f"ABOVE Thresholds di data: {sorted(above_th)}\n")
        
        invalid_b = [x for x in below_th if x not in valid_below]
        invalid_a = [x for x in above_th if x not in valid_above]
        f.write(f"Invalid BELOW thresholds: {invalid_b}\n")
        f.write(f"Invalid ABOVE thresholds: {invalid_a}\n\n")
        
        f.write("=== D. PROBABILITY VALIDATION ===\n")
        out_of_bounds = df_final[(df_final['probability_percent'] < 0) | (df_final['probability_percent'] > 100)]
        f.write(f"Probabilitas < 0 atau > 100 (%): {len(out_of_bounds)} record\n\n")
        
        f.write("=== E. SPATIAL VALIDATION ===\n")
        f.write(f"Status Mapping:\n{df_final.groupby('station_mapping_status').size().to_string()}\n\n")
        f.write(f"Status Spatial Flag:\n{df_final.groupby('spatial_flag').size().to_string()}\n\n")
        
        unmatched = df_final[df_final['station_mapping_status'] == 'UNMATCHED'][['source_station_name_raw', 'kabupaten']].drop_duplicates()
        if not unmatched.empty:
            f.write("Daftar Stasiun UNMATCHED:\n")
            f.write(unmatched.to_string() + "\n\n")
            
        f.write("=== F. DUPLICATE CHECK ===\n")
        dups = df_final.duplicated(subset=['station_id', 'target_year', 'target_month', 'probability_type', 'threshold_mm'], keep=False)
        dups_valid = df_final[dups & (df_final['station_mapping_status'] != 'UNMATCHED')]
        f.write(f"Jumlah duplikasi (station_id valid): {len(dups_valid)}\n\n")
        
        f.write("=== G. INDIKATOR CEWS (BMKG NO 9 TAHUN 2019) ===\n")
        f.write(f"Total Indikasi MONTHLY HEAVY RAIN (>400/500mm, >70%): {df_final['monthly_heavy_rain_indicator'].sum()}\n")
        f.write(f"Total Indikasi MONTHLY DRYNESS (<50/100/150mm, >70%): {df_final['monthly_dryness_indicator'].sum()}\n\n")
        
        f.write("=== H. PREVIEW 10 BARIS TERATAS ===\n")
        f.write(df_final.head(10).to_string() + "\n")
        
    logging.info("PIPELINE SELESAI.")

if __name__ == '__main__':
    main()
