import xlrd
import pandas as pd
from datetime import datetime

print("Reading Timeseries_Kepri.xls with xlrd...")
book = xlrd.open_workbook('tambahan/Timeseries_Kepri.xls', on_demand=True)
sheet = book.sheet_by_name('HARIAN')
print(f"Sheet 'HARIAN' dimensions: {sheet.nrows} rows, {sheet.ncols} cols")

# Inspect row 0 to 5
for r in range(min(5, sheet.nrows)):
    print(f"Row {r}: {sheet.row_values(r)[:10]}")

# Inspect last 5 rows
print("\nLast 5 rows:")
for r in range(max(0, sheet.nrows - 5), sheet.nrows):
    # Convert date if first col is date
    val0 = sheet.cell_value(r, 0)
    date_str = str(val0)
    if sheet.cell_type(r, 0) == xlrd.XL_CELL_DATE:
        dt = xlrd.xldate_as_datetime(val0, book.datemode)
        date_str = dt.strftime('%Y-%m-%d')
    print(f"Row {r} (col0={date_str}): {sheet.row_values(r)[:10]}")

