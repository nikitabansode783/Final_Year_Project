from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from pathlib import Path
from datetime import datetime
from functools import lru_cache

import pandas as pd
import io


router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"]
)


ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"


LOCATIONS = [
    "Delhi",
    "Faridabad",
    "Ghaziabad",
    "Gurgaon",
    "Noida"
]


def canonical(location):
    return next(
        (
            x for x in LOCATIONS
            if x.lower() == location.lower()
        ),
        None
    )


# ============================================================
# DATA LOADERS
# ============================================================

@lru_cache(maxsize=1)
def load_integrated():
    return pd.read_csv(
        PROCESSED / "aqi_weather_integrated.csv",
        parse_dates=["timestamp"]
    )


@lru_cache(maxsize=1)
def load_potential():
    return pd.read_csv(
        PROCESSED / "pollution_potential_region_summary.csv"
    )


@lru_cache(maxsize=1)
def load_hotspots():
    return pd.read_csv(
        PROCESSED / "future_hotspot_region_summary.csv"
    )


@lru_cache(maxsize=1)
def load_fire():
    return pd.read_csv(
        PROCESSED / "fire_hotspots_region_summary.csv"
    )


# ============================================================
# FORECAST
# ============================================================

def get_forecast(location):

    try:
        from backend.forecast_service import predict_24h_aqi

        return predict_24h_aqi(location)

    except Exception:
        return {
            "current_aqi": None,
            "predicted_24h_aqi": None,
            "model": "XGBoost"
        }


# ============================================================
# BUILD REPORT
# ============================================================

def build_report(location):

    location = canonical(location)

    if not location:
        raise HTTPException(
            status_code=404,
            detail="Unsupported Delhi-NCR region"
        )

    # --------------------------------------------------------
    # Historical data
    # --------------------------------------------------------

    df = load_integrated()

    rows = df[
        df["location_name"]
        .astype(str)
        .str.lower()
        == location.lower()
    ]

    if rows.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {location}"
        )

    latest = rows.sort_values("timestamp").iloc[-1]


    # --------------------------------------------------------
    # AI Forecast
    # --------------------------------------------------------

    forecast = get_forecast(location)


    # --------------------------------------------------------
    # Pollution Potential
    # --------------------------------------------------------

    potential = load_potential()

    potential_row = potential[
        potential["location_name"]
        .astype(str)
        .str.lower()
        == location.lower()
    ]


    # --------------------------------------------------------
    # Future Hotspot Prediction
    # --------------------------------------------------------

    hotspot = load_hotspots()

    hotspot_row = hotspot[
        hotspot["location_name"]
        .astype(str)
        .str.lower()
        == location.lower()
    ]


    # --------------------------------------------------------
    # Fire Hotspots
    # --------------------------------------------------------

    fire_count = 0

    try:

        fire = load_fire()

        possible_region_columns = [
            "region",
            "location_name",
            "location",
            "district",
            "Region",
            "Location"
        ]

        region_column = next(
            (
                c for c in possible_region_columns
                if c in fire.columns
            ),
            None
        )

        if region_column:

            fire_row = fire[
                fire[region_column]
                .astype(str)
                .str.lower()
                == location.lower()
            ]

            if not fire_row.empty:

                possible_count_columns = [
                    "hotspot_count",
                    "count",
                    "fire_count",
                    "hotspots"
                ]

                count_column = next(
                    (
                        c for c in possible_count_columns
                        if c in fire.columns
                    ),
                    None
                )

                if count_column:

                    fire_count = int(
                        fire_row.iloc[0][count_column]
                    )

    except Exception:

        fire_count = 0


    # --------------------------------------------------------
    # Pollution Potential Values
    # --------------------------------------------------------

    potential_score = (
        float(
            potential_row.iloc[0][
                "average_pollution_potential"
            ]
        )
        if not potential_row.empty
        else 0
    )

    potential_category = (
        str(
            potential_row.iloc[0][
                "risk_category"
            ]
        )
        if not potential_row.empty
        else "N/A"
    )


    # --------------------------------------------------------
    # Hotspot Prediction Values
    # --------------------------------------------------------

    hotspot_probability = (
        float(
            hotspot_row.iloc[0][
                "hotspot_probability"
            ]
        )
        if not hotspot_row.empty
        else 0
    )

    predicted_hotspot = (
        int(
            hotspot_row.iloc[0][
                "predicted_hotspot"
            ]
        )
        if not hotspot_row.empty
        else 0
    )

    hotspot_category = (
        str(
            hotspot_row.iloc[0][
                "risk_category"
            ]
        )
        if not hotspot_row.empty
        else "N/A"
    )


    # --------------------------------------------------------
    # Policy Recommendations
    # --------------------------------------------------------

    recommendations = []


    if potential_category == "VERY HIGH":

        recommendations.append(
            "Activate high-pollution response measures."
        )

        recommendations.append(
            "Restrict or closely regulate "
            "dust-generating activities."
        )


    elif potential_category == "HIGH":

        recommendations.append(
            "Increase emission-control inspections."
        )

        recommendations.append(
            "Strengthen public health advisories."
        )


    elif potential_category == "MODERATE":

        recommendations.append(
            "Continue enhanced monitoring "
            "and preventive advisories."
        )


    else:

        recommendations.append(
            "Continue routine environmental monitoring."
        )


    # --------------------------------------------------------
    # PM2.5 Recommendation
    # --------------------------------------------------------

    try:

        pm25_value = float(
            latest.get("pm25", 0) or 0
        )

    except Exception:

        pm25_value = 0


    if pm25_value >= 75:

        recommendations.append(
            "Prioritize particulate-matter reduction "
            "and dust suppression."
        )


    # --------------------------------------------------------
    # NO2 Recommendation
    # --------------------------------------------------------

    try:

        no2_value = float(
            latest.get("no2", 0) or 0
        )

    except Exception:

        no2_value = 0


    if no2_value >= 50:

        recommendations.append(
            "Prioritize traffic and "
            "combustion-emission controls."
        )


    # --------------------------------------------------------
    # Hotspot Recommendation
    # --------------------------------------------------------

    if predicted_hotspot == 1:

        recommendations.append(
            "Prepare targeted response for "
            "the predicted hotspot region."
        )


    # ========================================================
    # FINAL REPORT JSON
    # ========================================================

    return {

        "generated_at":
            datetime.now()
            .astimezone()
            .isoformat(),

        "location":
            location,


        # ----------------------------------------------------
        # Historical Observation
        # ----------------------------------------------------

        "historical_observation": {

            "timestamp":
                str(latest["timestamp"]),

            "aqi":
                round(
                    float(latest["aqi"]),
                    2
                ),

            "pm25":
                round(
                    float(latest["pm25"]),
                    2
                ),

            "pm10":
                round(
                    float(latest["pm10"]),
                    2
                ),

            "no2":
                round(
                    float(latest["no2"]),
                    2
                ),

            "so2":
                round(
                    float(latest["so2"]),
                    2
                ),

            "co":
                round(
                    float(latest["co"]),
                    2
                ),

            "o3":
                round(
                    float(latest["o3"]),
                    2
                )
        },


        # ----------------------------------------------------
        # Forecast
        # ----------------------------------------------------

        "forecast": {

            "current_aqi":
                forecast.get(
                    "current_aqi"
                ),

            "predicted_24h_aqi":
                forecast.get(
                    "predicted_24h_aqi"
                ),

            "model":
                forecast.get(
                    "model",
                    "XGBoost"
                )
        },


        # ----------------------------------------------------
        # Weather
        # ----------------------------------------------------

        "weather": {

            "temperature":
                float(
                    latest.get(
                        "temperature",
                        0
                    ) or 0
                ),

            "humidity":
                float(
                    latest.get(
                        "relative_humidity",
                        0
                    ) or 0
                ),

            "wind_speed":
                float(
                    latest.get(
                        "wind_speed",
                        0
                    ) or 0
                )
        },


        # ----------------------------------------------------
        # Pollution Potential
        # ----------------------------------------------------

        "pollution_potential": {

            "score":
                round(
                    potential_score,
                    2
                ),

            "category":
                potential_category
        },


        # ----------------------------------------------------
        # Hotspot Prediction
        # ----------------------------------------------------

        "hotspot_prediction": {

            "probability":
                round(
                    hotspot_probability,
                    4
                ),

            "predicted_hotspot":
                predicted_hotspot,

            "risk_category":
                hotspot_category
        },


        # ----------------------------------------------------
        # Fire Hotspots
        # ----------------------------------------------------

        "fire_hotspots": {

            "processed_hotspot_count":
                fire_count
        },


        # ----------------------------------------------------
        # Recommendations
        # ----------------------------------------------------

        "policy_recommendations":
            recommendations,


        # ----------------------------------------------------
        # Methodology
        # ----------------------------------------------------

        "methodology_note":

            "The system combines historical "
            "air-quality and weather observations, "
            "machine-learning AQI forecasting, "
            "pollution potential scoring, future "
            "hotspot classification, fire hotspot "
            "information and policy rules. "
            "Recommendations are decision-support guidance."
    }


# ============================================================
# JSON REPORT API
# ============================================================

@router.get("/{location}")
def report_json(location: str):

    return build_report(location)


# ============================================================
# PDF REPORT API
# ============================================================

@router.get("/{location}/pdf")
def report_pdf(location: str):

    data = build_report(location)

    try:

        from reportlab.lib.pagesizes import A4

        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle
        )

        from reportlab.lib import colors

        from reportlab.lib.styles import (
            getSampleStyleSheet
        )

    except ImportError:

        raise HTTPException(
            status_code=500,
            detail=(
                "PDF dependency missing. "
                "Run: pip install reportlab"
            )
        )


    # --------------------------------------------------------
    # PDF Buffer
    # --------------------------------------------------------

    buffer = io.BytesIO()


    doc = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )


    styles = getSampleStyleSheet()

    story = []


    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    story.append(

        Paragraph(
            "Delhi-NCR Environmental "
            "Decision Support System",
            styles["Title"]
        )
    )


    story.append(

        Paragraph(
            f"Regional Environmental Report — "
            f"{data['location']}",
            styles["Heading2"]
        )
    )


    story.append(

        Paragraph(
            f"Generated: {data['generated_at']}",
            styles["Normal"]
        )
    )


    story.append(
        Spacer(1, 15)
    )


    # --------------------------------------------------------
    # Table Helper
    # --------------------------------------------------------

    def add_table(title, rows):

        story.append(

            Paragraph(
                title,
                styles["Heading3"]
            )
        )


        table = Table(

            rows,

            colWidths=[
                190,
                300
            ]
        )


        table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6
                )

            ])
        )


        story.append(table)

        story.append(
            Spacer(1, 12)
        )


    # --------------------------------------------------------
    # Historical Data Table
    # --------------------------------------------------------

    h = data["historical_observation"]


    add_table(

        "Latest Historical Observation",

        [

            ["Metric", "Value"],

            ["Timestamp", h["timestamp"]],

            ["AQI", h["aqi"]],

            ["PM2.5", h["pm25"]],

            ["PM10", h["pm10"]],

            ["NO2", h["no2"]],

            ["SO2", h["so2"]],

            ["CO", h["co"]],

            ["O3", h["o3"]]

        ]
    )


    # --------------------------------------------------------
    # Forecast Table
    # --------------------------------------------------------

    f = data["forecast"]


    add_table(

        "AI Forecast",

        [

            ["Metric", "Value"],

            [
                "Current AQI",
                f["current_aqi"]
            ],

            [
                "Predicted 24-hour AQI",
                f["predicted_24h_aqi"]
            ],

            [
                "Model",
                f["model"]
            ]

        ]
    )


    # --------------------------------------------------------
    # Risk Assessment
    # --------------------------------------------------------

    p = data["pollution_potential"]

    hs = data["hotspot_prediction"]


    add_table(

        "Risk Assessment",

        [

            ["Metric", "Value"],

            [
                "Pollution Potential Score",
                p["score"]
            ],

            [
                "Pollution Risk",
                p["category"]
            ],

            [
                "Hotspot Probability",
                f"{hs['probability'] * 100:.2f}%"
            ],

            [
                "Predicted Hotspot",
                "YES"
                if hs["predicted_hotspot"]
                else "NO"
            ],

            [
                "Hotspot Risk",
                hs["risk_category"]
            ],

            [
                "Processed Fire Hotspots",
                data["fire_hotspots"]
                ["processed_hotspot_count"]
            ]

        ]
    )


    # --------------------------------------------------------
    # Policy Recommendations
    # --------------------------------------------------------

    story.append(

        Paragraph(
            "Policy Recommendations",
            styles["Heading3"]
        )
    )


    for recommendation in data[
        "policy_recommendations"
    ]:

        story.append(

            Paragraph(
                "• " + recommendation,
                styles["Normal"]
            )
        )

        story.append(
            Spacer(1, 4)
        )


    story.append(
        Spacer(1, 12)
    )


    # --------------------------------------------------------
    # Methodology Note
    # --------------------------------------------------------

    story.append(

        Paragraph(
            data["methodology_note"],
            styles["Normal"]
        )
    )


    # --------------------------------------------------------
    # Build PDF
    # --------------------------------------------------------

    doc.build(story)


    return Response(

        content=buffer.getvalue(),

        media_type="application/pdf",

        headers={

            "Content-Disposition":
                f'attachment; filename="{location}_EDSS_Report.pdf"'

        }
    )