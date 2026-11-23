import os
import openpyxl
from datetime import datetime

print("=== FAST AUDIT OF CH SOURCE FILES IN scratch/inspect_ch/ ===", flush=True)

files = [
    'Kabupaten Dabo Singkep.xlsx',
    'Kabupaten Karimun.xlsx',
    'Kabupaten Natuna.xlsx',
    'Kabupaten Tarempa.xlsx',
    'Kota Batam.xlsx',
    'Kota Tanjungpinang.xlsx',
    'Pos Hujan Tanjungpinang Oktober IiI 2026.xlsx',
    'Entry Data Pos Hujan Bintan.xlsm'
]

for f in files:
    fp = os.path.join('scratch/inspect_ch', f)
    if not os.path.exists(fp):
        print(f"File {f} not found!", flush=True)
        continue
    wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
    print(f"\n>> FILE: {f} ({len(wb.sheetnames)} sheets)", flush=True)
    for sname in wb.sheetnames:
        ws = wb[sname]
        # Read all rows into a light generator and collect 2026-10 dates
        oct_dates = {}
        last_date = None
        first_date = None
        row_count = 0
        for row in ws.iter_rows(values_only=True):
            if not row or row[0] is None:
                continue
            d = row[0]
            val = row[1] if len(row) > 1 else None
            if hasattr(d, 'year'):
                row_count += 1
                if first_date is None:
                    first_date = d
                last_date = d
                if d.year == 2026 and d.month == 10:
                    oct_dates[d.day] = val
        if row_count > 0:
            oct_non_empty = [d for d, v in oct_dates.items() if v not in (None, '', 'X', 'x')]
            max_oct = max(oct_dates.keys()) if oct_dates else 0
            max_data = max(oct_non_empty) if oct_non_empty else 0
            print(f"   Sheet: {sname:30s} | Rows: {row_count:5d} | Range: {str(first_date)[:10]} to {str(last_date)[:10]} | Oct days: {len(oct_dates)} (max={max_oct}) | Data days: {len(oct_non_empty)} (max={max_data})", flush=True)
        else:
            # Check if it's a summary or matrix sheet
            sample = list(ws.iter_rows(max_row=3, values_only=True))
            print(f"   Sheet: {sname:30s} | (Matrix/Summary sheet, sample: {sample[0] if sample else 'empty'})", flush=True)
    wb.close()

