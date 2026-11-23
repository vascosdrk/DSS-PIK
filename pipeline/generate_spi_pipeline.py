import os
import glob
import pandas as pd
import numpy as np
import datetime
import re
import traceback

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SPI_DIR = os.path.join(BASE_DIR, "SPI")

OUT_ANALYSIS = os.path.join(BASE_DIR, "spi_analysis_2021_2025.parquet")
OUT_FORECAST = os.path.join(BASE_DIR, "spi_forecast_2021_2025.parquet")
OUT_CEWS = os.path.join(BASE_DIR, "spi_cews_2021_2025.parquet")
OUT_HTH_SNAP = os.path.join(BASE_DIR, "hth_monthly_snapshot_2021_2025.parquet")
OUT_DROUGHT = os.path.join(BASE_DIR, "drought_monitoring_analysis_2021_2025.parquet")
OUT_FORECAST_LAYER = os.path.join(BASE_DIR, "drought_spi_forecast_2021_2025.parquet")
OUT_COMPARE = os.path.join(BASE_DIR, "spi_analysis_vs_forecast_2021_2025.parquet")
OUT_EXCLUDED = os.path.join(BASE_DIR, "spi_excluded_stations_2021_2025.parquet")
OUT_REGISTRY = os.path.join(BASE_DIR, "spi_station_mapping_registry_2021_2025.parquet")
OUT_REPORT = os.path.join(BASE_DIR, "STATION_MAPPING_AUDIT.md")

MONTHS = ["januari", "februari", "maret", "april", "mei", "juni", "juli", "agustus", "september", "oktober", "november", "desember"]
MONTH_NUM = {m: i+1 for i, m in enumerate(MONTHS)}

def clean_value(v):
    if pd.isna(v): return np.nan
    vs = str(v).strip()
    if vs in ['', '-', 'NA', 'NaN', 'null']: return np.nan
    vs = vs.replace(',', '.')
    vs = re.sub(r'[^\d\.\-]', '', vs)
    try: return float(vs)
    except: return np.nan

def clean_category(v):
    if pd.isna(v): return None
    vs = str(v).strip()
    if vs in ['', '-', 'NA', 'NaN', 'null']: return None
    return " ".join(vs.split())

def get_warning_status(val):
    if pd.isna(val): return "NO_DATA"
    if val <= -2.0: return "AWAS"
    if val <= -1.5: return "SIAGA"
    if val <= -1.0: return "WASPADA"
    return "NORMAL"

def get_warning_color(status):
    return {"NORMAL": "GREEN", "WASPADA": "YELLOW", "SIAGA": "ORANGE", "AWAS": "RED", "NO_DATA": "NO_DATA"}.get(status, "NO_DATA")

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

def parse_sheet(filepath, sheet, year, spi_type):
    try: df_raw = pd.read_excel(filepath, sheet_name=sheet, header=None)
    except: return pd.DataFrame()
    
    max_months, h_idx = 0, -1
    for idx, row in df_raw.head(15).iterrows():
        r_str = " ".join(row.astype(str).str.lower())
        m_count = sum(1 for m in MONTHS if m in r_str)
        if m_count > max_months:
            max_months = m_count
            h_idx = idx

    if h_idx == -1: return pd.DataFrame()
        
    h1 = df_raw.iloc[h_idx].ffill().astype(str).str.lower().str.replace('\n', ' ').str.strip()
    next_row_str = " ".join(df_raw.iloc[h_idx+1].astype(str).str.lower()) if h_idx+1 < len(df_raw) else ""
    is_multi_header = any(x in next_row_str for x in ['indeks', 'kriteria', 'nilai', 'kategori', 'index', 'spi', 'sifat'])
    
    data_start = h_idx + 2 if is_multi_header else h_idx + 1
    h2 = df_raw.iloc[h_idx+1].astype(str).str.lower().str.replace('\n', ' ').str.strip() if is_multi_header else pd.Series([""] * len(df_raw.columns))

    id_col, name_col, lat_col, lon_col = None, None, None, None
    for i in range(len(h1)):
        c1, c2 = h1[i] if h1[i] != 'nan' else '', h2[i] if h2[i] != 'nan' else ''
        combo = f"{c1} {c2}".lower()
        if not id_col and any(x in combo for x in ['id ', 'no ', 'no.', 'nopos', 'kode']): id_col = i
        if not name_col and any(x in combo for x in ['stasiun', 'station', 'nama']):
            if id_col != i:
                name_col = i
        if not lat_col and any(x in combo for x in ['lat', 'lintang', 'ls', 'lu']): lat_col = i
        if not lon_col and any(x in combo for x in ['lon', 'bujur', 'bt']): lon_col = i

    if id_col is None:
        for i in range(len(h1)):
            sample = df_raw.iloc[data_start:data_start+15, i].astype(str).str.replace(r'\.0$', '', regex=True)
            if sample.str.contains(r'^(21\d{6}[A-Za-z]?|96\d{3}|00096\d{3}[A-Za-z]?)$', regex=True).any():
                id_col = i
                break

    month_cols = {m: {'val': None, 'cat': None} for m in MONTHS}
    for i in range(len(h1)):
        c1, c2 = h1[i] if h1[i] != 'nan' else '', h2[i] if h2[i] != 'nan' else ''
        for m in MONTHS:
            if m in c1:
                if any(x in c2 for x in ['kriteria', 'kategori', 'status', 'sifat']): month_cols[m]['cat'] = i
                elif any(x in c2 for x in ['indeks', 'nilai', 'index', 'spi']): month_cols[m]['val'] = i
                else:
                    if month_cols[m]['val'] is None: month_cols[m]['val'] = i
                    elif month_cols[m]['cat'] is None: month_cols[m]['cat'] = i

    spi_scale = None
    head_text = " ".join(df_raw.head(10).astype(str).fillna('').values.flatten()).lower()
    if any(x in head_text for x in ['spi 3', 'spi-3', '3 bulanan']): spi_scale = 3
    elif any(x in head_text for x in ['spi 1', 'spi-1', '1 bulanan']): spi_scale = 1

    records = []
    for row_idx in range(data_start, len(df_raw)):
        row = df_raw.iloc[row_idx]
        if id_col is None or pd.isna(row[id_col]): continue
        sid = str(row[id_col]).strip()
        if sid.endswith('.0'): sid = sid[:-2]
        if not sid or sid.lower() == 'nan': continue
        
        sname = str(row[name_col]).strip() if name_col is not None else ''
        slat = row[lat_col] if lat_col is not None else np.nan
        slon = row[lon_col] if lon_col is not None else np.nan
        
        for m in MONTHS:
            v_col, c_col = month_cols[m]['val'], month_cols[m]['cat']
            if v_col is not None and pd.notna(row[v_col]):
                records.append({
                    'source_station_id': sid,
                    'source_nopos': sid,
                    'source_station_name': sname,
                    'source_latitude': slat,
                    'source_longitude': slon,
                    'year': year,
                    'month': MONTH_NUM[m],
                    'spi_value_raw': row[v_col],
                    'spi_category_source': row[c_col] if c_col is not None else None,
                    'source_file': os.path.basename(filepath),
                    'source_sheet': sheet,
                    'source_year': year,
                    'spi_type': spi_type,
                    'spi_scale_months': spi_scale
                })
    return pd.DataFrame(records)

def main():
    print("Mulai FINALISASI SPI Pipeline (mapping_tambahan.xlsx)...")
    
    # 1. LOAD MASTER
    master_meta_path = os.path.join(BASE_DIR, 'station_metadata.parquet')
    meta = pd.read_parquet(master_meta_path)
    meta['station_id_normalized'] = meta['station_id'].astype(str).str.strip().str.upper()
    master_ids = set(meta['station_id_normalized'].unique())
    total_master_stations = len(master_ids)
    
    # 2. EXTRACT EXCEL SPI
    files = glob.glob(os.path.join(SPI_DIR, "*.xls*"))
    files_dict = {y: [f for f in files if str(y) in os.path.basename(f)][0] for y in range(2021, 2026) if [f for f in files if str(y) in os.path.basename(f)]}
    
    all_data = []
    for y, fpath in files_dict.items():
        xl = pd.ExcelFile(fpath)
        a_sheet = [s for s in xl.sheet_names if 'analisis' in s.lower()]
        f_sheet = [s for s in xl.sheet_names if 'prakiraan' in s.lower()]
        if a_sheet: all_data.append(parse_sheet(fpath, a_sheet[0], y, 'ANALYSIS'))
        if f_sheet: all_data.append(parse_sheet(fpath, f_sheet[0], y, 'FORECAST'))
        
    df_raw = pd.concat(all_data, ignore_index=True)
    df_raw['spi_value'] = df_raw['spi_value_raw'].apply(clean_value)
    df_raw['spi_category_original'] = df_raw['spi_category_source'].apply(clean_category)
    df_raw['spi_warning_status'] = df_raw['spi_value'].apply(get_warning_status)
    df_raw['warning_color'] = df_raw['spi_warning_status'].apply(get_warning_color)
    df_raw['target_period'] = pd.to_datetime(df_raw['year'].astype(str) + '-' + df_raw['month'].astype(str).str.zfill(2) + '-01')
    
    df_raw['station_id_normalized'] = df_raw['source_station_id'].astype(str).str.strip().str.upper()

    # 3. TIER 2 - LOAD mapping_tambahan.xlsx
    mapping_path = os.path.join(BASE_DIR, 'mapping_tambahan.xlsx')
    ref_records = []
    debug_info = []
    if os.path.exists(mapping_path):
        ref_df = pd.read_excel(mapping_path)
        ref_df.columns = ref_df.columns.astype(str).str.strip().str.lower()
        debug_info.append(f"Ref_df loaded. Columns: {list(ref_df.columns)}")
        
        if 'usable_for_cews' in ref_df.columns:
            u_vals = ref_df['usable_for_cews'].unique().tolist()
            debug_info.append(f"Unique usable_for_cews values: {u_vals}")
            ref_df = ref_df[ref_df['usable_for_cews'].astype(str).str.upper().str.strip().isin(['TRUE', '1', 'YES', 'TRUE.0', 'T'])]
            debug_info.append(f"Ref_df size after usable filter: {len(ref_df)}")
            
        if 'station_id' in ref_df.columns:
            ref_df = ref_df[ref_df['station_id'].notna()]
            debug_info.append(f"Ref_df size after station_id notna: {len(ref_df)}")
            ref_df['station_id_normalized'] = ref_df['station_id'].astype(str).str.strip().str.upper()
            ref_df = ref_df[ref_df['station_id_normalized'].isin(master_ids)]
            debug_info.append(f"Ref_df size after master_ids filter: {len(ref_df)}")
            ref_records = ref_df.to_dict(orient='records')
            for i, r in enumerate(ref_records[:10]):
                debug_info.append(f"Record {i}: nopos='{r.get('source_nopos')}', key='{r.get('source_key')}', name='{r.get('source_name')}', id='{r.get('station_id')}'")
        else:
            debug_info.append("station_id column NOT FOUND in ref_df!")
            
    def match_reference(sid_norm, sname):
        for r in ref_records:
            snopos = str(r.get('source_nopos', '')).strip()
            if snopos.endswith('.0'): snopos = snopos[:-2]
            skey = str(r.get('source_key', '')).strip()
            if skey.endswith('.0'): skey = skey[:-2]
            if snopos.upper() == sid_norm: return r
            if skey.upper() == sid_norm: return r
        if sname:
            sname_norm = str(sname).strip().upper()
            for r in ref_records:
                if str(r.get('source_name', '')).strip().upper() == sname_norm: return r
                variants = str(r.get('source_name_variants', '')).upper().split(',')
                if sname_norm in [v.strip() for v in variants]: return r
        return None

    # 12. FORENSIC REMAPPING REGISTRY
    registry = df_raw[['source_year', 'source_file', 'source_sheet', 'source_nopos', 'source_station_id', 'source_station_name', 'source_latitude', 'source_longitude', 'station_id_normalized']].drop_duplicates().copy()
    
    registry['station_id_master'] = None
    registry['mapping_status_final'] = None
    registry['mapping_reference_status'] = None
    registry['mapping_method'] = None
    registry['mapping_note'] = None
    registry['distance_km'] = None
    
    for idx, row in registry.iterrows():
        sid_norm = row['station_id_normalized']
        sname = str(row['source_station_name']).strip().upper()
        slat = row['source_latitude']
        slon = row['source_longitude']
        
        # LEVEL 0 - DETERMINISTIC RESOLUTION (Untuk 3 Kasus Ambigu)
        resolved = False
        if sid_norm == '21010701A':
            if any(x in sname for x in ['BINTAN UTARA', 'SUNGAI JERAM', 'LANCANG KUNING']):
                registry.at[idx, 'station_id_master'] = '21010701A'
                registry.at[idx, 'mapping_status_final'] = 'RESOLVED_BY_NAME_COORDINATE'
                resolved = True
            elif any(x in sname for x in ['KUNDUR UTARA', 'URUNG', 'KANTOR CAMAT KUNDUR', 'KUNDUR']):
                dist = haversine(slat, slon, 0.78583, 103.4767)
                registry.at[idx, 'station_id_master'] = '21020701A'
                registry.at[idx, 'mapping_status_final'] = 'RESOLVED_BY_NAME_COORDINATE'
                registry.at[idx, 'distance_km'] = dist
                resolved = True
                
        elif sid_norm == '21010601A':
            if any(x in sname for x in ['BATU 18', 'KIJANG']):
                registry.at[idx, 'station_id_master'] = '21010601A'
                registry.at[idx, 'mapping_status_final'] = 'RESOLVED_BY_NAME_COORDINATE'
                resolved = True
            elif any(x in sname for x in ['BURU']):
                dist = haversine(slat, slon, 0.89694, 103.4953)
                registry.at[idx, 'station_id_master'] = '21020601A'
                registry.at[idx, 'mapping_status_final'] = 'RESOLVED_BY_NAME_COORDINATE'
                registry.at[idx, 'distance_km'] = dist
                resolved = True
                
        elif sid_norm == '21040203A':
            if any(x in sname for x in ['DINAS PERTANIAN', 'DAIK LINGGA', 'LINGGA']):
                registry.at[idx, 'station_id_master'] = '21040203A'
                registry.at[idx, 'mapping_status_final'] = 'RESOLVED_BY_NAME_COORDINATE'
                resolved = True
            elif any(x in sname for x in ['DUARA']):
                dist = haversine(slat, slon, -0.06719, 104.59671)
                registry.at[idx, 'station_id_master'] = '21040501A'
                registry.at[idx, 'mapping_status_final'] = 'RESOLVED_BY_NAME_COORDINATE'
                registry.at[idx, 'distance_km'] = dist
                resolved = True

        if resolved: continue

        # LEVEL 1 - EXACT
        if sid_norm in master_ids:
            registry.at[idx, 'station_id_master'] = sid_norm
            registry.at[idx, 'mapping_status_final'] = 'EXACT_MASTER'
            registry.at[idx, 'mapping_method'] = 'EXACT_ID'
        else:
            # LEVEL 2 - REFERENCE
            match = match_reference(sid_norm, sname)
            if idx < 10:
                debug_info.append(f"Attempting to match: sid_norm='{sid_norm}', sname='{sname}'. Match found? {'YES' if match else 'NO'}")
            if match:
                registry.at[idx, 'station_id_master'] = match['station_id_normalized']
                registry.at[idx, 'mapping_status_final'] = 'REFERENCE_TO_MASTER'
                registry.at[idx, 'mapping_reference_status'] = match.get('mapping_status', '')
                registry.at[idx, 'mapping_method'] = match.get('mapping_method', '')
                registry.at[idx, 'mapping_note'] = match.get('mapping_note', '')
                registry.at[idx, 'distance_km'] = match.get('distance_km', np.nan)
            else:
                registry.at[idx, 'mapping_status_final'] = 'UNRESOLVED'
                registry.at[idx, 'mapping_method'] = 'UNRESOLVED'

    # 13. CROSS-YEAR CONSISTENCY
    conflict_sources = set()
    for sid in registry['source_station_id'].unique():
        df_sid = registry[(registry['source_station_id'] == sid) & (registry['mapping_status_final'] != 'RESOLVED_BY_NAME_COORDINATE')]
        masters = df_sid['station_id_master'].dropna().unique()
        if len(masters) > 1:
            conflict_sources.add(sid)
            
    if conflict_sources:
        mask = registry['source_station_id'].isin(conflict_sources) & (registry['mapping_status_final'] != 'RESOLVED_BY_NAME_COORDINATE')
        registry.loc[mask, 'mapping_status_final'] = 'CROSS_YEAR_MAPPING_CONFLICT'
        registry.loc[mask, 'station_id_master'] = None
        
    registry.to_parquet(OUT_REGISTRY)
    
    # Merge registry back to df_raw
    df_raw = pd.merge(
        df_raw, 
        registry[['source_file', 'source_sheet', 'source_station_id', 'source_station_name', 'station_id_master', 'mapping_status_final', 'mapping_reference_status', 'mapping_method', 'mapping_note', 'distance_km']], 
        on=['source_file', 'source_sheet', 'source_station_id', 'source_station_name'], 
        how='left'
    )
    
    # 14. CEK DUPLIKASI SETELAH REMAPPING
    df_valid = df_raw[df_raw['mapping_status_final'].isin(['EXACT_MASTER', 'REFERENCE_TO_MASTER', 'RESOLVED_BY_NAME_COORDINATE'])].copy()
    dups = df_valid.duplicated(subset=['station_id_master', 'target_period', 'spi_type'], keep=False)
    
    ambig_src = set()
    if dups.any():
        ambig_src = set(df_valid[dups]['source_station_id'].unique())
        df_raw.loc[df_raw['source_station_id'].isin(ambig_src), 'mapping_status_final'] = 'AMBIGUOUS_MAPPING'
        df_valid = df_raw[df_raw['mapping_status_final'].isin(['EXACT_MASTER', 'REFERENCE_TO_MASTER', 'RESOLVED_BY_NAME_COORDINATE'])].copy()

    # 10. EXCLUDED STATIONS
    df_excluded = df_raw[~df_raw['mapping_status_final'].isin(['EXACT_MASTER', 'REFERENCE_TO_MASTER', 'RESOLVED_BY_NAME_COORDINATE'])].copy()
    df_excluded['exclusion_reason'] = df_excluded['mapping_status_final']
    
    ex_cols = ['source_station_id', 'station_id_normalized', 'source_station_name', 'source_file', 'source_sheet', 'source_year', 'exclusion_reason']
    ex_cols = [c for c in ex_cols if c in df_excluded.columns]
    df_excluded[ex_cols].drop_duplicates().to_parquet(OUT_EXCLUDED)
    
    # 15. REBUILD DATASET FINAL -> station_id diganti dengan station_id_master
    df_valid['station_id'] = df_valid['station_id_master']
    
    # 17. METADATA FINAL DARI MASTER
    meta_sub = meta[['station_id_normalized', 'station_name', 'latitude', 'longitude', 'elevation_m', 'region', 'province', 'regency', 'NOZOM_PROV']].rename(columns={'station_id_normalized': 'station_id'})
    
    # 16. HTH INTEGRATION & FINAL DATASET
    hth_path = os.path.join(BASE_DIR, 'hth_daily_2021_2025.parquet')
    if os.path.exists(hth_path):
        hth = pd.read_parquet(hth_path)
        hth['station_id'] = hth['station_id'].astype(str).str.strip().str.upper()
        hth['year'] = hth['date'].dt.year
        hth['month'] = hth['date'].dt.month
        hth_snap = hth.sort_values('date').groupby(['station_id', 'year', 'month']).tail(1)
        hth_snap = hth_snap[['station_id', 'year', 'month', 'date', 'hth_days', 'hth_status', 'hth_source', 'hth_uncertain']].rename(columns={'date': 'hth_snapshot_date'})
        hth_snap['target_period'] = pd.to_datetime(hth_snap['year'].astype(str) + '-' + hth_snap['month'].astype(str).str.zfill(2) + '-01')
        hth_snap.to_parquet(OUT_HTH_SNAP)
    else:
        hth_snap = pd.DataFrame(columns=['station_id', 'target_period'])
        
    df_analysis = df_valid[df_valid['spi_type'] == 'ANALYSIS'].drop_duplicates(subset=['station_id', 'target_period'])
    df_forecast = df_valid[df_valid['spi_type'] == 'FORECAST'].drop_duplicates(subset=['station_id', 'target_period'])
    
    df_a_out = pd.merge(df_analysis, meta_sub, on='station_id', how='left')
    df_f_out = pd.merge(df_forecast, meta_sub, on='station_id', how='left')
    
    cols_base = ['station_id', 'source_station_id', 'station_name', 'year', 'month', 'target_period', 
                 'spi_value', 'spi_category_original', 'spi_warning_status', 'warning_color', 'spi_scale_months',
                 'region', 'province', 'regency', 'latitude', 'longitude', 'elevation_m', 'NOZOM_PROV',
                 'source_file', 'source_sheet', 'spi_type', 'mapping_status_final', 'mapping_method']
    cols_a = [c for c in cols_base if c in df_a_out.columns]
    df_a_out[cols_a].to_parquet(OUT_ANALYSIS)
    df_f_out[[c for c in cols_base if c in df_f_out.columns]].to_parquet(OUT_FORECAST)
    pd.concat([df_a_out[cols_a], df_f_out[[c for c in cols_base if c in df_f_out.columns]]], ignore_index=True).to_parquet(OUT_CEWS)
    
    drought_raw = pd.merge(hth_snap, df_analysis.drop(columns=['year', 'month', 'spi_value_raw', 'spi_category_source'], errors='ignore'), on=['station_id', 'target_period'], how='outer')
    drought_raw['has_spi'] = drought_raw['spi_value'].notna()
    drought_raw['spi_warning_status'] = drought_raw['spi_warning_status'].fillna('SPI_NOT_AVAILABLE')
    drought_raw = drought_raw[drought_raw['station_id'].isin(master_ids)]
    drought_final = pd.merge(drought_raw, meta_sub, on='station_id', how='left')
    drought_final = drought_final.drop(columns=['spi_value_raw', 'spi_category_source'], errors='ignore')
    drought_final.to_parquet(OUT_DROUGHT)
    
    # 18. FINAL ASSERTION
    out_ids = set(drought_final['station_id'].unique()).union(set(df_a_out['station_id'].unique())).union(set(df_f_out['station_id'].unique()))
    assert out_ids.issubset(master_ids), "CRITICAL: Terdapat output dengan station_id yang tidak ada di MASTER!"
    
    # 19. LAPORAN AUDIT
    master_with_a = set(df_analysis['station_id'].unique())
    master_with_f = set(df_forecast['station_id'].unique())
    master_without = master_ids - (master_with_a.union(master_with_f))
    
    exact_count = df_raw[df_raw['mapping_status_final'] == 'EXACT_MASTER']['source_station_id'].nunique()
    ref_count = df_raw[df_raw['mapping_status_final'] == 'REFERENCE_TO_MASTER']['source_station_id'].nunique()
    unresolved_count = df_raw[df_raw['mapping_status_final'] == 'UNRESOLVED']['source_station_id'].nunique()
    excluded_count = df_excluded['source_station_id'].nunique()
    
    with open(OUT_REPORT, 'w', encoding='utf-8') as f:
        f.write("# FINAL STATION MAPPING AUDIT (mapping_tambahan.xlsx)\n\n")
        f.write(f"Generated at: {datetime.datetime.now().isoformat()}\n\n")
        
        f.write("## 0. DEBUG INFO MAPPING TAMBAHAN\n")
        for d in debug_info:
            f.write(f"- {d}\n")
        f.write("\n")
        
        f.write("## 19. RINGKASAN MAPPING\n")
        f.write(f"- TOTAL MASTER STATION           : {total_master_stations}\n")
        f.write(f"- MASTER WITH SPI ANALYSIS       : {len(master_with_a)}\n")
        f.write(f"- MASTER WITH SPI FORECAST       : {len(master_with_f)}\n")
        f.write(f"- MASTER WITHOUT SPI             : {len(master_without)}\n")
        f.write(f"- EXACT MASTER MATCH             : {exact_count}\n")
        f.write(f"- MATCHED VIA mapping_tambahan   : {ref_count}\n")
        
        resolved_count = df_raw[df_raw['mapping_status_final'] == 'RESOLVED_BY_NAME_COORDINATE']['source_station_id'].nunique()
        f.write(f"- RESOLVED AMBIGUOUS BY NAME/COORDINATE : {resolved_count}\n")
        
        f.write("\nBreakdown reference:\n")
        for m_method in df_raw[df_raw['mapping_status_final'] == 'REFERENCE_TO_MASTER']['mapping_reference_status'].unique():
            if pd.notna(m_method):
                mc = df_raw[(df_raw['mapping_status_final'] == 'REFERENCE_TO_MASTER') & (df_raw['mapping_reference_status'] == m_method)]['source_station_id'].nunique()
                f.write(f"  - {m_method}: {mc}\n")
                
        f.write(f"\n- UNRESOLVED SOURCE              : {unresolved_count}\n")
        f.write(f"- EXCLUDED OUTSIDE MASTER        : {excluded_count}\n")
        f.write(f"- AMBIGUOUS REMAINING            : {len(ambig_src)}\n")
        f.write(f"- CROSS-YEAR CONFLICT            : {len(conflict_sources)}\n\n")
        
        # 20. STATION MASTER TANPA SPI
        f.write("## 20. STATION MASTER YANG BELUM MEMILIKI SPI\n")
        b_data = []
        for mid in master_without:
            s_name = meta[meta['station_id_normalized'] == mid]['station_name'].iloc[0] if len(meta[meta['station_id_normalized'] == mid]) > 0 else ''
            h_hth = mid in hth_snap['station_id'].unique() if not hth_snap.empty else False
            
            # Determine reason
            if mid in [r.get('station_id_normalized') for r in ref_records]:
                reason = "SOURCE_NOT_FOUND" # ada di kamus, tapi SPI nya ga ada di excel
            else:
                reason = "TRUE_SPI_NOT_AVAILABLE" # ga ada di kamus dan ga exact match
            
            b_data.append({
                'station_id': mid,
                'station_name': s_name,
                'has_spi_analysis': False,
                'has_spi_forecast': False,
                'has_hth': h_hth,
                'has_ch': True,
                'mapping_search_result': reason
            })
        if b_data: f.write(pd.DataFrame(b_data).to_csv(sep='|', index=False))
        f.write("\n\n")
        
        # 21. MAPPING YANG BERHASIL DISELAMATKAN
        f.write("## 21. MAPPING YANG BERHASIL DISELAMATKAN (VIA mapping_tambahan.xlsx)\n")
        d_data = []
        df_saved = registry[registry['mapping_status_final'] == 'REFERENCE_TO_MASTER']
        for _, row in df_saved.iterrows():
            d_data.append({
                'source_nopos': row['source_nopos'],
                'source_station_id': row['source_station_id'],
                'source_station_name': row['source_station_name'],
                'source_year': row['source_year'],
                'station_id_master': row['station_id_master'],
                'station_name_master': meta[meta['station_id_normalized'] == row['station_id_master']]['station_name'].iloc[0] if pd.notna(row['station_id_master']) else '',
                'mapping_status_reference': row['mapping_reference_status'],
                'mapping_method': row['mapping_method'],
                'distance_km': row['distance_km'],
                'mapping_note': row['mapping_note']
            })
        if d_data: f.write(pd.DataFrame(d_data).to_csv(sep='|', index=False))
        f.write("\n\n")
        
    print(f"\nSelesai! Laporan Audit disimpan di: {OUT_REPORT}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open(os.path.join(BASE_DIR, "pipeline_error.txt"), "w") as f:
            f.write(traceback.format_exc())
        print("Script error! Check pipeline_error.txt")
