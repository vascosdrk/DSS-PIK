import sys
sys.path.insert(0, '.')
import openpyxl
import pandas as pd
from backend.ingestion_service import parse_spi_bulanan_excel, parse_spi_parquet

print("=== AUDIT SPI VIA INGESTION PARSERS ===")

# Test SPI Excel
for spi_f in ['tambahan/baru/2026_SPI.xlsx', 'tambahan/template_data_input/spi/2026_SPI.xlsx']:
    try:
        fbytes = open(spi_f, 'rb').read()
        res = parse_spi_bulanan_excel(fbytes, spi_f, target_year=2026, sheet_preference="Analisis")
        print(f"\nFile: {spi_f} (Sheet: Analisis)")
        summ = res['summary']
        print(f"  Target Year: {summ['target_year']}")
        print(f"  Months in File: {summ['months_in_file']}")
        print(f"  Recognized Stations: {summ['total_stations_recognized']}")
        print(f"  New Records: {summ['total_new']}")
        print(f"  Updated Records: {summ['total_updated']}")
        print(f"  Identical Records: {summ['total_identical']}")
    except Exception as e:
        print(f"Error parsing {spi_f}: {e}")

# Check SPI Parquets
for p in ['data/raw/spi/dasarian/SPI_all_30d.parquet', 'data/raw/spi/dasarian/SPI_all_90d.parquet', 'data/raw/spi/bulanan/SPI_monthly.parquet']:
    try:
        fbytes = open(p, 'rb').read()
        res = parse_spi_parquet(fbytes, p, period_type="DASARIAN" if "dasarian" in p else "BULANAN", timescale="30D" if "30d" in p else "90D")
        summ = res['summary']
        print(f"\nParquet: {p}")
        print(f"  Date Range: {summ['date_range']}")
        print(f"  Stations: {summ['total_stations_recognized']}")
        print(f"  New Dates: {summ['total_new_dates']}")
        print(f"  Identical Dates: {summ['total_identical_dates']}")
        print(f"  Diff Dates: {summ['total_diff_dates']}")
    except Exception as e:
        print(f"Error parsing {p}: {e}")

