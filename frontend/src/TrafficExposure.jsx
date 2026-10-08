
import React, { useEffect, useState } from "react";

export default function TrafficExposure({ selectedRegion }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/api/traffic/exposure/${encodeURIComponent(selectedRegion || "Delhi")}`
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const result = await response.json();
        if (!cancelled) {
          setData(result);
          setError("");
        }
      } catch (err) {
        if (!cancelled) setError("Traffic exposure data unavailable.");
      }
    }

    load();
    const timer = setInterval(load, 15 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [selectedRegion]);

  if (error) {
    return (
      <section className="panel traffic-panel">
        <div className="panel-head">
          <div>
            <h2>Traffic Exposure</h2>
            <span>OpenStreetMap road-network analysis</span>
          </div>
        </div>
        <div className="live-error">{error}</div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="panel traffic-panel">
        <div className="panel-head">
          <div>
            <h2>Traffic Exposure</h2>
            <span>Loading road-network data...</span>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="panel traffic-panel">
      <div className="panel-head">
        <div>
          <h2>Traffic Exposure</h2>
          <span>{data.location} · OpenStreetMap road network</span>
        </div>
        <span className="pill">Spatial Proxy</span>
      </div>

      <div className="traffic-main">
        <div>
          <small>Exposure Score</small>
          <strong>{data.exposure_score}</strong>
          <span>{data.category}</span>
        </div>
        <div className="traffic-info">
          <b>{data.road_segments.toLocaleString()}</b>
          <span>mapped road segments</span>
        </div>
      </div>

      <div className="traffic-classes">
        {Object.entries(data.road_class_counts || {})
          .sort((a, b) => b[1] - a[1])
          .slice(0, 6)
          .map(([road, count]) => (
            <div key={road}>
              <span>{road}</span>
              <b>{count.toLocaleString()}</b>
            </div>
          ))}
      </div>

      <p className="traffic-note">
        This indicator represents road-network exposure and potential
        traffic-related emission influence. It is not a measured congestion
        or vehicle-speed value.
      </p>
    </section>
  );
}
