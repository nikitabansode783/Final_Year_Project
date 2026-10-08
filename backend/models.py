from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from backend.db import Base


class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    district = Column(String(100))
    state = Column(String(100))
    geometry = Column(Geometry("POLYGON", srid=4326))

    air_quality = relationship("AirQuality", back_populates="region")
    weather = relationship("Weather", back_populates="region")
    hotspots = relationship("Hotspot", back_populates="region")


class AirQuality(Base):
    __tablename__ = "air_quality"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    timestamp = Column(DateTime, nullable=False)

    aqi = Column(Float)
    pm25 = Column(Float)
    pm10 = Column(Float)
    no2 = Column(Float)
    so2 = Column(Float)
    co = Column(Float)
    o3 = Column(Float)

    region = relationship("Region", back_populates="air_quality")


class Weather(Base):
    __tablename__ = "weather"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    timestamp = Column(DateTime, nullable=False)

    temperature = Column(Float)
    humidity = Column(Float)
    wind_speed = Column(Float)
    wind_direction = Column(Float)
    pressure = Column(Float)
    rainfall = Column(Float)

    region = relationship("Region", back_populates="weather")


class Hotspot(Base):
    __tablename__ = "hotspots"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    timestamp = Column(DateTime, nullable=False)

    latitude = Column(Float)
    longitude = Column(Float)
    risk_score = Column(Float)
    risk_level = Column(String(50))
    source_type = Column(String(100))

    location = Column(Geometry("POINT", srid=4326))

    region = relationship("Region", back_populates="hotspots")


class AQIForecast(Base):
    __tablename__ = "aqi_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    forecast_time = Column(DateTime, nullable=False)

    predicted_aqi = Column(Float)
    predicted_pm25 = Column(Float)
    predicted_pm10 = Column(Float)

    model_name = Column(String(100))
    mae = Column(Float)
    rmse = Column(Float)
    r2 = Column(Float)


class PollutionRisk(Base):
    __tablename__ = "pollution_risk"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    timestamp = Column(DateTime, nullable=False)

    risk_score = Column(Float)
    risk_level = Column(String(50))
    traffic_factor = Column(Float)
    weather_factor = Column(Float)
    fire_factor = Column(Float)
    industrial_factor = Column(Float)
    dust_factor = Column(Float)


class PolicyRecommendation(Base):
    __tablename__ = "policy_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    timestamp = Column(DateTime, nullable=False)

    recommendation_type = Column(String(100))
    priority = Column(String(50))
    recommendation = Column(Text)