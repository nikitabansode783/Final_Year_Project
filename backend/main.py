from backend.report_service import router as report_router
from backend.traffic_exposure import router as traffic_exposure_router
from backend.live_environment import router as live_environment_router
from pathlib import Path
import os
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from backend.forecast_service import predict_24h_aqi
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "backend" / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found in backend/.env")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="Delhi-NCR Pollution EDSS API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

def rows(result): return [dict(r._mapping) for r in result]

@app.get("/")
def root(): return {"project":"Delhi-NCR Pollution EDSS","status":"running","version":"1.0.0"}

@app.get("/api/health")
def health():
    try:
        with engine.connect() as c: c.execute(text("SELECT 1"))
        return {"status":"healthy","database":"connected"}
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")

@app.get("/api/regions")
def regions():
    with engine.connect() as c:
        return rows(c.execute(text("""
            SELECT id,name,district,state,ST_AsGeoJSON(geometry)::json AS geometry
            FROM regions ORDER BY id
        """)))

@app.get("/api/gis/geojson")
def gis_geojson():
    data=regions()
    return {"type":"FeatureCollection","features":[
        {"type":"Feature","properties":{
            "id":r["id"],"name":r["name"],"district":r["district"],"state":r["state"]
        },"geometry":r["geometry"]} for r in data
    ]}

@app.get("/api/dashboard/summary")
def dashboard_summary():
    with engine.connect() as c:
        data=rows(c.execute(text("""
            SELECT r.id region_id,r.name location,r.district,r.state,
                   aq.timestamp,aq.aqi,aq.pm25,aq.pm10,aq.no2,aq.so2,aq.co,aq.o3,
                   w.temperature,w.humidity,w.wind_speed,w.wind_direction,w.pressure,w.rainfall
            FROM regions r
            JOIN LATERAL (
                SELECT * FROM air_quality a WHERE a.region_id=r.id
                ORDER BY a.timestamp DESC LIMIT 1
            ) aq ON TRUE
            LEFT JOIN LATERAL (
                SELECT * FROM weather ww WHERE ww.region_id=r.id
                ORDER BY ABS(EXTRACT(EPOCH FROM (ww.timestamp-aq.timestamp))) LIMIT 1
            ) w ON TRUE
            ORDER BY r.id
        """)))
    return {"regions":data,"region_count":len(data)}

@app.get("/api/aqi/current/{location}")
def current_aqi(location:str):
    with engine.connect() as c:
        r=c.execute(text("""
            SELECT r.name location,a.timestamp,a.aqi,a.pm25,a.pm10,a.no2,a.so2,a.co,a.o3
            FROM air_quality a JOIN regions r ON r.id=a.region_id
            WHERE LOWER(r.name)=LOWER(:location) ORDER BY a.timestamp DESC LIMIT 1
        """),{"location":location}).mappings().first()
    if not r: raise HTTPException(404,"Location not found")
    return dict(r)

@app.get("/api/aqi/history/{location}")
def aqi_history(
    location: str,
    days: int = Query(30, ge=1, le=365),
):
    with engine.connect() as conn:

        # First find the latest AQI timestamp for the selected region
        latest_result = conn.execute(
            text("""
                SELECT MAX(a.timestamp)
                FROM air_quality a
                JOIN regions r ON r.id = a.region_id
                WHERE LOWER(r.name) = LOWER(:location)
            """),
            {"location": location},
        )

        latest_timestamp = latest_result.scalar()

        if latest_timestamp is None:
            raise HTTPException(
                status_code=404,
                detail=f"No AQI history found for {location}"
            )

        # Fetch only the requested historical period
        result = conn.execute(
            text("""
                SELECT
                    a.timestamp,
                    r.name AS location,
                    a.aqi,
                    a.pm25,
                    a.pm10,
                    a.no2,
                    a.so2,
                    a.co,
                    a.o3
                FROM air_quality a
                JOIN regions r ON r.id = a.region_id
                WHERE LOWER(r.name) = LOWER(:location)
                  AND a.timestamp >= :start_timestamp
                  AND a.timestamp <= :latest_timestamp
                ORDER BY a.timestamp ASC
            """),
            {
                "location": location,
                "start_timestamp": latest_timestamp - timedelta(days=days),
                "latest_timestamp": latest_timestamp,
            },
        )

        history_rows = [dict(row._mapping) for row in result]

    if not history_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No AQI history found for {location}"
        )

    return {
        "location": history_rows[0]["location"],
        "days": days,
        "count": len(history_rows),
        "data": history_rows,
    }

@app.get("/api/forecast/{location}")
def forecast(location:str):
    try: return predict_24h_aqi(location)
    except ValueError as e: raise HTTPException(400,str(e))
    except FileNotFoundError as e: raise HTTPException(500,str(e))

@app.get("/api/weather/current/{location}")
def weather(location:str):
    with engine.connect() as c:
        r=c.execute(text("""
            SELECT r.name location,w.timestamp,w.temperature,w.humidity,w.wind_speed,
                   w.wind_direction,w.pressure,w.rainfall
            FROM weather w JOIN regions r ON r.id=w.region_id
            WHERE LOWER(r.name)=LOWER(:location) ORDER BY w.timestamp DESC LIMIT 1
        """),{"location":location}).mappings().first()
    if not r: raise HTTPException(404,"Weather data not found")
    return dict(r)

def csv_json(path):
    p=ROOT/"data"/"processed"/path
    if not p.exists(): return None
    d=pd.read_csv(p).where(pd.notna(pd.read_csv(p)),None)
    return d.to_dict(orient="records")

@app.get("/api/pollution-potential")
def pollution_potential():
    p=ROOT/"data"/"processed"/"pollution_potential_region_summary.csv"
    if not p.exists(): raise HTTPException(404,"Run ml/04_pollution_potential.py first.")
    df=pd.read_csv(p).where(pd.notna(pd.read_csv(p)),None)
    return {"data":df.to_dict(orient="records")}

@app.get("/api/hotspots")
def hotspots():
    p=ROOT/"data"/"processed"/"future_hotspot_region_summary.csv"
    if not p.exists(): raise HTTPException(404,"Run ml/05_hotspot_prediction.py first.")
    df=pd.read_csv(p).where(pd.notna(pd.read_csv(p)),None)
    return {"data":df.to_dict(orient="records")}

@app.get("/api/fire-hotspots")
def fire_hotspots(limit:int=Query(500,ge=1,le=5000)):
    p=ROOT/"data"/"processed"/"fire_hotspots_ncr.csv"
    if not p.exists(): raise HTTPException(404,"Run ml/03_process_fire_hotspots.py first.")
    df=pd.read_csv(p).head(limit).where(pd.notna(pd.read_csv(p).head(limit)),None)
    return {"count":len(df),"data":df.to_dict(orient="records")}

@app.get("/api/statistics")
def statistics():
    with engine.connect() as c:
        return {"data":rows(c.execute(text("""
            SELECT r.name location,ROUND(AVG(a.aqi)::numeric,2) average_aqi,
                   ROUND(MAX(a.aqi)::numeric,2) maximum_aqi,
                   ROUND(AVG(a.pm25)::numeric,2) average_pm25,
                   ROUND(AVG(a.pm10)::numeric,2) average_pm10,
                   ROUND(AVG(a.no2)::numeric,2) average_no2,COUNT(*) observations
            FROM air_quality a JOIN regions r ON r.id=a.region_id
            GROUP BY r.name ORDER BY average_aqi DESC
        """)))}

@app.get("/api/policy/recommendations")
def policy_recommendations():
    pp=ROOT/"data"/"processed"/"pollution_potential_region_summary.csv"
    hs=ROOT/"data"/"processed"/"future_hotspot_region_summary.csv"
    if not pp.exists(): raise HTTPException(404,"Run pollution potential first.")
    pot=pd.read_csv(pp)
    hot=pd.read_csv(hs) if hs.exists() else pd.DataFrame()
    rec=[]
    for _,r in pot.iterrows():
        name=r["location_name"]; risk=str(r.get("risk_category","MODERATE"))
        actions=[]
        if risk=="VERY HIGH": actions += ["Activate high-pollution response measures","Restrict dust-generating construction where applicable"]
        elif risk=="HIGH": actions += ["Increase emission-control inspections","Strengthen public pollution advisories"]
        elif risk=="MODERATE": actions += ["Continue monitoring pollutant trends","Issue preventive public advisories during peaks"]
        else: actions += ["Maintain routine monitoring"]
        if float(r.get("average_pm25",0))>=60: actions.append("Prioritize PM2.5 emission reduction measures")
        if float(r.get("average_no2",0))>=40: actions.append("Review traffic-related emission controls")
        if not hot.empty and name in hot["location_name"].values:
            h=hot[hot["location_name"]==name].iloc[0]
            if int(h["predicted_hotspot"])==1: actions.append("Prepare targeted hotspot response for next 24 hours")
        rec.append({"location":name,"risk":risk,"priority":"HIGH" if risk in ["HIGH","VERY HIGH"] else "MEDIUM","recommendations":actions})
    return {"data":rec}


app.include_router(live_environment_router)
app.include_router(traffic_exposure_router)
app.include_router(report_router)
