
from urllib.request import urlopen
import json

BASE = "http://127.0.0.1:8000"

def get(path):
    with urlopen(BASE + path, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))

print("=" * 65)
print("TRAFFIC / ROAD NETWORK EXPOSURE API TEST")
print("=" * 65)

health = get("/api/traffic/health")
print("Health:", health)

for location in ["Delhi", "Faridabad", "Ghaziabad", "Gurgaon", "Noida"]:
    data = get(f"/api/traffic/exposure/{location}")
    print(f"\n{location}")
    print("  Source:", data["source"])
    print("  Exposure Score:", data["exposure_score"])
    print("  Category:", data["category"])
    print("  Road Segments:", data["road_segments"])

print("\n" + "=" * 65)
print("RESULT: TRAFFIC EXPOSURE API CHECK PASSED")
print("=" * 65)
