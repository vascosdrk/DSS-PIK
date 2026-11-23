import os
import openpyxl

print("=== INSPECTING scratch/inspect_ch FILES ===")
files = os.listdir('scratch/inspect_ch')
for f in sorted(files):
    fp = os.path.join('scratch/inspect_ch', f)
    sz = os.path.getsize(fp)
    print(f"\n--- File: {f} ({sz:,} bytes) ---")
    try:
        wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
        print(f"  Sheets ({len(wb.sheetnames)}): {wb.sheetnames}")
        for sname in wb.sheetnames[:5]:
            ws = wb[sname]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            header = rows[0]
            # find date column
            date_vals = [r[0] for r in rows[1:] if r and r[0] is not None]
            min_d = date_vals[0] if date_vals else 'None'
            max_d = date_vals[-1] if date_vals else 'None'
            print(f"    Sheet '{sname}': {len(rows)} rows | Date range: {min_d} to {max_d}")
    except Exception as e:
        print(f"  Error loading {f}: {e}")

