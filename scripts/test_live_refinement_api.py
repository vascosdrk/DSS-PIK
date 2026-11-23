import sys
sys.path.insert(0, ".")
import urllib.request
import json

from backend.auth import create_session_token

token = create_session_token('klimatkepri')
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

# 2. Test PDKM map generation
payload_pdkm = {
    'period_id': '2026-09-das2',
    'map_type': 'PDKM',
    'regency_decisions': {
        'BINTAN': {'warning_type': 'PDKM', 'classification': 'WASPADA', 'override_reason': ''},
        'NATUNA': {'warning_type': 'PDCHT', 'classification': 'SIAGA', 'override_reason': ''},
        'KOTA TANJUNGPINANG': {'warning_type': 'NONE', 'classification': 'AMAN', 'override_reason': ''},
    }
}
req_m1 = urllib.request.Request('http://127.0.0.1:8000/api/v1/maps/generate', data=json.dumps(payload_pdkm).encode(), headers=headers)
r_m1 = json.loads(urllib.request.urlopen(req_m1).read().decode())
print('PDKM Map File:', r_m1['jpg_filename'])
print('  - Bintan status on PDKM:', r_m1['regency_status']['BINTAN'])
print('  - Natuna status on PDKM:', r_m1['regency_status']['NATUNA'])

# 3. Test PDCHT map generation
payload_pdcht = {
    'period_id': '2026-09-das2',
    'map_type': 'PDCHT',
    'regency_decisions': {
        'BINTAN': {'warning_type': 'PDKM', 'classification': 'WASPADA', 'override_reason': ''},
        'NATUNA': {'warning_type': 'PDCHT', 'classification': 'SIAGA', 'override_reason': ''},
        'KOTA TANJUNGPINANG': {'warning_type': 'NONE', 'classification': 'AMAN', 'override_reason': ''},
    }
}
req_m2 = urllib.request.Request('http://127.0.0.1:8000/api/v1/maps/generate', data=json.dumps(payload_pdcht).encode(), headers=headers)
r_m2 = json.loads(urllib.request.urlopen(req_m2).read().decode())
print('PDCHT Map File:', r_m2['jpg_filename'])
print('  - Bintan status on PDCHT:', r_m2['regency_status']['BINTAN'])
print('  - Natuna status on PDCHT:', r_m2['regency_status']['NATUNA'])

# 4. Test JSON export
req_j = urllib.request.Request('http://127.0.0.1:8000/api/v1/maps/generate-json', data=json.dumps(payload_pdkm).encode(), headers=headers)
r_j = json.loads(urllib.request.urlopen(req_j).read().decode())
print('JSON Export File:', r_j['download_filename'])
print('  - Schema Version:', r_j['payload']['schema_version'])
print('  - System:', r_j['payload']['system'])
print('  - Regions Count:', len(r_j['payload']['regions']))
print('  - Region 0:', r_j['payload']['regions'][0]['region_name'], r_j['payload']['regions'][0]['final_decision'])

# 5. Verify download endpoint for the generated files
for test_file in [r_m1['jpg_filename'], r_m2['jpg_filename'], r_j['download_filename']]:
    url_dl = f"http://127.0.0.1:8000/api/v1/maps/download/{test_file}"
    resp_dl = urllib.request.urlopen(url_dl)
    content_len = len(resp_dl.read())
    print(f"Download {test_file}: HTTP {resp_dl.status}, {content_len} bytes")

print("\nALL API ENDPOINTS TESTED SUCCESSFULLY!")
