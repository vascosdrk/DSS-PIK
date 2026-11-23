import os
import zipfile
import pandas as pd
import openpyxl

print("=== INSPECTING tambahan/Timeseries_Kepri.xls ===")
# Note: xlrd or pandas can read xls
try:
    xl = pd.ExcelFile('tambahan/Timeseries_Kepri.xls')
    print("Sheets in Timeseries_Kepri.xls:", xl.sheet_names[:10])
except Exception as e:
    print(f"Error reading Timeseries_Kepri.xls: {e}")

print("\n=== INSPECTING tambahan/template_data_input/ch/ ===")
ch_dir = 'tambahan/template_data_input/ch'
for f in os.listdir(ch_dir):
    fp = os.path.join(ch_dir, f)
    try:
        wb = openpyxl.load_workbook(fp, read_only=True)
        print(f"File: {f} | Sheets: {wb.sheetnames[:5]}")
    except Exception as e:
        print(f"File: {f} | Error: {e}")

print("\n=== INSPECTING tambahan/baru/2026_SPI.xlsx & template_data_input/spi/2026_SPI.xlsx ===")
for p in ['tambahan/baru/2026_SPI.xlsx', 'tambahan/template_data_input/spi/2026_SPI.xlsx', 'data/raw/spi/SPI_all_30d_dasarian.xlsx']:
    if os.path.exists(p):
        try:
            wb = openpyxl.load_workbook(p, read_only=True)
            print(f"File: {p} | Sheets: {wb.sheetnames}")
        except Exception as e:
            print(f"File: {p} | Error: {e}")

