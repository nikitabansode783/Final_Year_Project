"""
Forecast service for the Delhi-NCR Pollution EDSS.

Loads the trained XGBoost 24-hour AQI model and uses the latest
available integrated AQI + weather record for a selected region.
"""

from pathlib import Path
import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

MODEL_FILE = ROOT / "ml" / "saved_models" / "xgboost_aqi_24h.joblib"
DATA_FILE = ROOT / "data" / "processed" / "aqi_weather_integrated.csv"

FEATURE_COLUMNS = [
    "aqi",
    "pm25",
    "pm10",
    "no2",
    "so2",
    "co",
    "o3",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "hour",
    "day",
    "month",
    "day_of_week",
    "is_weekend",
    "aqi_lag_1h",
    "aqi_lag_3h",
    "aqi_lag_6h",
    "aqi_lag_12h",
    "aqi_lag_24h",
    "pm25_lag_1h",
    "pm25_lag_3h",
    "pm25_lag_6h",
    "pm25_lag_24h",
]


def load_forecast_resources():
    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Trained XGBoost model not found: {MODEL_FILE}"
        )

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Integrated dataset not found: {DATA_FILE}"
        )

    model = joblib.load(MODEL_FILE)
    data = pd.read_csv(DATA_FILE)
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    data = data.dropna(subset=["timestamp"])

    return model, data


def predict_24h_aqi(location: str):
    model, data = load_forecast_resources()

    # Accept common user spellings.
    aliases = {
        "delhi": "Delhi",
        "faridabad": "Faridabad",
        "ghaziabad": "Ghaziabad",
        "gurgaon": "Gurgaon",
        "gurugram": "Gurgaon",
        "noida": "Noida",
    }

    key = location.strip().lower()
    if key not in aliases:
        raise ValueError(
            "Location must be one of: Delhi, Faridabad, Ghaziabad, Gurgaon, Noida"
        )

    selected_location = aliases[key]

    location_data = data[
        data["location_name"] == selected_location
    ].sort_values("timestamp")

    if location_data.empty:
        raise ValueError(f"No data available for {selected_location}")

    latest = location_data.iloc[-1]

    missing = [
        col for col in FEATURE_COLUMNS
        if col not in latest.index or pd.isna(latest[col])
    ]

    if missing:
        raise ValueError(
            f"Latest record for {selected_location} is missing features: {missing}"
        )

    X = pd.DataFrame(
        [[latest[col] for col in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS,
    )

    predicted_aqi = float(model.predict(X)[0])

    # AQI cannot be negative.
    predicted_aqi = max(0.0, predicted_aqi)

    return {
        "location": selected_location,
        "forecast_horizon": "24 hours",
        "based_on_timestamp": latest["timestamp"].isoformat(),
        "current_aqi": float(latest["aqi"]),
        "predicted_aqi_24h": round(predicted_aqi, 2),
        "current_pm25": float(latest["pm25"]),
        "current_pm10": float(latest["pm10"]),
        "temperature": float(latest["temperature_2m"]),
        "humidity": float(latest["relative_humidity_2m"]),
        "wind_speed": float(latest["wind_speed_10m"]),
        "weather_source_city": latest["weather_source_city"],
        "weather_is_proxy": bool(latest["weather_is_proxy"]),
        "model": "XGBoost",
    }
