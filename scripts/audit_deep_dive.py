import os
import glob
import pandas as pd
import openpyxl

print("=== 1. SEARCH FOR 2026.10 / 2026.11 FILES ===")
for root, _, files in os.walk('.'):
    if any(k in root for k in ['.git', 'node_modules', 'reports/maintenance']):
        continue
    for f in files:
        if any(term in f for term in ['2026.10', '2026.11', '2026_10', '2026_11', 'Oktober', 'November']):
            print(f"  {os.path.join(root, f)}")

print("\n=== 2. INSPECT SPI SOURCE EXCEL (2026_SPI.xlsx) ===")
for spi_path in ['tambahan/baru/2026_SPI.xlsx', 'tambahan/template_data_input/spi/2026_SPI.xlsx']:
    if os.path.exists(spi_path):
        print(f"\nAnalyzing {spi_path}:")
        wb = openpyxl.load_workbook(spi_path, data_only=True)
        for sname in wb.sheetnames:
            ws = wb[sname]
            print(f"  Sheet: {sname} | Max Row: {ws.max_row}, Max Col: {ws.max_column}")
            # print sample rows
            sample = []
            for r in range(1, min(6, ws.max_row + 1)):
                row_vals = [ws.cell(r, c).value for c in range(1, min(10, ws.max_column + 1))]
                sample.append(row_vals)
            print(f"    Header/First rows: {sample[:2]}")

print("\n=== 3. INSPECT CH TEMPLATE EXCEL FILES IN tambahan/template_data_input/ch/ ===")
ch_dir = 'tambahan/template_data_input/ch'
if os.path.exists(ch_dir):
    for f in sorted(os.listdir(ch_dir)):
        if f.endswith('.xlsx'):
            fp = os.path.join(ch_dir, f)
            wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
            print(f"\nFile: {f} ({len(wb.sheetnames)} sheets: {wb.sheetnames})")
            # Inspect first sheet
            ws = wb[wb.sheetnames[0]]
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                print(f"  First sheet '{wb.sheetnames[0]}' total rows: {len(rows)}")
                print(f"  Header row: {rows[0][:8]}")
                # find date column and range
                dates = [r[0] for r in rows[1:] if r and r[0] is not None]
                if dates:
                    print(f"  Date range: {dates[0]} to {dates[-1]}")

