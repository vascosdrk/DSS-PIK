import xlrd
from datetime import datetime

book = xlrd.open_workbook('tambahan/Timeseries_Kepri.xls', on_demand=True)
sheet = book.sheet_by_name('HARIAN')

header = sheet.row_values(1)
stations = [(c, header[c]) for c in range(4, sheet.ncols) if header[c]]
print(f"Total stations in header: {len(stations)}")

# Check from the bottom up to see when data starts having values
last_row_with_data = None
for r in range(sheet.nrows - 1, 1, -1):
    vals = sheet.row_values(r)[4:]
    # Check if any cell has a numeric value or valid non-empty string
    non_empty = [v for v in vals if v not in ('', None)]
    if non_empty:
        # Check if there is actual observed data, not just all 'X' or '-'
        data_vals = [v for v in non_empty if v not in ('X', 'x', '-', '8888', '9999')]
        y, m, d = int(sheet.cell_value(r, 0)), int(sheet.cell_value(r, 1)), int(sheet.cell_value(r, 2))
        print(f"Row {r}: Date {y}-{m:02d}-{d:02d} | Non-empty count: {len(non_empty)} | Data vals count: {len(data_vals)} | Sample: {non_empty[:5]}")
        if not last_row_with_data and len(non_empty) > 0:
            last_row_with_data = (r, y, m, d, len(non_empty), len(data_vals))
        if y == 2026 and m in [9, 10, 11]:
            # Print details for Oct 2026
            pass
        if y == 2026 and m == 10:
            print(f"  --> Oct 2026: {y}-{m:02d}-{d:02d}: {len(non_empty)} non-empty, {len(data_vals)} data vals")

print(f"\nLast row with any value: {last_row_with_data}")

