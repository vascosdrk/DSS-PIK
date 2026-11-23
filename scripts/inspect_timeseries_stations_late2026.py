import xlrd

book = xlrd.open_workbook('tambahan/Timeseries_Kepri.xls', on_demand=True)
sheet = book.sheet_by_name('HARIAN')

header = sheet.row_values(1)

for m_target in [9, 10, 11, 12]:
    print(f"\n--- Checking Month {m_target} 2026 ---")
    st_data = {}
    for r in range(2, sheet.nrows):
        y = int(sheet.cell_value(r, 0))
        m = int(sheet.cell_value(r, 1))
        d = int(sheet.cell_value(r, 2))
        if y == 2026 and m == m_target:
            vals = sheet.row_values(r)
            for c in range(4, sheet.ncols):
                st_name = header[c]
                val = vals[c]
                if val not in ('', None, 'X', 'x'):
                    if st_name not in st_data:
                        st_data[st_name] = {'count': 0, 'days': []}
                    st_data[st_name]['count'] += 1
                    st_data[st_name]['days'].append(d)
    print(f"Stations with data in 2026-{m_target:02d}: {len(st_data)}")
    for st, info in st_data.items():
        print(f"  {st}: {info['count']} days (min day={min(info['days'])}, max day={max(info['days'])})")

