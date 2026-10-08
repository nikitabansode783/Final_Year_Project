"""
Delhi-NCR EDSS - API Smoke Test
Run from project root:
    python backend/test_all_apis.py
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

checks = [
    ("/", "Root"),
    ("/api/health", "Health"),
    ("/api/regions", "Regions"),
    ("/api/dashboard/summary", "Dashboard summary"),
    ("/api/aqi/current/Delhi", "Current AQI"),
    ("/api/aqi/history/Delhi?days=30", "AQI history"),
    ("/api/forecast/Delhi", "24h forecast"),
    ("/api/weather/current/Delhi", "Weather"),
    ("/api/pollution-potential", "Pollution potential"),
    ("/api/hotspots", "Future hotspots"),
    ("/api/fire-hotspots?limit=10", "Fire hotspots"),
    ("/api/gis/geojson", "GIS GeoJSON"),
    ("/api/policy/recommendations", "Policy recommendations"),
    ("/api/statistics", "Statistics"),
]

def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=20) as r:
            raw = r.read().decode("utf-8")
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)

print("=" * 72)
print("DELHI-NCR POLLUTION EDSS - API SMOKE TEST")
print("=" * 72)

failed = 0

for path, name in checks:
    status, data = get(path)
    ok = status == 200
    print(f"{'PASS' if ok else 'FAIL':<6} {name:<24} {status}")
    if not ok:
        failed += 1
        print("       ", str(data)[:300])

print("-" * 72)

# Check all five regions on the key region-specific endpoints.
locations = ["Delhi", "Faridabad", "Ghaziabad", "Gurgaon", "Noida"]
for loc in locations:
    for suffix, name in [
        (f"/api/aqi/current/{loc}", "AQI"),
        (f"/api/aqi/history/{loc}?days=30", "History"),
        (f"/api/forecast/{loc}", "Forecast"),
        (f"/api/weather/current/{loc}", "Weather"),
    ]:
        status, data = get(suffix)
        ok = status == 200
        print(f"{'PASS' if ok else 'FAIL':<6} {loc:<12} {name:<12} {status}")
        if not ok:
            failed += 1

print("=" * 72)
if failed:
    print(f"RESULT: {failed} CHECK(S) FAILED")
    sys.exit(1)
else:
    print("RESULT: ALL API CHECKS PASSED")
    sys.exit(0)
