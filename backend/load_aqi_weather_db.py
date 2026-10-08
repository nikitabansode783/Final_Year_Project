from pathlib import Path
import sys
import os
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "backend" / ".env"
AQI_WEATHER_FILE = ROOT / "data" / "processed" / "aqi_weather_integrated.csv"
GIS_FILE = ROOT / "data" / "raw" / "gis" / "output.shp"

load_dotenv(ENV_FILE)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL not found. Check: {ENV_FILE}")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def pick_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col
    return None

def numeric(df, col):
    if col and col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series([None] * len(df), index=df.index, dtype="float64")

def identify_region(row):
    vals = []
    for col in ["distname", "statename", "state_ut", "district", "name"]:
        if col in row.index and pd.notna(row[col]):
            vals.append(str(row[col]).strip().lower())
    s = " ".join(vals)
    if any(x in s for x in [
        "delhi", "central delhi", "east delhi", "new delhi",
        "north delhi", "north east delhi", "north west delhi",
        "south delhi", "south east delhi", "south west delhi", "shahdara"
    ]):
        return "Delhi"
    if "faridabad" in s:
        return "Faridabad"
    if "gurgaon" in s or "gurugram" in s:
        return "Gurgaon"
    if "ghaziabad" in s:
        return "Ghaziabad"
    if "gautam buddha nagar" in s or "gautam buddh nagar" in s or "noida" in s:
        return "Noida"
    return None

def load_regions():
    print("\nLoading GIS district boundaries...")
    gdf = gpd.read_file(GIS_FILE)
    print(f"GIS features loaded: {len(gdf):,}")
    print("\nGIS columns:")
    print(list(gdf.columns))

    gdf["ncr_region"] = gdf.apply(identify_region, axis=1)
    print("\nNCR regions detected:")
    print(gdf["ncr_region"].value_counts(dropna=True))

    gdf = gdf[gdf["ncr_region"].notna()].copy()
    regions = gdf.dissolve(by="ncr_region", as_index=False)[["ncr_region", "geometry"]]
    if regions.crs is None:
        regions = regions.set_crs("EPSG:4326")
    else:
        regions = regions.to_crs("EPSG:4326")

    order = {"Delhi": 0, "Faridabad": 1, "Ghaziabad": 2, "Gurgaon": 3, "Noida": 4}
    regions["order"] = regions["ncr_region"].map(order)
    regions = regions.sort_values("order").drop(columns="order")
    print(f"\nFinal NCR regions: {len(regions)}")
    return regions

def reset_and_insert_regions(regions):
    print("\nResetting existing project data...")
    with engine.begin() as conn:
        for table in ["air_quality", "weather", "aqi_forecasts", "pollution_risk", "policy_recommendations", "hotspots"]:
            try:
                conn.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass
        conn.execute(text("DELETE FROM regions"))
    print("Existing project records cleared.")

    print("\nLoading GIS polygons into PostgreSQL...")
    with engine.begin() as conn:
        for _, row in regions.iterrows():
            name = row["ncr_region"]
            district = "Gautam Buddha Nagar" if name == "Noida" else name
            state = "Delhi" if name == "Delhi" else ("Haryana" if name in ["Faridabad", "Gurgaon"] else "Uttar Pradesh")
            conn.execute(
                text("""
                    INSERT INTO regions (name, district, state, geometry)
                    VALUES (:name, :district, :state,
                            ST_SetSRID(ST_GeomFromText(:geometry), 4326))
                """),
                {"name": name, "district": district, "state": state, "geometry": row.geometry.wkt},
            )
    print(f"GIS regions inserted: {len(regions)}")

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, name FROM regions
            WHERE name IN ('Delhi','Faridabad','Ghaziabad','Gurgaon','Noida')
            ORDER BY id
        """)).fetchall()

    region_map = {r.name: r.id for r in rows}
    print("\nDatabase region mapping:")
    for name in ["Delhi", "Faridabad", "Ghaziabad", "Gurgaon", "Noida"]:
        print(f"  {name} -> {region_map.get(name)}")
    if len(region_map) != 5:
        raise RuntimeError(f"Expected 5 NCR regions, found: {region_map}")
    return region_map

def load_data(region_map):
    print("\nLoading integrated AQI + weather data...")
    df = pd.read_csv(AQI_WEATHER_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["location_name"] = df["location_name"].astype(str).str.strip()
    df["region_id"] = df["location_name"].map(region_map)
    if df["region_id"].isna().any():
        bad = df.loc[df["region_id"].isna(), "location_name"].unique().tolist()
        raise RuntimeError(f"Unmapped locations: {bad}")
    print(f"Rows loaded: {len(df):,}")

    print("\nLoading air quality data...")
    aqi = pd.DataFrame({
        "region_id": df["region_id"].astype("int64"),
        "timestamp": df["timestamp"],
        "aqi": numeric(df, "aqi"),
        "pm25": numeric(df, "pm25"),
        "pm10": numeric(df, "pm10"),
        "no2": numeric(df, "no2"),
        "so2": numeric(df, "so2"),
        "co": numeric(df, "co"),
        "o3": numeric(df, "o3"),
    }).dropna(subset=["region_id", "timestamp"])

    aqi.to_sql("air_quality", engine, if_exists="append", index=False, chunksize=500, method=None)
    print(f"AQI records inserted: {len(aqi):,}")
    print(f"Air quality rows inserted: {len(aqi):,}")

    print("\nLoading weather data...")
    temp = pick_column(df, ["temperature_2m", "temperature", "temp"])
    hum = pick_column(df, ["relative_humidity_2m", "humidity", "relative_humidity"])
    wind = pick_column(df, ["wind_speed_10m", "wind_speed", "windspeed"])
    direction = pick_column(df, ["wind_direction_10m", "wind_direction", "winddirection", "wind_direction_deg"])
    pressure = pick_column(df, ["pressure_msl", "surface_pressure", "pressure"])
    rain = pick_column(df, ["precipitation", "rainfall", "rain"])

    print("Weather source columns detected:")
    print(f"  temperature    -> {temp}")
    print(f"  humidity       -> {hum}")
    print(f"  wind_speed     -> {wind}")
    print(f"  wind_direction -> {direction}")
    print(f"  pressure       -> {pressure}")
    print(f"  rainfall       -> {rain}")

    weather = pd.DataFrame({
        "region_id": df["region_id"].astype("int64"),
        "timestamp": df["timestamp"],
        "temperature": numeric(df, temp),
        "humidity": numeric(df, hum),
        "wind_speed": numeric(df, wind),
        "wind_direction": numeric(df, direction),
        "pressure": numeric(df, pressure),
        "rainfall": numeric(df, rain),
    }).dropna(subset=["region_id", "timestamp"])

    weather.to_sql("weather", engine, if_exists="append", index=False, chunksize=500, method=None)
    print(f"Weather records inserted: {len(weather):,}")
    return len(aqi), len(weather)

def main():
    print("=" * 70)
    print("POSTGRESQL DATA INGESTION")
    print("=" * 70)
    if not AQI_WEATHER_FILE.exists():
        raise FileNotFoundError(f"Missing integrated dataset: {AQI_WEATHER_FILE}")
    if not GIS_FILE.exists():
        raise FileNotFoundError(f"Missing GIS shapefile: {GIS_FILE}")
    regions = load_regions()
    region_map = reset_and_insert_regions(regions)
    aqi_count, weather_count = load_data(region_map)
    print("\n" + "=" * 70)
    print("DATABASE INGESTION COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"Regions:       {len(region_map)}")
    print(f"Air quality:   {aqi_count:,} rows")
    print(f"Weather:       {weather_count:,} rows")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n" + "=" * 70)
        print("DATABASE INGESTION FAILED")
        print("=" * 70)
        print(f"{type(exc).__name__}: {exc}")
        print("=" * 70)
        sys.exit(1)
