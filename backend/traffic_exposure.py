
from fastapi import APIRouter, HTTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import time

router = APIRouter(prefix="/api/traffic", tags=["Traffic Exposure"])

LOCATIONS = {
    "Delhi": (28.6139, 77.2090),
    "Faridabad": (28.4089, 77.3178),
    "Ghaziabad": (28.6692, 77.4538),
    "Gurgaon": (28.4595, 77.0266),
    "Noida": (28.5355, 77.3910),
}

HIGHWAY_WEIGHTS = {
    "motorway": 1.00,
    "trunk": 0.95,
    "primary": 0.85,
    "secondary": 0.70,
    "tertiary": 0.55,
    "unclassified": 0.35,
    "residential": 0.25,
    "service": 0.15,
}

# Public Overpass instances. The main overpass-api.de service can be
# overloaded; using a fallback makes the dashboard more robust.
OVERPASS_URLS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

def _fetch_overpass(query: str):
    last_error = None

    for endpoint in OVERPASS_URLS:
        req = Request(
            endpoint,
            data=urlencode({"data": query}).encode("utf-8"),
            headers={
                "User-Agent": "Delhi-NCR-EDSS/1.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            continue

    raise HTTPException(
        status_code=502,
        detail=f"OpenStreetMap road-network service unavailable after trying {len(OVERPASS_URLS)} public Overpass servers: {last_error}"
    )

def _canonical(location: str):
    return next((x for x in LOCATIONS if x.lower() == location.lower()), None)

@router.get("/health")
def traffic_health():
    return {
        "status": "ok",
        "service": "osm-road-network-traffic-exposure",
        "locations": list(LOCATIONS.keys()),
        "note": "Road-network exposure proxy; not live congestion.",
    }

@router.get("/exposure/{location}")
def traffic_exposure(location: str):
    canonical = _canonical(location)
    if not canonical:
        raise HTTPException(
            status_code=404,
            detail=f"Unsupported Delhi-NCR region: {location}",
        )

    lat, lon = LOCATIONS[canonical]

    # Smaller bounding box and major road classes keep public Overpass
    # requests lightweight and reliable.
    south, north = lat - 0.045, lat + 0.045
    west, east = lon - 0.045, lon + 0.045

    query = f"""
    [out:json][timeout:25];
    way["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|residential"]({south},{west},{north},{east});
    out tags;
    """

    data = _fetch_overpass(query)
    elements = data.get("elements", [])

    counts = {}
    weighted_total = 0.0

    for el in elements:
        highway = el.get("tags", {}).get("highway")
        if highway in HIGHWAY_WEIGHTS:
            counts[highway] = counts.get(highway, 0) + 1
            weighted_total += HIGHWAY_WEIGHTS[highway]

    # Engineering index for spatial exposure. It is deliberately labeled
    # as a proxy, not measured congestion.
    score = min(100.0, round(weighted_total / 70.0 * 100.0, 2))

    if score >= 75:
        category = "VERY HIGH"
    elif score >= 50:
        category = "HIGH"
    elif score >= 25:
        category = "MODERATE"
    else:
        category = "LOW"

    return {
        "location": canonical,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "OpenStreetMap / Overpass",
        "live": True,
        "metric": "Road Network Traffic Exposure",
        "exposure_score": score,
        "category": category,
        "road_segments": len(elements),
        "weighted_road_segments": round(weighted_total, 2),
        "road_class_counts": counts,
        "interpretation": (
            "Higher values indicate greater road-network exposure and "
            "potential traffic-related emission influence. This is a "
            "spatial proxy, not measured traffic speed, congestion, or "
            "vehicle volume."
        ),
    }

@router.get("/all")
def traffic_all():
    results = []
    for location in LOCATIONS:
        results.append(traffic_exposure(location))
    return {"count": len(results), "results": results}
