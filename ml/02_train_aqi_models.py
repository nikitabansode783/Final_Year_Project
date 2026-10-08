"""
02_train_aqi_models.py

Train and compare AQI forecasting models using the integrated
Delhi-NCR AQI + weather dataset.

Forecast horizon:
    24 hours ahead

Models:
    1. Linear Regression
    2. Random Forest Regressor
    3. XGBoost Regressor

Evaluation:
    MAE, RMSE, R²

The split is chronological to prevent future-data leakage.
"""

from pathlib import Path
import json
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "processed" / "aqi_weather_integrated.csv"
MODEL_DIR = ROOT / "ml" / "saved_models"
RESULT_DIR = ROOT / "data" / "processed"

FORECAST_HOURS = 24

print("\n" + "=" * 72)
print("DELHI-NCR AQI FORECASTING — MODEL COMPARISON")
print("=" * 72)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Integrated dataset not found:\n{INPUT_FILE}\n"
        "Run 01_integrate_aqi_weather.py first."
    )

# -------------------------------------------------------------------
# 1. Load data
# -------------------------------------------------------------------
print("\n[1/7] Loading integrated dataset...")
df = pd.read_csv(INPUT_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp"]).sort_values(
    ["location_name", "timestamp"]
).reset_index(drop=True)

print(f"Rows: {len(df):,}")
print(f"Columns: {len(df.columns)}")
print(f"Time range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

# -------------------------------------------------------------------
# 2. Create 24-hour forecasting target
# -------------------------------------------------------------------
print("\n[2/7] Creating 24-hour-ahead AQI target...")

df["target_aqi_24h"] = (
    df.groupby("location_name")["aqi"].shift(-FORECAST_HOURS)
)

df["target_timestamp"] = (
    df.groupby("location_name")["timestamp"].shift(-FORECAST_HOURS)
)

# Remove rows without a future target.
df = df.dropna(subset=["target_aqi_24h", "target_timestamp"]).copy()

# -------------------------------------------------------------------
# 3. Select features
# -------------------------------------------------------------------
print("\n[3/7] Preparing ML features...")

feature_columns = [
    # Current pollution state
    "aqi",
    "pm25",
    "pm10",
    "no2",
    "so2",
    "co",
    "o3",

    # Weather
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "pressure_msl",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",

    # Time
    "hour",
    "day",
    "month",
    "day_of_week",
    "is_weekend",

    # AQI history
    "aqi_lag_1h",
    "aqi_lag_3h",
    "aqi_lag_6h",
    "aqi_lag_12h",
    "aqi_lag_24h",

    # PM2.5 history
    "pm25_lag_1h",
    "pm25_lag_3h",
    "pm25_lag_6h",
    "pm25_lag_24h",
]

# Keep only features actually present.
missing_features = [c for c in feature_columns if c not in df.columns]
if missing_features:
    raise ValueError(f"Missing expected feature columns: {missing_features}")

# Do not use location coordinates or weather proxy flags as model inputs.
# One-hot encoding location is not necessary because separate regional
# temporal patterns are already represented through the data.
model_df = df[feature_columns + ["target_aqi_24h", "timestamp", "target_timestamp"]].copy()

# Convert everything used by the models to numeric.
for col in feature_columns + ["target_aqi_24h"]:
    model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

before = len(model_df)
model_df = model_df.dropna(subset=feature_columns + ["target_aqi_24h"]).copy()
print(f"Rows after removing incomplete ML records: {len(model_df):,}")
print(f"Rows removed: {before - len(model_df):,}")

# -------------------------------------------------------------------
# 4. Chronological split
# -------------------------------------------------------------------
print("\n[4/7] Creating chronological train/test split...")

# Use 80% of the available time range as the training period.
split_time = model_df["timestamp"].quantile(0.80)

# Important:
# A training observation is allowed only if its 24h target is also before
# the test period. This prevents target leakage across the split boundary.
train_df = model_df[model_df["target_timestamp"] < split_time].copy()
test_df = model_df[model_df["timestamp"] >= split_time].copy()

X_train = train_df[feature_columns]
y_train = train_df["target_aqi_24h"]

X_test = test_df[feature_columns]
y_test = test_df["target_aqi_24h"]

print(f"Split timestamp: {split_time}")
print(f"Training rows: {len(train_df):,}")
print(f"Testing rows:  {len(test_df):,}")
print(f"Train period: {train_df['timestamp'].min()} -> {train_df['timestamp'].max()}")
print(f"Test period:  {test_df['timestamp'].min()} -> {test_df['timestamp'].max()}")

if len(train_df) == 0 or len(test_df) == 0:
    raise RuntimeError("Train/test split produced an empty dataset.")

# -------------------------------------------------------------------
# 5. Train models
# -------------------------------------------------------------------
print("\n[5/7] Training models...")

MODEL_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

models = {
    "Linear Regression": Pipeline([
        ("scaler", StandardScaler()),
        ("model", LinearRegression()),
    ]),
    "Random Forest": RandomForestRegressor(
        n_estimators=150,
        max_depth=25,
        min_samples_leaf=2,
        n_jobs=-1,
        random_state=42,
    ),
}

# XGBoost is optional in this first run; if installed, include it.
try:
    from xgboost import XGBRegressor

    models["XGBoost"] = XGBRegressor(
        n_estimators=500,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        n_jobs=-1,
        random_state=42,
    )
    print("XGBoost detected: included in comparison.")
except ImportError:
    print("XGBoost not installed: skipping it for this run.")
    print("We can install it after the first comparison if required.")

results = []
predictions = {}

for name, model in models.items():
    print(f"\nTraining {name}...")
    start = time.time()

    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    elapsed = time.time() - start

    mae = mean_absolute_error(y_test, pred)
    rmse = np.sqrt(mean_squared_error(y_test, pred))
    r2 = r2_score(y_test, pred)

    results.append({
        "model": name,
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2,
        "training_seconds": elapsed,
    })

    predictions[name] = pred

    print(f"MAE :  {mae:.4f}")
    print(f"RMSE:  {rmse:.4f}")
    print(f"R²  :  {r2:.4f}")
    print(f"Time:  {elapsed:.2f} seconds")

    # Save model using joblib.
    try:
        import joblib
        safe_name = name.lower().replace(" ", "_")
        joblib.dump(model, MODEL_DIR / f"{safe_name}_aqi_24h.joblib")
    except ImportError:
        print("joblib unavailable; model file not saved.")

# -------------------------------------------------------------------
# 6. Select best model
# -------------------------------------------------------------------
print("\n[6/7] Comparing models...")

results_df = pd.DataFrame(results).sort_values("RMSE").reset_index(drop=True)

print("\n" + "-" * 72)
print(results_df.to_string(index=False))
print("-" * 72)

best_model_name = results_df.iloc[0]["model"]

print(f"\nBEST MODEL BY RMSE: {best_model_name}")

# Save results.
results_file = RESULT_DIR / "aqi_model_results.csv"
results_df.to_csv(results_file, index=False)

# Save test predictions from the best model.
best_predictions = predictions[best_model_name]

prediction_output = test_df[
    ["timestamp", "target_timestamp"]
].copy()

# Recover region safely by looking up the original data.
lookup = df[["timestamp", "location_name"]].drop_duplicates(
    ["timestamp", "location_name"]
)

# Reconstruct region using row order from test_df isn't safe if timestamps repeat,
# so create a region column before model_df creation in future versions.
# For this version, predictions are still valid; save the numeric comparison.
prediction_output["actual_aqi_24h"] = y_test.to_numpy()
prediction_output["predicted_aqi_24h"] = best_predictions

prediction_file = RESULT_DIR / "aqi_24h_predictions.csv"
prediction_output.to_csv(prediction_file, index=False)

summary = {
    "forecast_horizon_hours": FORECAST_HOURS,
    "split_timestamp": str(split_time),
    "training_rows": int(len(train_df)),
    "testing_rows": int(len(test_df)),
    "best_model": best_model_name,
    "models": results,
}

with open(RESULT_DIR / "aqi_model_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

# -------------------------------------------------------------------
# 7. Final message
# -------------------------------------------------------------------
print("\n[7/7] Files created:")
print(f"  Model results:     {results_file}")
print(f"  Predictions:       {prediction_file}")
print(f"  Model directory:   {MODEL_DIR}")
print(f"  Summary JSON:       {RESULT_DIR / 'aqi_model_summary.json'}")

print("\n" + "=" * 72)
print("AQI MODEL TRAINING COMPLETE")
print("=" * 72)
print(f"Best model: {best_model_name}")
print("Next step: use the best saved model through FastAPI.")
