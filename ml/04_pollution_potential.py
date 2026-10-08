"""
Pollution Potential / Risk Index
Delhi-NCR Pollution EDSS

Transparent decision-support index; it is NOT a causal source-attribution model.
"""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "aqi_weather_integrated.csv"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

def rank01(s):
    s = pd.to_numeric(s, errors="coerce")
    return s.rank(pct=True).fillna(0.5)

def col(df, names):
    for n in names:
        if n in df.columns:
            return n
    return None

df = pd.read_csv(SRC)
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp", "location_name"]).copy()

wind_col = col(df, ["wind_speed_10m","wind_speed"])
rain_col = col(df, ["precipitation","rainfall"])
temp_col = col(df, ["temperature_2m","temperature"])
hum_col = col(df, ["relative_humidity_2m","humidity"])

aqi_r = rank01(df["aqi"])
pm25_r = rank01(df["pm25"])
pm10_r = rank01(df["pm10"])
no2_r = rank01(df["no2"])

pollution_intensity = 100 * (
    0.40 * aqi_r +
    0.30 * pm25_r +
    0.20 * pm10_r +
    0.10 * no2_r
)

if wind_col:
    wind = pd.to_numeric(df[wind_col], errors="coerce")
    wind_rank = rank01(wind)
else:
    wind_rank = pd.Series(0.5, index=df.index)

if rain_col:
    rain = pd.to_numeric(df[rain_col], errors="coerce").clip(lower=0)
    rain_rank = rank01(rain)
else:
    rain_rank = pd.Series(0.5, index=df.index)

stagnation = 100 * (0.70 * (1 - wind_rank) + 0.30 * (1 - rain_rank))
potential = (0.80 * pollution_intensity + 0.20 * stagnation).clip(0,100)

df["pollution_intensity"] = pollution_intensity.round(2)
df["stagnation_score"] = stagnation.round(2)
df["pollution_potential"] = potential.round(2)
df["risk_category"] = pd.cut(
    df["pollution_potential"],
    bins=[-0.01,25,50,75,100.01],
    labels=["LOW","MODERATE","HIGH","VERY HIGH"]
)

hourly_cols = [
    "timestamp","location_name","aqi","pm25","pm10","no2","so2","co","o3",
    temp_col,hum_col,wind_col,rain_col,
    "pollution_intensity","stagnation_score","pollution_potential","risk_category"
]
hourly_cols = [c for c in hourly_cols if c and c in df.columns]
df[hourly_cols].to_csv(OUT/"pollution_potential_hourly.csv", index=False)

summary = (
    df.groupby("location_name", as_index=False)
      .agg(
        average_aqi=("aqi","mean"),
        maximum_aqi=("aqi","max"),
        average_pm25=("pm25","mean"),
        maximum_pm25=("pm25","max"),
        average_pm10=("pm10","mean"),
        maximum_pm10=("pm10","max"),
        average_no2=("no2","mean"),
        average_pollution_potential=("pollution_potential","mean"),
        maximum_pollution_potential=("pollution_potential","max"),
        high_risk_hours=("pollution_potential", lambda s: int((s>=50).sum())),
        very_high_hours=("pollution_potential", lambda s: int((s>=75).sum())),
    )
)
summary["high_risk_percentage"] = (
    100 * summary["high_risk_hours"] / df.groupby("location_name").size().values
)
summary["risk_category"] = pd.cut(
    summary["average_pollution_potential"],
    bins=[-0.01,25,50,75,100.01],
    labels=["LOW","MODERATE","HIGH","VERY HIGH"]
)
summary = summary.round(2)
summary.to_csv(OUT/"pollution_potential_region_summary.csv", index=False)

print("="*70)
print("POLLUTION POTENTIAL ANALYSIS COMPLETED")
print("="*70)
print(f"Hourly records: {len(df):,}")
print(f"Regions: {summary['location_name'].nunique()}")
print("\nRegional summary:")
print(summary[["location_name","average_pollution_potential","maximum_pollution_potential","risk_category"]].to_string(index=False))
print("="*70)
