import xlrd

book = xlrd.open_workbook('tambahan/Timeseries_Kepri.xls', on_demand=True)
sheet = book.sheet_by_name('HARIAN')

# Collect stats per month for 2026
month_stats = {}
for r in range(2, sheet.nrows):
    y = int(sheet.cell_value(r, 0))
    if y == 2026:
        m = int(sheet.cell_value(r, 1))
        d = int(sheet.cell_value(r, 2))
        vals = sheet.row_values(r)[4:]
        non_empty = [v for v in vals if v not in ('', None)]
        data_vals = [v for v in non_empty if v not in ('X', 'x', '-', '8888', '9999')]
        if m not in month_stats:
            month_stats[m] = {'days': 0, 'total_non_empty': 0, 'total_data': 0, 'max_day_data': 0, 'max_day_non_empty': 0}
        month_stats[m]['days'] += 1
        month_stats[m]['total_non_empty'] += len(non_empty)
        month_stats[m]['total_data'] += len(data_vals)
        if len(data_vals) > 0:
            month_stats[m]['max_day_data'] = max(month_stats[m]['max_day_data'], d)
        if len(non_empty) > 0:
            month_stats[m]['max_day_non_empty'] = max(month_stats[m]['max_day_non_empty'], d)

print("2026 Monthly Breakdown in Timeseries_Kepri.xls:")
for m in sorted(month_stats.keys()):
    st = month_stats[m]
    print(f"Month {m:02d}: days={st['days']} | max_day_with_data={st['max_day_data']} | max_day_non_empty={st['max_day_non_empty']} | total_data_pts={st['total_data']}")

