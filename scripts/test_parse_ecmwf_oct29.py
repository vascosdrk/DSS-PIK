import sys
sys.path.insert(0, '.')
from backend.ingestion_service import parse_probability_excel
import json

print("=== PARSING ECMWF FORECAST 2026.10.29 ===")
fp = 'scratch/inspect_ecmwf/KEPRI_pch_ecmwf_perpos_ver_2026.10.29_DAS1 NOV.xlsx'
with open(fp, 'rb') as f:
    fbytes = f.read()

res = parse_probability_excel(fbytes, 'KEPRI_pch_ecmwf_perpos_ver_2026.10.29_DAS1 NOV.xlsx', forecast_type='DASARIAN')

summ = res['summary']
print("Status:", res['status'])
print("Forecast Resolution:", summ['forecast_resolution'])
print("Forecast Type:", summ['forecast_type'])
print("Issue Date (from content):", summ['issue_date'])
print("Issue Date (from filename):", summ.get('filename_issue_date'))
print("Target Period:", summ['target_period'])
print("Target Year/Month/Dasarian:", summ['target_year'], summ['target_month'], summ['target_dasarian'])
print("Recognized Stations:", summ['total_stations_recognized'])
print("Unrecognized Stations:", summ['total_stations_unrecognized'])
print("Parameters Detected:", summ['parameters_detected'])
print("Total Records:", summ['total_records'])
print("New Records (NEW VINTAGE):", summ['total_new'])
print("Identical Records:", summ['total_identical'])
print("Updated Records:", summ['total_updated'])
print("Anomalies:", len(res['anomalies']))

print("\nSample Preview Items (first 8):")
for it in res['preview_items'][:8]:
    print(f"  Station {it['station_id']} ({it['station_name']}) | Param: {it['parameter']} | Prob: {it['new_value']}% | Status: {it['diff_status']}")

