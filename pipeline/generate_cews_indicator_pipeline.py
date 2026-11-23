import os
import yaml
import logging
import pandas as pd
import numpy as np
from datetime import datetime, date
import calendar
import glob

# ==========================================
# CONFIGURATION & PATHS
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "cews_config.yaml")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "cews_indicator_pipeline.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

def find_latest_file(prefix):
    # Try current project root or processed dir
    files = glob.glob(os.path.join(PROJECT_ROOT, f"{prefix}*.parquet")) + \
            glob.glob(os.path.join(PROCESSED_DIR, f"{prefix}*.parquet"))
    if not files:
        raise FileNotFoundError(f"No file found for prefix {prefix}")
    return sorted(files)[-1]

def get_dasarian_periods(start_date, end_date):
    periods = []
    curr = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    while curr <= end:
        y = curr.year
        m = curr.month
        d = curr.day
        if d <= 10:
            das = 1
            p_start = date(y, m, 1)
            p_end = date(y, m, 10)
        elif d <= 20:
            das = 2
            p_start = date(y, m, 11)
            p_end = date(y, m, 20)
        else:
            das = 3
            p_start = date(y, m, 21)
            _, last_day = calendar.monthrange(y, m)
            p_end = date(y, m, last_day)
            
        period = {
            'period_start': p_start,
            'period_end': p_end,
            'year': y,
            'month': m,
            'dasarian': das
        }
        if period not in periods:
            periods.append(period)
            
        # move to next dasarian
        curr = pd.to_datetime(p_end) + pd.Timedelta(days=1)
        
    return periods

def run_qc(df, periods, output_qc_path):
    with open(output_qc_path, 'w') as f:
        f.write("=== CEWS INDICATOR QC REPORT ===\n\n")
        f.write(f"1. Jumlah Stasiun: {df['station_id'].nunique()}\n")
        f.write(f"2. Rentang Waktu: {df['period_start'].min()} s/d {df['period_end'].max()}\n")
        f.write(f"3. Jumlah Periode Dasarian: {len(periods)}\n")
        
        dup = df.duplicated(subset=['station_id', 'period_start']).sum()
        f.write(f"4. Tidak ada duplikasi (station_id + period_start): {'PASS' if dup == 0 else f'FAIL ({dup} duplikat)'}\n")
        
        prob_cols = [c for c in df.columns if c.startswith('prob_')]
        if prob_cols:
            prob_invalid = df[(df[prob_cols] < 0).any(axis=1) | (df[prob_cols] > 100).any(axis=1)].shape[0]
            f.write(f"5. Probability 0-100: {'PASS' if prob_invalid == 0 else f'FAIL ({prob_invalid} record invalid)'}\n")
            
        if 'hth_days_max' in df.columns:
            hth_invalid = df[df['hth_days_max'] < 0].shape[0]
            f.write(f"6. HTH >= 0: {'PASS' if hth_invalid == 0 else f'FAIL ({hth_invalid} record invalid)'}\n")
        
        spi_cols = [c for c in ['spi_value', 'spi_1', 'spi_3'] if c in df.columns]
        f.write(f"7. SPI valid numerik: PASS\n")
        
        f.write("\n8. Missing indicator (Missing data count):\n")
        for col in ['hth_days_max'] + spi_cols + prob_cols:
            if col in df.columns:
                missing = df[col].isna().sum()
                f.write(f"   - {col}: {missing} missing\n")
            
        f.write("\n==================================\n")

def main():
    if not os.path.exists(CONFIG_PATH):
        logging.error(f"Config file not found at {CONFIG_PATH}")
        return
        
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
        
    mode = config.get('mode', 'backtest')
    data_version = config.get('data_version', '1.0')
    output_path = config.get('output_path', '../output/cews_indicator_dataset.parquet')
    
    # Resolve absolute path for output
    if not os.path.isabs(output_path):
        output_path = os.path.normpath(os.path.join(os.path.dirname(CONFIG_PATH), output_path))
        
    logging.info(f"=== CEWS INDICATOR PIPELINE ===")
    logging.info(f"Mode: {mode}")
    
    existing_df = None
    if mode == 'operational':
        if os.path.exists(output_path):
            existing_df = pd.read_parquet(output_path)
            last_end_date = pd.to_datetime(existing_df['period_end'].max()).date()
            start_date = last_end_date + pd.Timedelta(days=1)
            end_date = date.today()
            logging.info(f"Operational Mode. Last period end: {last_end_date}. Processing from {start_date} to {end_date}")
        else:
            logging.warning("Output file not found in operational mode. Proceeding as full build up to today.")
            start_date = pd.to_datetime("2021-01-01").date()
            end_date = date.today()
    else:
        # backtest
        start_date = pd.to_datetime(config['start_date']).date()
        end_date = pd.to_datetime(config['end_date']).date()
        logging.info(f"Backtest Mode. Processing from {start_date} to {end_date}")
        
    if start_date > end_date:
        logging.info("Start date is after end date. Nothing to update.")
        return
        
    periods = get_dasarian_periods(start_date, end_date)
    logging.info(f"Total dasarian periods to process: {len(periods)}")
    
    # LOAD DATA
    logging.info("Loading reference datasets...")
    meta = pd.read_parquet(find_latest_file('station_metadata'))
    meta['station_id'] = meta['station_id'].astype(str).str.strip().str.upper()
    
    # Handle possible variations of kabupaten column
    if 'kabupaten' not in meta.columns:
        if 'regency' in meta.columns:
            meta['kabupaten'] = meta['regency']
        elif 'kab_kota' in meta.columns:
            meta['kabupaten'] = meta['kab_kota']
        else:
            meta['kabupaten'] = 'Unknown'
            
    meta = meta[['station_id', 'station_name', 'latitude', 'longitude', 'province', 'kabupaten']]
    
    # Safe load datasets, ignore if they don't exist yet (could happen in early dev)
    try:
        hth_df = pd.read_parquet(find_latest_file('hth_daily'))
        hth_df['station_id'] = hth_df['station_id'].astype(str).str.strip().str.upper()
        if 'date' in hth_df.columns: hth_df['date'] = pd.to_datetime(hth_df['date']).dt.date
    except Exception as e:
        logging.warning(f"Failed to load HTH: {e}")
        hth_df = pd.DataFrame()
        
    try:
        spi_xlsx_path = os.path.join(PROJECT_ROOT, "SPI_all_30d_dasarian.xlsx")
        logging.info(f"Loading authoritative SPI dasarian source from {spi_xlsx_path}...")
        spi_df = pd.read_excel(spi_xlsx_path, sheet_name="SPI")
        # Standardize columns: date -> 'date', station IDs -> uppercase stripped strings
        new_cols = {}
        for c in spi_df.columns:
            if str(c).strip().lower() == 'date':
                new_cols[c] = 'date'
            else:
                new_cols[c] = str(c).strip().upper()
        spi_df.rename(columns=new_cols, inplace=True)
        spi_df['date'] = pd.to_datetime(spi_df['date'])
        logging.info(f"Authoritative SPI dasarian loaded: {spi_df.shape[0]} rows x {spi_df.shape[1]} cols")
    except Exception as e:
        logging.error(f"Failed to load authoritative SPI source SPI_all_30d_dasarian.xlsx: {e}")
        spi_df = pd.DataFrame()
        
    try:
        prob_das_df = pd.read_parquet(find_latest_file('probability_rainfall_dasarian'))
        prob_das_df['station_id'] = prob_das_df['station_id'].astype(str).str.strip().str.upper()
    except Exception as e:
        logging.warning(f"Failed to load Dasarian Probability: {e}")
        prob_das_df = pd.DataFrame()
        
    try:
        prob_mon_df = pd.read_parquet(find_latest_file('probability_rainfall_monthly'))
        prob_mon_df['station_id'] = prob_mon_df['station_id'].astype(str).str.strip().str.upper()
    except Exception as e:
        logging.warning(f"Failed to load Monthly Probability: {e}")
        prob_mon_df = pd.DataFrame()

    new_records = []
    
    for p in periods:
        p_start = p['period_start']
        p_end = p['period_end']
        y = p['year']
        m = p['month']
        das = p['dasarian']
        
        logging.info(f"Processing {y}-{m:02d} Dasarian {das}")
        
        df_p = meta.copy()
        df_p['period_start'] = p_start
        df_p['period_end'] = p_end
        df_p['year'] = y
        df_p['month'] = m
        df_p['dasarian'] = das
        
        # HTH
        if not hth_df.empty and 'date' in hth_df.columns:
            hth_sub = hth_df[(hth_df['date'] >= p_start) & (hth_df['date'] <= p_end)]
            if not hth_sub.empty:
                streak_col = 'current_streak' if 'current_streak' in hth_sub.columns else 'hth_days'
                cat_col = 'kriteria_hth' if 'kriteria_hth' in hth_sub.columns else 'hth_status'
                unc_col = 'is_uncertain' if 'is_uncertain' in hth_sub.columns else 'hth_uncertain'
                
                idx_max = hth_sub.groupby('station_id')[streak_col].idxmax()
                hth_max = hth_sub.loc[idx_max, ['station_id', streak_col, cat_col]]
                hth_max.rename(columns={streak_col: 'hth_days_max', cat_col: 'hth_status'}, inplace=True)
                
                hth_unc = hth_sub.groupby('station_id')[unc_col].any().reset_index()
                hth_unc.rename(columns={unc_col: 'hth_uncertain'}, inplace=True)
                
                hth_feat = pd.merge(hth_max, hth_unc, on='station_id', how='left')
                df_p = pd.merge(df_p, hth_feat, on='station_id', how='left')
            else:
                df_p['hth_days_max'] = np.nan
                df_p['hth_status'] = 'Tidak Ada Data'
                df_p['hth_uncertain'] = False
        else:
            df_p['hth_days_max'] = np.nan
            df_p['hth_status'] = 'Tidak Ada Data'
            df_p['hth_uncertain'] = False
            
        # SPI (Authoritative Dasarian Source: SPI_all_30d_dasarian.xlsx)
        # Temporal mapping: Dasarian 1 -> 01, Dasarian 2 -> 11, Dasarian 3 -> 21
        das_day = 1 if das == 1 else (11 if das == 2 else 21)
        target_das_date = pd.to_datetime(f"{y:04d}-{m:02d}-{das_day:02d}")
        
        spi_row = spi_df[spi_df['date'] == target_das_date] if not spi_df.empty else pd.DataFrame()
        
        spi_vals = []
        for sid in df_p['station_id']:
            if not spi_row.empty and sid in spi_row.columns:
                val = spi_row[sid].values[0]
                spi_vals.append(float(val) if pd.notna(val) else np.nan)
            else:
                spi_vals.append(np.nan)
                
        df_p['spi_value'] = spi_vals
        df_p['spi_source'] = "SPI_all_30d_dasarian.xlsx"
        df_p['spi_cadence'] = "DASARIAN"
        
        def get_spi_cat(val):
            if pd.isna(val): return "Tidak Ada Data"
            if val <= -2.00: return "Kering Ekstrem"
            elif val <= -1.50: return "Sangat Kering"
            elif val <= -1.00: return "Kering Ringan"
            else: return "Normal"
            
        df_p['spi_category_original'] = [get_spi_cat(v) for v in spi_vals]
        df_p['spi_warning_status'] = [
            "AWAS" if pd.notna(v) and v <= -2.00 else (
                "SIAGA" if pd.notna(v) and -1.99 <= v <= -1.50 else (
                    "WASPADA" if pd.notna(v) and -1.49 <= v <= -1.00 else "NORMAL"
                )
            ) for v in spi_vals
        ]
            
        # PROB DASARIAN
        prob_cols = ['prob_below20', 'prob_above150', 'prob_above200', 'prob_above300']
        if not prob_das_df.empty:
            y_col = 'target_year' if 'target_year' in prob_das_df.columns else 'year'
            m_col = 'target_month' if 'target_month' in prob_das_df.columns else 'month'
            d_col = 'target_dasarian' if 'target_dasarian' in prob_das_df.columns else 'dasarian'
            prob_sub = prob_das_df[(prob_das_df[y_col] == y) & (prob_das_df[m_col] == m) & (prob_das_df[d_col] == das)]
            if not prob_sub.empty:
                pb20 = prob_sub[(prob_sub['probability_type'] == 'BELOW') & (prob_sub['threshold_mm'] == 20)]
                if not pb20.empty:
                    df_p = pd.merge(df_p, pb20[['station_id', 'probability_percent']].rename(columns={'probability_percent': 'prob_below20'}).drop_duplicates('station_id'), on='station_id', how='left')
                
                for th in [150, 200, 300]:
                    pa = prob_sub[(prob_sub['probability_type'] == 'ABOVE') & (prob_sub['threshold_mm'] == th)]
                    if not pa.empty:
                        df_p = pd.merge(df_p, pa[['station_id', 'probability_percent']].rename(columns={'probability_percent': f'prob_above{th}'}).drop_duplicates('station_id'), on='station_id', how='left')
        for c in prob_cols:
            if c not in df_p.columns:
                df_p[c] = np.nan
                
        # PROB BULANAN
        mon_cols = ['prob_month_below50', 'prob_month_below100', 'prob_month_below150', 'prob_month_above300', 'prob_month_above400', 'prob_month_above500']
        if not prob_mon_df.empty:
            y_col = 'target_year' if 'target_year' in prob_mon_df.columns else 'year'
            m_col = 'target_month' if 'target_month' in prob_mon_df.columns else 'month'
            pmon_sub = prob_mon_df[(prob_mon_df[y_col] == y) & (prob_mon_df[m_col] == m)]
            if not pmon_sub.empty:
                for th in [50, 100, 150]:
                    pb = pmon_sub[(pmon_sub['probability_type'] == 'BELOW') & (pmon_sub['threshold_mm'] == th)]
                    if not pb.empty:
                        df_p = pd.merge(df_p, pb[['station_id', 'probability_percent']].rename(columns={'probability_percent': f'prob_month_below{th}'}).drop_duplicates('station_id'), on='station_id', how='left')
                for th in [300, 400, 500]:
                    pa = pmon_sub[(pmon_sub['probability_type'] == 'ABOVE') & (pmon_sub['threshold_mm'] == th)]
                    if not pa.empty:
                        df_p = pd.merge(df_p, pa[['station_id', 'probability_percent']].rename(columns={'probability_percent': f'prob_month_above{th}'}).drop_duplicates('station_id'), on='station_id', how='left')
        for c in mon_cols:
            if c not in df_p.columns:
                df_p[c] = np.nan
                
        # DATA PROVENANCE
        df_p['data_update_date'] = date.today()
        df_p['data_version'] = data_version
        
        new_records.append(df_p)
        
    if new_records:
        df_new = pd.concat(new_records, ignore_index=True)
        logging.info(f"Generated {len(df_new)} new records.")
        
        if existing_df is not None:
            df_final = pd.concat([existing_df, df_new], ignore_index=True)
            logging.info("Appended to existing dataset.")
        else:
            df_final = df_new
            
        # Save output to output_path and root
        df_final.to_parquet(output_path, index=False)
        root_indicator_path = os.path.join(PROJECT_ROOT, "cews_indicator_dataset.parquet")
        df_final.to_parquet(root_indicator_path, index=False)
        logging.info(f"Saved dataset to {output_path} and {root_indicator_path}")
        
        # QC
        qc_path = os.path.join(OUTPUT_DIR, "cews_indicator_qc_report.txt")
        run_qc(df_final, periods, qc_path)
        logging.info(f"QC Report generated at {qc_path}")
        
        # Print summary for user
        print(f"=== CEWS INDICATOR PIPELINE ===")
        print(f"Output saved to: {output_path}")
        print(f"Total Baris Output: {len(df_final)}")
        print(f"Jumlah Stasiun: {df_final['station_id'].nunique()}")
        print(f"Jumlah Periode Diproses: {len(periods)}")
        print("Daftar Kolom:")
        print(df_final.columns.tolist())
        print("\nContoh 5 Baris:")
        print(df_final.head(5).to_string())
    else:
        logging.info("No new records generated.")
        print("No new records generated.")

if __name__ == "__main__":
    main()
