import json
import sys
from urllib.request import urlopen

BASE = "http://127.0.0.1:8000"

def get(path):
    with urlopen(BASE + path, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

print("=" * 65)
print("LIVE ENVIRONMENT API TEST")
print("=" * 65)

health = get("/api/live/health")
print("Health:", health)

for location in ["Delhi", "Faridabad", "Ghaziabad", "Gurgaon", "Noida"]:
    data = get(f"/api/live/environment/{location}")
    aq = data["air_quality"]
    wx = data["weather"]

    print(f"\n{location}")
    print("  Live:", data["live"])
    print("  Source:", data["source"])
    print("  Timestamp:", data["timestamp"])
    print("  US AQI:", aq["us_aqi"])
    print("  PM2.5:", aq["pm25"])
    print("  PM10:", aq["pm10"])
    print("  Temperature:", wx["temperature"])
    print("  Humidity:", wx["humidity"])
    print("  Wind:", wx["wind_speed"])

print("\n" + "=" * 65)
print("RESULT: LIVE ENVIRONMENT API CHECK PASSED")
print("=" * 65)
