from fastapi import APIRouter, HTTPException
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import json

router = APIRouter(prefix="/api/live", tags=["Live Environmental Data"])

LOCATIONS = {
    "Delhi": (28.6139, 77.2090),
    "Faridabad": (28.4089, 77.3178),
    "Ghaziabad": (28.6692, 77.4538),
    "Gurgaon": (28.4595, 77.0266),
    "Noida": (28.5355, 77.3910),
}

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _fetch_json(url: str, params: dict):
    full_url = url + "?" + urlencode(params)
    try:
        with urlopen(full_url, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"External environmental API returned HTTP {exc.code}",
        )
    except URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach external environmental API: {exc.reason}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"External environmental API error: {exc}",
        )


def _latest_current(obj: dict, key: str):
    current = obj.get("current", {})
    return current.get(key)


@router.get("/environment/{location}")
def live_environment(location: str):
    canonical = next(
        (name for name in LOCATIONS if name.lower() == location.lower()),
        None,
    )

    if canonical is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unsupported Delhi-NCR region: {location}",
        )

    latitude, longitude = LOCATIONS[canonical]

    air = _fetch_json(
        AIR_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join([
                "us_aqi",
                "pm2_5",
                "pm10",
                "carbon_monoxide",
                "nitrogen_dioxide",
                "sulphur_dioxide",
                "ozone",
            ]),
            "timezone": "Asia/Kolkata",
        },
    )

    weather = _fetch_json(
        WEATHER_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "wind_direction_10m",
                "pressure_msl",
                "precipitation",
            ]),
            "wind_speed_unit": "kmh",
            "timezone": "Asia/Kolkata",
        },
    )

    air_time = air.get("current", {}).get("time")
    weather_time = weather.get("current", {}).get("time")

    return {
        "live": True,
        "source": "Open-Meteo / CAMS",
        "location": canonical,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": air_time or weather_time,
        "air_quality": {
            "us_aqi": _latest_current(air, "us_aqi"),
            "pm25": _latest_current(air, "pm2_5"),
            "pm10": _latest_current(air, "pm10"),
            "co": _latest_current(air, "carbon_monoxide"),
            "no2": _latest_current(air, "nitrogen_dioxide"),
            "so2": _latest_current(air, "sulphur_dioxide"),
            "o3": _latest_current(air, "ozone"),
        },
        "weather": {
            "temperature": _latest_current(weather, "temperature_2m"),
            "humidity": _latest_current(weather, "relative_humidity_2m"),
            "wind_speed": _latest_current(weather, "wind_speed_10m"),
            "wind_direction": _latest_current(weather, "wind_direction_10m"),
            "pressure": _latest_current(weather, "pressure_msl"),
            "precipitation": _latest_current(weather, "precipitation"),
        },
        "notes": [
            "Live atmospheric conditions are supplied by Open-Meteo.",
            "Air-quality values are based on CAMS model data exposed by Open-Meteo.",
            "This live AQI is displayed separately from the project's historical India AQI training dataset.",
        ],
    }


@router.get("/health")
def live_health():
    return {
        "status": "ok",
        "service": "live-environment",
        "locations": list(LOCATIONS.keys()),
    }
