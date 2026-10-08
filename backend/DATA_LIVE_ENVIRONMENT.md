# Live Environmental Data Feature

This adds a separate live environmental layer to the Delhi-NCR EDSS.

Source:
- Open-Meteo Air Quality API
- Open-Meteo Weather API
- Air-quality model data exposed by Open-Meteo is based on CAMS.

Supported regions:
Delhi, Faridabad, Ghaziabad, Gurgaon, Noida

Endpoints:
GET /api/live/health
GET /api/live/environment/{location}

Important:
- The existing historical AQI database and ML training pipeline are NOT modified.
- The live AQI returned here is US AQI from Open-Meteo, so it should be labelled separately from the project's historical India AQI values.
- This avoids mixing two different AQI scales.

Install:
1. Copy backend/live_environment.py into project/backend/
2. Copy backend/install_live_feature.py into project/backend/
3. Run from project root:
   python backend/install_live_feature.py
4. Restart FastAPI.
5. Run:
   python backend/test_live_environment.py
