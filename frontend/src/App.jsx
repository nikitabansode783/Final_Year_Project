import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import LiveEnvironment from "./LiveEnvironment";


const API = "http://127.0.0.1:8000";
const locations = ["Delhi","Faridabad","Ghaziabad","Gurgaon","Noida"];

function aqiClass(aqi){
  if(aqi >= 300) return "severe";
  if(aqi >= 200) return "verypoor";
  if(aqi >= 150) return "poor";
  if(aqi >= 100) return "moderate";
  return "good";
}
function riskClass(risk){
  return String(risk||"").toLowerCase().replace(" ","-");
}
function fmt(v,d=1){ return v==null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d); }

function Sparkline({ data = [], field = "aqi" }) {
  if (!data.length) {
    return <div className="empty">No trend data available</div>;
  }

  // Convert hourly AQI data into daily average AQI
  const daily = {};

  data.forEach((item) => {
    if (!item.timestamp) return;

    const date = new Date(item.timestamp).toISOString().split("T")[0];
    const value = Number(item[field]);

    if (!Number.isFinite(value)) return;

    if (!daily[date]) {
      daily[date] = {
        total: 0,
        count: 0,
      };
    }

    daily[date].total += value;
    daily[date].count += 1;
  });

  const dailyData = Object.entries(daily)
    .map(([date, values]) => ({
      date,
      value: values.total / values.count,
    }))
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  if (!dailyData.length) {
    return <div className="empty">No valid AQI trend data</div>;
  }

  const vals = dailyData.map((x) => x.value);

  const max = Math.max(...vals);
  const min = Math.min(...vals);

  const points = dailyData
    .map((item, i) => {
      const x = (i / Math.max(dailyData.length - 1, 1)) * 100;
      const y =
        90 -
        ((item.value - min) / Math.max(max - min, 1)) * 75;

      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="trend-wrapper">
      <svg
        className="spark"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        <polyline
          points={points}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>

      <div className="trend-info">
        <span>
          Avg: <b>{(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)}</b>
        </span>

        <span>
          Max: <b>{max.toFixed(1)}</b>
        </span>

        <span>
          Min: <b>{min.toFixed(1)}</b>
        </span>
      </div>
    </div>
  );
}

export default function App(){
  const [summary,setSummary]=useState([]);
  const [selected,setSelected]=useState("Delhi");
  const [history,setHistory]=useState([]);
  const [forecast,setForecast]=useState(null);
  const [weather,setWeather]=useState(null);
  const [potential,setPotential]=useState([]);
  const [hotspots,setHotspots]=useState([]);
  const [policy,setPolicy]=useState([]);
  const [geo,setGeo]=useState(null);
  const [fire,setFire]=useState([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");

  const current=useMemo(()=>summary.find(x=>x.location===selected),[summary,selected]);
  const selectedPotential=potential.find(x=>x.location_name===selected);
  const selectedHotspot=hotspots.find(x=>x.location_name===selected);
  const selectedPolicy=policy.find(x=>x.location===selected);

  async function get(path){
    const r=await fetch(API+path);
    if(!r.ok) throw new Error(await r.text());
    return r.json();
  }

  useEffect(()=>{
    (async()=>{
      try{
        setLoading(true);
        const [s,p,h,g,f,pol]=await Promise.all([
          get("/api/dashboard/summary"),
          get("/api/pollution-potential").catch(()=>({data:[]})),
          get("/api/hotspots").catch(()=>({data:[]})),
          get("/api/gis/geojson"),
          get("/api/fire-hotspots?limit=500").catch(()=>({data:[]})),
          get("/api/policy/recommendations").catch(()=>({data:[]})),
        ]);
        setSummary(s.regions||[]);
        setPotential(p.data||[]);
        setHotspots(h.data||[]);
        setGeo(g);
        setFire(f.data||[]);
        setPolicy(pol.data||[]);
      }catch(e){setError(e.message)}
      finally{setLoading(false)}
    })();
  },[]);

  useEffect(() => {
  if (!selected) return;

  setHistory([]);
  setForecast(null);
  setWeather(null);

  // AQI history
  get(`/api/aqi/history/${encodeURIComponent(selected)}?days=30`)
    .then((h) => {
      console.log("AQI HISTORY RESPONSE:", h);
      console.log("AQI HISTORY RECORDS:", h?.data?.length || 0);

      setHistory(Array.isArray(h?.data) ? h.data : []);
    })
    .catch((e) => {
      console.error("AQI history error:", e);
    });

  // 24-hour forecast
  get(`/api/forecast/${encodeURIComponent(selected)}`)
    .then((f) => {
      setForecast(f || null);
    })
    .catch((e) => {
      console.error("Forecast error:", e);
    });

  // Weather
  get(`/api/weather/current/${encodeURIComponent(selected)}`)
    .then((w) => {
      setWeather(w || null);
    })
    .catch((e) => {
      console.error("Weather error:", e);
    });

}, [selected]);

  const avgAqi=summary.length ? summary.reduce((a,b)=>a+Number(b.aqi||0),0)/summary.length : 0;
  const highRisk=potential.filter(x=>["HIGH","VERY HIGH"].includes(String(x.risk_category))).length;
  const predictedHotspots=hotspots.filter(x=>Number(x.predicted_hotspot)===1).length;

  return <div className="app">
    <header className="topbar">
      <div>
        <div className="eyebrow">ENVIRONMENTAL DECISION SUPPORT SYSTEM</div>
        <h1>Delhi-NCR Pollution Intelligence</h1>
        <p>AI forecasting • pollution risk • hotspot intelligence • GIS decision support</p>
      </div>
      <div className="live"><span/> AI + HISTORICAL DATA</div>
    </header>

    {error && <div className="error">{error}</div>}

    <main className="content">
      <section className="hero-grid">
        <div className="hero-card">
          <div className="hero-top"><span>Selected Region</span><select value={selected} onChange={e=>setSelected(e.target.value)}>{locations.map(x=><option key={x}>{x}</option>)}</select></div>
          <div className="hero-number">{fmt(current?.aqi)}</div>
          <div className={`badge ${aqiClass(current?.aqi||0)}`}>{aqiClass(current?.aqi||0).toUpperCase()}</div>
          <div className="hero-meta">Latest observation: {current?.timestamp ? new Date(current.timestamp).toLocaleString() : "—"}</div>
        </div>
        <div className="metric-card"><span>24h Forecast</span><strong>{fmt(forecast?.predicted_aqi_24h)}</strong><small>AI / XGBoost</small></div>
        <div className="metric-card"><span>PM2.5</span><strong>{fmt(current?.pm25)}</strong><small>µg/m³</small></div>
        <div className="metric-card"><span>PM10</span><strong>{fmt(current?.pm10)}</strong><small>µg/m³</small></div>
      </section>

      <section className="kpi-row">
        <div><span>Regions monitored</span><b>{summary.length || 5}</b></div>
        <div><span>Average current AQI</span><b>{fmt(avgAqi)}</b></div>
        <div><span>High-risk regions</span><b>{highRisk}</b></div>
        <div><span>Predicted hotspots</span><b>{predictedHotspots}</b></div>
      </section>

      <LiveEnvironment selectedRegion={selected} />
      <section className="two-col">
        <div className="panel">
          <div className="panel-head"><div><h2>30-Day AQI Trend</h2><span>{selected}</span></div><span className="pill">Historical</span></div>
          <div className="chart"><Sparkline data={history} field="aqi"/></div>
          <div className="chart-labels"><span>Older</span><span>Latest</span></div>
        </div>
        <div className="panel">
          <div className="panel-head"><div><h2>Environmental Conditions</h2><span>Latest matching observation</span></div></div>
          <div className="weather-grid">
            <div><small>Temperature</small><b>{fmt(weather?.temperature)} °C</b></div>
            <div><small>Humidity</small><b>{fmt(weather?.humidity)} %</b></div>
            <div><small>Wind</small><b>{fmt(weather?.wind_speed)} km/h</b></div>
            <div><small>Pressure</small><b>{fmt(weather?.pressure)} hPa</b></div>
          </div>
          <div className="pollutants">
            <span>NO₂ <b>{fmt(current?.no2)}</b></span>
            <span>SO₂ <b>{fmt(current?.so2)}</b></span>
            <span>CO <b>{fmt(current?.co,2)}</b></span>
            <span>O₃ <b>{fmt(current?.o3)}</b></span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head"><div><h2>Regional Pollution Risk</h2><span>Decision-support potential index</span></div></div>
        <div className="region-grid">
          {potential.map(r=><button className={`region-card ${riskClass(r.risk_category)}`} key={r.location_name} onClick={()=>setSelected(r.location_name)}>
            <span>{r.location_name}</span><b>{fmt(r.average_pollution_potential)}</b><small>{r.risk_category}</small>
          </button>)}
        </div>
      </section>

      <section className="two-col">
        <div className="panel">
          <div className="panel-head"><div><h2>Future Hotspot Risk</h2><span>24-hour predictive classification</span></div></div>
          <div className="table">
            {hotspots.map(r=><div className="table-row" key={r.location_name}>
              <b>{r.location_name}</b><span>{fmt(r.hotspot_probability)}%</span><span className={`badge ${Number(r.predicted_hotspot) ? "poor":"good"}`}>{r.risk_category}</span>
            </div>)}
          </div>
        </div>
        <div className="panel">
          <div className="panel-head"><div><h2>Policy Recommendation</h2><span>{selected}</span></div></div>
          <div className="recommendation">
            <div className={`risk-title ${riskClass(selectedPolicy?.risk)}`}>{selectedPolicy?.risk || selectedPotential?.risk_category || "MONITORING"}</div>
            <ul>{(selectedPolicy?.recommendations||["Continue monitoring regional pollution conditions"]).map((x,i)=><li key={i}>{x}</li>)}</ul>
          </div>
        </div>
      </section>

      <section className="panel map-panel">
        <div className="panel-head"><div><h2>Delhi-NCR GIS Intelligence</h2><span>Regional boundaries and processed fire hotspots</span></div></div>
        <div className="map-wrap">
          {geo ? <MapContainer center={[28.55,77.25]} zoom={8.5} scrollWheelZoom={true}>
            <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
            <GeoJSON data={geo} style={(feature)=>({
              fillOpacity:0.22,
              weight:2,
              color: feature?.properties?.name===selected ? "#0f766e" : "#334155"
            })}/>
            {fire.map((p,i)=>{
              const lat=Number(p.latitude ?? p.lat), lon=Number(p.longitude ?? p.lon);
              if(!Number.isFinite(lat)||!Number.isFinite(lon)) return null;
              return <CircleMarker key={i} center={[lat,lon]} radius={4} pathOptions={{color:"#ef4444",fillOpacity:.7}}>
                <Popup>Fire hotspot<br/>Date: {p.acq_date||"—"}<br/>FRP: {p.frp||"—"}</Popup>
              </CircleMarker>
            })}
          </MapContainer> : <div className="empty">Loading GIS…</div>}
        </div>
      </section>

      <footer>Delhi-NCR Pollution EDSS • AI-assisted environmental decision support • Built with React, FastAPI, PostgreSQL/PostGIS and Python ML</footer>
    </main>
    {loading && <div className="loading">Loading intelligence dashboard…</div>}
  </div>
}
