import openpyxl

wb = openpyxl.load_workbook('scratch/inspect_ch/Pos Hujan Tanjungpinang Oktober IiI 2026.xlsx', data_only=True)
ws = wb.active
print(f"Sheet dimensions: {ws.max_row} rows, {ws.max_column} cols")
for r in range(1, min(25, ws.max_row + 1)):
    row_vals = [ws.cell(r, c).value for c in range(1, min(15, ws.max_column + 1))]
    print(f"Row {r:2d}: {row_vals}")

