"""
01_integrate_aqi_weather.py

AI-Driven Pollution Source Identification, Forecasting and Policy Dashboard
for Delhi-NCR

Purpose:
1. Read the existing AQI dataset.
2. Read the downloaded hourly weather dataset.
3. Normalize timestamps and location names.
4. Match Delhi-NCR AQI observations with the closest available weather city.
5. Create a clean integrated dataset for ML.
6. Save it to data/processed/aqi_weather_integrated.csv.

Important:
- No values are fabricated.
- Delhi, Faridabad and Ghaziabad have matching weather-city records.
- Gurgaon and Noida do not have separate weather-city records in the downloaded
  weather file, so Delhi weather is used as a clearly marked proxy for those two
  regions. This is recorded in weather_is_proxy and weather_source_city.
"""

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

AQI_FILE = ROOT / "data" / "raw" / "processed_aqi_data.csv"
WEATHER_FILE = ROOT / "data" / "raw" / "weather" / "hourly_data.csv"
OUTPUT_DIR = ROOT / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "aqi_weather_integrated.csv"

# AQI location -> weather city in the downloaded dataset.
# Exact matches are used where available.
LOCATION_TO_WEATHER = {
    "Delhi": "Delhi",
    "Faridabad": "Farīdābād",
    "Ghaziabad": "Ghāziābād",
    "Gurgaon": "Delhi",   # proxy; no Gurgaon weather city in downloaded file
    "Noida": "Delhi",     # proxy; no Noida weather city in downloaded file
}

print("\n" + "=" * 70)
print("DELHI-NCR AQI + WEATHER DATA INTEGRATION")
print("=" * 70)

# -------------------------------------------------------------------
# 1. Check files
# -------------------------------------------------------------------
if not AQI_FILE.exists():
    raise FileNotFoundError(
        f"\nAQI file not found:\n{AQI_FILE}\n"
        "Make sure processed_aqi_data.csv is inside data/raw/"
    )

if not WEATHER_FILE.exists():
    raise FileNotFoundError(
        f"\nWeather file not found:\n{WEATHER_FILE}\n"
        "Make sure hourly_data.csv is inside data/raw/weather/"
    )

# -------------------------------------------------------------------
# 2. Load AQI
# -------------------------------------------------------------------
print("\n[1/6] Loading AQI data...")
aqi = pd.read_csv(AQI_FILE)

required_aqi = [
    "timestamp",
    "location_name",
    "location_lat",
    "location_lon",
    "co",
    "no2",
    "o3",
    "pm10",
    "pm25",
    "so2",
    "aqi",
]

missing_aqi = [c for c in required_aqi if c not in aqi.columns]
if missing_aqi:
    raise ValueError(f"AQI dataset is missing columns: {missing_aqi}")

aqi["timestamp"] = pd.to_datetime(aqi["timestamp"], errors="coerce")

# Standardize AQI location spelling.
aqi["location_name"] = (
    aqi["location_name"]
    .astype(str)
    .str.strip()
    .replace({
        "Gurugram": "Gurgaon",
        "Gurgaon ": "Gurgaon",
    })
)

aqi = aqi.dropna(subset=["timestamp", "location_name"]).copy()

print(f"AQI rows: {len(aqi):,}")
print(f"AQI time range: {aqi['timestamp'].min()} -> {aqi['timestamp'].max()}")
print("AQI locations:")
print(aqi["location_name"].value_counts().to_string())

# -------------------------------------------------------------------
# 3. Keep only the five Delhi-NCR regions in the project
# -------------------------------------------------------------------
target_locations = list(LOCATION_TO_WEATHER.keys())
aqi = aqi[aqi["location_name"].isin(target_locations)].copy()

# -------------------------------------------------------------------
# 4. Load weather
# -------------------------------------------------------------------
print("\n[2/6] Loading hourly weather data...")

weather_columns = [
    "city_name",
    "datetime",
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "snowfall",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

weather = pd.read_csv(
    WEATHER_FILE,
    usecols=weather_columns,
)

weather["datetime"] = pd.to_datetime(weather["datetime"], errors="coerce")
weather = weather.dropna(subset=["datetime", "city_name"]).copy()

print(f"Weather rows loaded: {len(weather):,}")
print(f"Weather time range: {weather['datetime'].min()} -> {weather['datetime'].max()}")

# Keep only weather cities required for the project.
weather_cities = set(LOCATION_TO_WEATHER.values())
weather = weather[weather["city_name"].isin(weather_cities)].copy()

# -------------------------------------------------------------------
# 5. Rename weather datetime and merge
# -------------------------------------------------------------------
print("\n[3/6] Aligning timestamps and locations...")

weather = weather.rename(columns={"datetime": "timestamp"})

# One row per weather city + timestamp.
weather = (
    weather
    .sort_values(["city_name", "timestamp"])
    .drop_duplicates(subset=["city_name", "timestamp"], keep="first")
)

aqi["weather_source_city"] = aqi["location_name"].map(LOCATION_TO_WEATHER)
aqi["weather_is_proxy"] = aqi["location_name"].isin(["Gurgaon", "Noida"])

merged = aqi.merge(
    weather,
    left_on=["weather_source_city", "timestamp"],
    right_on=["city_name", "timestamp"],
    how="left",
    suffixes=("", "_weather"),
)

merged = merged.drop(columns=["city_name"])

# -------------------------------------------------------------------
# 6. Feature engineering
# -------------------------------------------------------------------
print("\n[4/6] Creating ML features...")

merged["hour"] = merged["timestamp"].dt.hour
merged["day"] = merged["timestamp"].dt.day
merged["month"] = merged["timestamp"].dt.month
merged["year"] = merged["timestamp"].dt.year
merged["day_of_week"] = merged["timestamp"].dt.dayofweek
merged["is_weekend"] = (merged["day_of_week"] >= 5).astype(int)

# AQI lag features: extremely useful for short-term time-series forecasting.
merged = merged.sort_values(["location_name", "timestamp"])

for lag in [1, 3, 6, 12, 24]:
    merged[f"aqi_lag_{lag}h"] = (
        merged.groupby("location_name")["aqi"].shift(lag)
    )

# Previous PM2.5 is also useful for forecasting.
for lag in [1, 3, 6, 24]:
    merged[f"pm25_lag_{lag}h"] = (
        merged.groupby("location_name")["pm25"].shift(lag)
    )

# -------------------------------------------------------------------
# 7. Report weather coverage
# -------------------------------------------------------------------
print("\n[5/6] Checking weather coverage...")

weather_features = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
]

for col in weather_features:
    missing_pct = merged[col].isna().mean() * 100
    print(f"{col:25s}: {missing_pct:6.2f}% missing")

# For the ML-ready dataset, remove rows where the core target or core
# weather variables are unavailable. We do NOT fabricate weather values.
core_columns = [
    "aqi",
    "temperature_2m",
    "relative_humidity_2m",
    "pressure_msl",
    "wind_speed_10m",
]

before = len(merged)
merged_ml = merged.dropna(subset=core_columns).copy()
after = len(merged_ml)

print(f"\nRows before ML cleaning: {before:,}")
print(f"Rows after ML cleaning:  {after:,}")
print(f"Rows removed:            {before - after:,}")

# -------------------------------------------------------------------
# 8. Save
# -------------------------------------------------------------------
print("\n[6/6] Saving integrated dataset...")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
merged_ml.to_csv(OUTPUT_FILE, index=False)

print("\n" + "=" * 70)
print("SUCCESS")
print("=" * 70)
print(f"Saved to:\n{OUTPUT_FILE}")
print(f"Rows: {len(merged_ml):,}")
print(f"Columns: {len(merged_ml.columns)}")

print("\nFinal locations:")
print(merged_ml["location_name"].value_counts().to_string())

print("\nWeather proxy usage:")
print(merged_ml.groupby(
    ["location_name", "weather_source_city", "weather_is_proxy"]
).size().to_string())

print("\nNext file we will build:")
print("02_train_aqi_models.py")
print("This will train and compare Linear Regression, Random Forest and XGBoost.")
