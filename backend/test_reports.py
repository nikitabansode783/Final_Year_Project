
from urllib.request import urlopen
BASE="http://127.0.0.1:8000"
for loc in ["Delhi","Faridabad","Ghaziabad","Gurgaon","Noida"]:
    with urlopen(f"{BASE}/api/reports/{loc}", timeout=30) as r:
        data=r.read()
        print(loc, "JSON REPORT OK", len(data), "bytes")
with urlopen(f"{BASE}/api/reports/Delhi/pdf", timeout=30) as r:
    data=r.read()
    print("PDF REPORT OK", len(data), "bytes", r.headers.get("Content-Type"))
print("RESULT: REPORT API CHECK PASSED")
