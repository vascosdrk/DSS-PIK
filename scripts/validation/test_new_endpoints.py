import urllib.request
import json

def test():
    # 1. Test /api/v1/hth
    req = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/hth')
    hth_res = json.loads(req.read().decode())
    print(f"HTH Table: total={hth_res['meta']['total']}")
    top = hth_res['data'][0]
    print(f"Top row: {top['station_name']} ({top['station_id']}) -> HTH: {top['hth_days_current']}, Category: {top['hth_category']}, Warning: {top['warning_level']}, Last Rain: {top['last_rain_date']}")

    # 2. Test /api/v1/stations/21040101B/evaluation
    req2 = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/stations/21040101B/evaluation')
    eval_res = json.loads(req2.read().decode())
    print("\nEvaluation for 21040101B (ARG Singkep):")
    print(f"Status: {eval_res['evaluation']['status']}")
    print(f"Reasons: {eval_res['evaluation']['reasons']}")
    print(f"Recent rainfall days: {len(eval_res['observation_diagnostics']['recent_rainfall'])}")
    print("Nearest 5 stations:")
    for n in eval_res['nearest_stations']:
        print(f"  - {n['station_name']} ({n['distance_km']} km): HTH={n['hth_days_current']} ({n['warning_level']})")

if __name__ == '__main__':
    test()
