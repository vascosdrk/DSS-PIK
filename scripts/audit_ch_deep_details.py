import os
import openpyxl
import pandas as pd

print("=== DEEP AUDIT OF CH SOURCE FILES IN scratch/inspect_ch/ ===")

def inspect_sheet(fp, sname):
    wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
    ws = wb[sname]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows or len(rows) < 2:
        return None
    # find header and data
    h = rows[0]
    dates = []
    data_pts = 0
    non_empty = 0
    max_oct_day = 0
    oct_rows = 0
    for r in rows[1:]:
        if not r or r[0] is None:
            continue
        d = r[0]
        # check if date
        if hasattr(d, 'year'):
            if d.year == 2026 and d.month == 10:
                oct_rows += 1
                ch_val = r[1] if len(r) > 1 else None
                if ch_val not in (None, '', 'X', 'x'):
                    data_pts += 1
                    max_oct_day = max(max_oct_day, d.day)
            dates.append(d)
    return {
        'total_rows': len(rows),
        'min_date': dates[0] if dates else None,
        'max_date': dates[-1] if dates else None,
        'oct_rows': oct_rows,
        'oct_data_pts': data_pts,
        'max_oct_day': max_oct_day
    }

for f in sorted(os.listdir('scratch/inspect_ch')):
    fp = os.path.join('scratch/inspect_ch', f)
    if not f.endswith(('.xlsx', '.xlsm')):
        continue
    wb = openpyxl.load_workbook(fp, read_only=True)
    snames = wb.sheetnames
    wb.close()
    print(f"\n>> FILE: {f} ({len(snames)} sheets)")
    for s in snames:
        if any(ign in s.lower() for ign in ['entry', 'paste', 'sheet1']) and 'pos hujan' not in f.lower():
            continue
        res = inspect_sheet(fp, s)
        if res:
            print(f"   Sheet: {s:32s} | Max Date: {str(res['max_date'])[:10]} | Oct Rows: {res['oct_rows']} | Oct Data Pts: {res['oct_data_pts']} | Max Oct Day: {res['max_oct_day']}")

