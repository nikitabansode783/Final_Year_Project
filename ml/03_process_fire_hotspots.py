"""
03_process_fire_hotspots.py

Process NASA FIRMS active-fire CSV files and spatially identify
fire activity inside the five Delhi-NCR project regions:

    Delhi
    Faridabad
    Ghaziabad
    Gurgaon
    Noida

Important limitation:
The uploaded FIRMS files cover Nov 2024-Jan 2025, while the AQI
dataset currently ends Jan 2024. Therefore this script creates a
separate, spatially processed fire-hotspot layer. It does NOT
pretend these fire observations are temporally aligned with the
historical AQI training data.

Outputs:
    data/processed/fire_hotspots_ncr.csv
    data/processed/fire_hotspots_daily.csv
    data/processed/fire_hotspots_region_summary.csv
    data/processed/fire_hotspots_ncr.geojson
"""

from pathlib import Path
import zipfile
import tempfile
import shutil

import pandas as pd
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
FIRE_ZIP = ROOT / "data" / "raw" / "fire_hotspots.zip"
GIS_ZIP = ROOT / "data" / "raw" / "gis.zip"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

FIRE_COLUMNS = [
    "latitude",
    "longitude",
    "brightness",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_t31",
    "frp",
    "daynight",
]

print("\n" + "=" * 72)
print("NASA FIRMS FIRE HOTSPOT PROCESSING — DELHI-NCR")
print("=" * 72)

if not FIRE_ZIP.exists():
    raise FileNotFoundError(f"Missing: {FIRE_ZIP}")

if not GIS_ZIP.exists():
    raise FileNotFoundError(f"Missing: {GIS_ZIP}")

# -------------------------------------------------------------------
# 1. Extract ZIP files to temporary folders
# -------------------------------------------------------------------
tmp_root = Path(tempfile.mkdtemp(prefix="delhi_ncr_fire_"))

try:
    fire_dir = tmp_root / "fire"
    gis_dir = tmp_root / "gis"
    fire_dir.mkdir()
    gis_dir.mkdir()

    with zipfile.ZipFile(FIRE_ZIP) as z:
        z.extractall(fire_dir)

    with zipfile.ZipFile(GIS_ZIP) as z:
        z.extractall(gis_dir)

    # ----------------------------------------------------------------
    # 2. Read all FIRMS CSVs
    # ----------------------------------------------------------------
    print("\n[1/6] Reading NASA FIRMS files...")

    fire_files = sorted(fire_dir.rglob("*.csv"))
    if not fire_files:
        raise FileNotFoundError("No FIRMS CSV files found inside fire_hotspots.zip")

    frames = []

    for file in fire_files:
        print(f"  Reading {file.name}")
        df = pd.read_csv(file, low_memory=False)

        missing = [c for c in FIRE_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{file.name} is missing columns: {missing}")

        df = df[FIRE_COLUMNS].copy()
        df["source_file"] = file.name
        frames.append(df)

    fire = pd.concat(frames, ignore_index=True)

    print(f"Total FIRMS detections: {len(fire):,}")

    fire["latitude"] = pd.to_numeric(fire["latitude"], errors="coerce")
    fire["longitude"] = pd.to_numeric(fire["longitude"], errors="coerce")
    fire["frp"] = pd.to_numeric(fire["frp"], errors="coerce")
    fire["brightness"] = pd.to_numeric(fire["brightness"], errors="coerce")
    fire["acq_date"] = pd.to_datetime(fire["acq_date"], errors="coerce")

    fire = fire.dropna(
        subset=["latitude", "longitude", "acq_date"]
    ).copy()

    # ----------------------------------------------------------------
    # 3. Restrict to a broad Delhi-NCR geographic bounding box first.
    # ----------------------------------------------------------------
    print("\n[2/6] Filtering to Delhi-NCR geographic area...")

    # Broad box covering Delhi and the surrounding NCR districts.
    ncr = fire[
        fire["latitude"].between(27.5, 29.8)
        & fire["longitude"].between(76.3, 78.8)
    ].copy()

    print(f"Potential NCR-area detections: {len(ncr):,}")

    # ----------------------------------------------------------------
    # 4. Load GIS boundaries and keep the project regions.
    # ----------------------------------------------------------------
    print("\n[3/6] Loading district boundaries...")

    shp_files = list(gis_dir.rglob("*.shp"))
    if not shp_files:
        raise FileNotFoundError("No .shp file found inside gis.zip")

    districts = gpd.read_file(shp_files[0])

    # Five project region mappings.
    #
    # Delhi consists of multiple districts, all mapped to Delhi.
    # Noida corresponds to Gautam Buddha Nagar.
    region_rules = (
        (districts["statename"].eq("Delhi"), "Delhi"),
        (
            districts["statename"].eq("Haryana")
            & districts["distname"].eq("Faridabad"),
            "Faridabad",
        ),
        (
            districts["statename"].eq("Haryana")
            & districts["distname"].eq("Gurgaon"),
            "Gurgaon",
        ),
        (
            districts["statename"].eq("Uttar Pradesh")
            & districts["distname"].eq("Ghaziabad"),
            "Ghaziabad",
        ),
        (
            districts["statename"].eq("Uttar Pradesh")
            & districts["distname"].eq("Gautam Buddha Nagar"),
            "Noida",
        ),
    )

    selected_parts = []

    for mask, region in region_rules:
        part = districts.loc[mask, ["statename", "distname", "geometry"]].copy()
        part["project_region"] = region
        selected_parts.append(part)

    selected = pd.concat(selected_parts, ignore_index=True)
    selected = gpd.GeoDataFrame(selected, geometry="geometry", crs=districts.crs)

    print("Selected GIS districts:")
    print(
        selected[["statename", "distname", "project_region"]]
        .to_string(index=False)
    )

    # ----------------------------------------------------------------
    # 5. Spatially join fire points to the project regions.
    # ----------------------------------------------------------------
    print("\n[4/6] Assigning fire detections to project regions...")

    fire_gdf = gpd.GeoDataFrame(
        ncr.copy(),
        geometry=gpd.points_from_xy(
            ncr["longitude"],
            ncr["latitude"],
        ),
        crs="EPSG:4326",
    )

    if selected.crs != fire_gdf.crs:
        selected = selected.to_crs(fire_gdf.crs)

    joined = gpd.sjoin(
        fire_gdf,
        selected[["project_region", "geometry"]],
        how="inner",
        predicate="within",
    )

    print(f"Fire detections inside project regions: {len(joined):,}")

    # Remove spatial-join bookkeeping.
    if "index_right" in joined.columns:
        joined = joined.drop(columns=["index_right"])

    # ----------------------------------------------------------------
    # 6. Create region/day summaries and GeoJSON.
    # ----------------------------------------------------------------
    print("\n[5/6] Creating hotspot summaries...")

    joined["fire_count"] = 1
    joined["frp"] = joined["frp"].fillna(0)

    daily = (
        joined.groupby(
            ["project_region", "acq_date"],
            as_index=False
        )
        .agg(
            fire_count=("fire_count", "sum"),
            total_frp=("frp", "sum"),
            mean_frp=("frp", "mean"),
            max_frp=("frp", "max"),
            mean_brightness=("brightness", "mean"),
        )
        .sort_values(["acq_date", "project_region"])
    )

    region_summary = (
        joined.groupby("project_region", as_index=False)
        .agg(
            total_fire_detections=("fire_count", "sum"),
            total_frp=("frp", "sum"),
            mean_frp=("frp", "mean"),
            max_frp=("frp", "max"),
            first_detection=("acq_date", "min"),
            last_detection=("acq_date", "max"),
        )
        .sort_values("total_fire_detections", ascending=False)
    )

    # Save CSV without geometry.
    csv_columns = [
        "latitude",
        "longitude",
        "brightness",
        "scan",
        "track",
        "acq_date",
        "acq_time",
        "satellite",
        "instrument",
        "confidence",
        "version",
        "bright_t31",
        "frp",
        "daynight",
        "source_file",
        "project_region",
    ]

    joined[csv_columns].to_csv(
        OUT / "fire_hotspots_ncr.csv",
        index=False,
    )

    daily.to_csv(
        OUT / "fire_hotspots_daily.csv",
        index=False,
    )

    region_summary.to_csv(
        OUT / "fire_hotspots_region_summary.csv",
        index=False,
    )

    # GeoJSON for Leaflet/React later.
    joined[
        [
            "latitude",
            "longitude",
            "acq_date",
            "acq_time",
            "frp",
            "brightness",
            "confidence",
            "satellite",
            "instrument",
            "project_region",
            "geometry",
        ]
    ].to_file(
        OUT / "fire_hotspots_ncr.geojson",
        driver="GeoJSON",
    )

    print("\n[6/6] FIRE HOTSPOT PROCESSING COMPLETE")
    print("\nRegion summary:")
    print(region_summary.to_string(index=False))

    print("\nDate range:")
    print(f"{joined['acq_date'].min()} -> {joined['acq_date'].max()}")

    print("\nOutput files:")
    print(f"  {OUT / 'fire_hotspots_ncr.csv'}")
    print(f"  {OUT / 'fire_hotspots_daily.csv'}")
    print(f"  {OUT / 'fire_hotspots_region_summary.csv'}")
    print(f"  {OUT / 'fire_hotspots_ncr.geojson'}")

    print("\nIMPORTANT DATA LIMITATION:")
    print(
        "The uploaded FIRMS data is from Nov 2024-Jan 2025 and does not "
        "overlap the current AQI training period (2020-2023)."
    )
    print(
        "Therefore the fire layer is processed separately for spatial "
        "hotspot visualization; it is NOT merged into the AQI training "
        "dataset in this step."
    )

finally:
    shutil.rmtree(tmp_root, ignore_errors=True)
