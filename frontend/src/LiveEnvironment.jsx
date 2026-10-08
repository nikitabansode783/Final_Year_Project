import React, { useEffect, useState } from "react";

const locations = ["Delhi", "Faridabad", "Ghaziabad", "Gurgaon", "Noida"];

function getAqiStatus(aqi) {
  if (aqi === null || aqi === undefined) return "Unavailable";
  if (aqi <= 50) return "Good";
  if (aqi <= 100) return "Moderate";
  if (aqi <= 150) return "Unhealthy for Sensitive Groups";
  if (aqi <= 200) return "Unhealthy";
  if (aqi <= 300) return "Very Unhealthy";
  return "Hazardous";
}

export default function LiveEnvironment({ selectedRegion }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const location = selectedRegion || "Delhi";

  useEffect(() => {
    let cancelled = false;

    async function loadLiveData() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(
          `http://127.0.0.1:8000/api/live/environment/${encodeURIComponent(location)}`
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();

        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError("Unable to load live environmental data.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadLiveData();

    const interval = setInterval(loadLiveData, 5 * 60 * 1000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [location]);

  if (loading) {
    return (
      <section className="dashboard-card live-environment-card">
        <div className="section-heading">
          <div>
            <span className="section-eyebrow">LIVE MONITORING</span>
            <h2>Live Environmental Conditions</h2>
          </div>
        </div>

        <div className="live-loading">
          Loading current environmental conditions...
        </div>
      </section>
    );
  }

  if (error || !data) {
    return (
      <section className="dashboard-card live-environment-card">
        <div className="section-heading">
          <div>
            <span className="section-eyebrow">LIVE MONITORING</span>
            <h2>Live Environmental Conditions</h2>
          </div>
        </div>

        <div className="live-error">
          {error || "Live data unavailable"}
        </div>
      </section>
    );
  }

  const aq = data.air_quality || {};
  const weather = data.weather || {};

  return (
    <section className="dashboard-card live-environment-card">
      <div className="section-heading live-heading">
        <div>
          <span className="section-eyebrow">LIVE MONITORING</span>
          <h2>Live Environmental Conditions</h2>
          <p>
            Current atmospheric conditions for{" "}
            <strong>{data.location}</strong>
          </p>
        </div>

        <div className="live-status">
          <span className="live-dot"></span>
          LIVE
        </div>
      </div>

      <div className="live-source">
        <span>Source: {data.source}</span>
        <span>
          Updated: {data.timestamp ? data.timestamp.replace("T", " ") : "—"}
        </span>
      </div>

      <div className="live-aqi-main">
        <div>
          <span className="metric-label">US AQI</span>
          <div className="live-aqi-value">{aq.us_aqi ?? "—"}</div>
          <div className="live-aqi-status">
            {getAqiStatus(aq.us_aqi)}
          </div>
        </div>

        <div className="live-aqi-note">
          <strong>Live atmospheric monitoring</strong>
          <p>
            These values are retrieved from Open-Meteo/CAMS and are displayed
            separately from the historical AQI model used for forecasting.
          </p>
        </div>
      </div>

      <div className="live-metrics-grid">
        <div className="live-metric">
          <span>PM2.5</span>
          <strong>{aq.pm25 ?? "—"}</strong>
          <small>µg/m³</small>
        </div>

        <div className="live-metric">
          <span>PM10</span>
          <strong>{aq.pm10 ?? "—"}</strong>
          <small>µg/m³</small>
        </div>

        <div className="live-metric">
          <span>NO₂</span>
          <strong>{aq.no2 ?? "—"}</strong>
          <small>µg/m³</small>
        </div>

        <div className="live-metric">
          <span>SO₂</span>
          <strong>{aq.so2 ?? "—"}</strong>
          <small>µg/m³</small>
        </div>

        <div className="live-metric">
          <span>O₃</span>
          <strong>{aq.o3 ?? "—"}</strong>
          <small>µg/m³</small>
        </div>

        <div className="live-metric">
          <span>CO</span>
          <strong>{aq.co ?? "—"}</strong>
          <small>µg/m³</small>
        </div>
      </div>

      <div className="live-weather-section">
        <h3>Current Weather Conditions</h3>

        <div className="live-weather-grid">
          <div>
            <span>Temperature</span>
            <strong>{weather.temperature ?? "—"} °C</strong>
          </div>

          <div>
            <span>Humidity</span>
            <strong>{weather.humidity ?? "—"} %</strong>
          </div>

          <div>
            <span>Wind Speed</span>
            <strong>{weather.wind_speed ?? "—"} km/h</strong>
          </div>

          <div>
            <span>Wind Direction</span>
            <strong>{weather.wind_direction ?? "—"}°</strong>
          </div>

          <div>
            <span>Pressure</span>
            <strong>{weather.pressure ?? "—"} hPa</strong>
          </div>

          <div>
            <span>Precipitation</span>
            <strong>{weather.precipitation ?? "—"} mm</strong>
          </div>
        </div>
      </div>
    </section>
  );
}