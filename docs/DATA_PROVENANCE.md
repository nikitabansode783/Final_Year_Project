# Data Provenance and Model Limitations

## Air quality
The project uses the processed AQI dataset stored at `data/raw/processed_aqi_data.csv`.
Coverage: 2019-01-01 to 2024-01-01, with hourly observations for Delhi, Faridabad, Ghaziabad, Gurgaon and Noida.

## Weather
Weather records are stored in `data/raw/weather/` and cover 2020-01-01 to 2025-04-06.
Delhi is used as a documented proxy weather source for Gurgaon and Noida in the current integrated dataset.

## Fire hotspots
FIRMS fire hotspot files are stored in `data/raw/fire_hotspots/`.
The processed fire layer is a separate spatial hotspot layer because its observed period does not overlap the historical AQI training period.

## GIS
District boundaries are stored in `data/raw/gis/` and processed into five NCR regions.

## AQI forecasting
The 24-hour AQI forecasting experiment compares Linear Regression, Random Forest and XGBoost.
The selected model is XGBoost based on the lowest test RMSE.

## Hotspot prediction
The future hotspot classifier predicts whether 24-hour-ahead AQI reaches the high-risk threshold of AQI >= 150.

## Pollution potential
Pollution potential is an engineering decision-support index combining pollution intensity and atmospheric stagnation. It is not a causal source-attribution model.

## Source identification limitation
The current implementation provides source indicators and spatial fire-hotspot context, but it does not claim exact causal source percentages. Exact source apportionment would require source-specific measurements or a validated source-attribution model.

## Live-data limitation
The current dashboard is based primarily on stored historical datasets. Any label suggesting live data should only be used after a live external source is actually connected.
