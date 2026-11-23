import openpyxl

wb = openpyxl.load_workbook('scratch/inspect_ch/Entry Data Pos Hujan Bintan.xlsm', data_only=True)
ws = wb['Data_Pos_Hujan']
print(f"Data_Pos_Hujan dimensions: {ws.max_row} rows, {ws.max_column} cols")
# Header row
header = [ws.cell(1, c).value for c in range(1, min(25, ws.max_column + 1))]
print("Header:", header)

# Last 10 rows
print("\nLast 10 rows:")
for r in range(max(1, ws.max_row - 10), ws.max_row + 1):
    vals = [ws.cell(r, c).value for c in range(1, min(10, ws.max_column + 1))]
    print(f"Row {r:5d}: {vals}")

