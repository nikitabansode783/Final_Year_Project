"""
Future Hotspot Prediction - Delhi-NCR Pollution EDSS

Predicts whether AQI 24 hours ahead will be >= 150.
This is a predictive hotspot-risk classifier, not causal source attribution.
"""
from pathlib import Path
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, f1_score, roc_auc_score
from sklearn.preprocessing import LabelEncoder

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/"data"/"processed"/"aqi_weather_integrated.csv"
OUT = ROOT/"data"/"processed"
MODEL_DIR = ROOT/"ml"/"saved_models"
OUT.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(SRC)
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.sort_values(["location_name","timestamp"]).copy()
df["future_aqi_24h"] = df.groupby("location_name")["aqi"].shift(-24)
df["future_hotspot"] = (df["future_aqi_24h"] >= 150).astype(int)

def detect(names):
    for n in names:
        if n in df.columns: return n
    return None

features = [
    "aqi","pm25","pm10","no2","so2","co","o3",
    "hour","day","month","day_of_week","is_weekend"
]
for cands in [
    ["temperature_2m","temperature"],
    ["relative_humidity_2m","humidity"],
    ["wind_speed_10m","wind_speed"],
    ["wind_direction_10m","wind_direction"],
    ["pressure_msl","pressure"],
    ["precipitation","rainfall"]
]:
    c=detect(cands)
    if c: features.append(c)

# Stable numeric location encoding
le = LabelEncoder()
df["location_code"] = le.fit_transform(df["location_name"].astype(str))
features.append("location_code")

# Add useful lag features
for lag in [1,3,6,12,24]:
    name=f"aqi_lag_{lag}"
    df[name]=df.groupby("location_name")["aqi"].shift(lag)
    features.append(name)

model_df = df[["timestamp","location_name","future_aqi_24h","future_hotspot"]+features].copy()
model_df = model_df.replace([np.inf,-np.inf], np.nan).dropna()

# Chronological 80/20 split
model_df = model_df.sort_values("timestamp")
split = int(len(model_df)*0.80)
train = model_df.iloc[:split]
test = model_df.iloc[split:]

X_train=train[features]
y_train=train["future_hotspot"]
X_test=test[features]
y_test=test["future_hotspot"]

model=RandomForestClassifier(
    n_estimators=250,
    max_depth=14,
    min_samples_leaf=3,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1
)
model.fit(X_train,y_train)
pred=model.predict(X_test)
prob=model.predict_proba(X_test)[:,1]

print("="*70)
print("FUTURE HOTSPOT PREDICTION")
print("="*70)
print(f"Training rows: {len(train):,}")
print(f"Testing rows: {len(test):,}")
print(f"Accuracy: {accuracy_score(y_test,pred):.4f}")
print(f"F1: {f1_score(y_test,pred):.4f}")
try:
    print(f"ROC-AUC: {roc_auc_score(y_test,prob):.4f}")
except Exception:
    pass

joblib.dump(
    {"model":model,"features":features,"label_encoder":le},
    MODEL_DIR/"random_forest_hotspot.joblib"
)

# Test predictions with actual future AQI
test_out=test[["timestamp","location_name","future_aqi_24h"]].copy()
test_out["hotspot_probability"]=(prob*100).round(2)
test_out["predicted_hotspot"]=pred
test_out["risk_category"]=np.where(pred==1,"HIGH","LOW")
test_out.to_csv(OUT/"future_hotspot_predictions.csv",index=False)

# Current/latest prediction for each region
latest=df.sort_values("timestamp").groupby("location_name").tail(1).copy()
latest=latest.dropna(subset=features)
latest["hotspot_probability"]=(model.predict_proba(latest[features])[:,1]*100).round(2)
latest["predicted_hotspot"]=model.predict(latest[features])
latest["risk_category"]=np.where(latest["predicted_hotspot"]==1,"HIGH","LOW")
latest["forecast_timestamp"]=latest["timestamp"] + pd.Timedelta(hours=24)

summary=latest[[
    "location_name","timestamp","forecast_timestamp",
    "aqi","hotspot_probability","predicted_hotspot","risk_category"
]].rename(columns={"timestamp":"latest_timestamp"})
summary.to_csv(OUT/"future_hotspot_region_summary.csv",index=False)

imp=pd.DataFrame({"feature":features,"importance":model.feature_importances_}).sort_values("importance",ascending=False)
imp.to_csv(OUT/"hotspot_feature_importance.csv",index=False)

print("\nRegional current hotspot-risk summary:")
print(summary.to_string(index=False))
print("="*70)
print("Hotspot prediction outputs saved successfully.")
print("="*70)
