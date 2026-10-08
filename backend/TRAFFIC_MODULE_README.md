
# Traffic Exposure Module

This module adds a traffic-related environmental factor using OpenStreetMap road-network data through the Overpass API.

Important:
- It is a spatial road-network exposure proxy.
- It is NOT live congestion, speed, or traffic-volume data.
- It should be described in the project as a traffic/road-network exposure factor.
- If a TomTom traffic API key is later available, this module can be upgraded to measured live traffic conditions.

Backend endpoints:
- /api/traffic/health
- /api/traffic/exposure/{location}
- /api/traffic/all
