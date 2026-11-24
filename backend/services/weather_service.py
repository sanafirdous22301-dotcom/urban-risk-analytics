"""
Weather Integration Service for URBANRISK Hyderabad.
Retrieves, validates, and stores live city-level weather observations from Open-Meteo API.
Preserves historical observations, enforces duplicate-prevention, and maintains strict
boundaries between ambient city-level weather and 1-km spatial IUPS flood hazard scoring.
"""

from datetime import datetime, timezone, timedelta
import json
import logging
from typing import Dict, Any, Optional, List
import urllib.request
import urllib.error

import pymongo
from database.mongodb import db as default_db

logger = logging.getLogger("urbanrisk.weather")

DEFAULT_LATITUDE = 17.3850
DEFAULT_LONGITUDE = 78.4867
LOCATION_NAME = "Hyderabad City Center"
TIMEZONE = "Asia/Kolkata"
SOURCE_NAME = "Open-Meteo Weather API"
SOURCE_URL = "https://open-meteo.com/"
SOURCE_ATTRIBUTION = "Weather data by Open-Meteo.com under CC BY 4.0"
SPATIAL_SCALE = "city_level_aggregate"
COLLECTION_NAME = "weather_observations"

WMO_CODE_MAP = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    71: ("Slight snow", "🌨️"),
    73: ("Moderate snow", "🌨️"),
    75: ("Heavy snow", "❄️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}


class WeatherService:
    def __init__(
        self,
        latitude: float = DEFAULT_LATITUDE,
        longitude: float = DEFAULT_LONGITUDE,
        location_name: str = LOCATION_NAME
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.location_name = location_name

    def fetch_weather_from_provider(self, timeout: int = 10) -> Dict[str, Any]:
        """
        Fetches current weather observations for Hyderabad from the Open-Meteo API.
        Open-Meteo is a free, non-commercial open data provider with no API key requirement.
        """
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={self.latitude}&longitude={self.longitude}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m,weather_code"
            f"&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
            f"&past_days=1&forecast_days=1&timezone=Asia%2FKolkata"
        )

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "URBANRISK-Weather-Integration/1.0 (Hyderabad Risk Analytics)"}
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"Open-Meteo API returned HTTP status {response.status}")
                raw_payload = response.read().decode("utf-8")
                data = json.loads(raw_payload)
                return data
        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to connect to Open-Meteo Weather API: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON received from Open-Meteo Weather API: {e}")

    def validate_and_parse_observation(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates API fields, physical ranges, and structures observation document."""
        current = raw_data.get("current")
        if not current or not isinstance(current, dict):
            raise ValueError("Missing 'current' weather block in API response")

        observation_time = current.get("time")
        if not observation_time or not isinstance(observation_time, str):
            raise ValueError("Missing or invalid 'time' in current weather block")

        # Temperature validation (-20°C to 60°C reasonable for Hyderabad)
        temp = current.get("temperature_2m")
        if temp is None or not isinstance(temp, (int, float)) or not (-20.0 <= temp <= 60.0):
            raise ValueError(f"Invalid or out-of-bounds temperature: {temp}")

        # Humidity validation (0 to 100%)
        humidity = current.get("relative_humidity_2m")
        if humidity is None or not isinstance(humidity, (int, float)) or not (0.0 <= humidity <= 100.0):
            raise ValueError(f"Invalid or out-of-bounds relative humidity: {humidity}")

        # Precipitation validation (>= 0 mm)
        precip = current.get("precipitation", 0.0)
        if precip is None or not isinstance(precip, (int, float)) or precip < 0.0:
            raise ValueError(f"Invalid precipitation measurement: {precip}")

        rain = current.get("rain", 0.0)
        if rain is None or not isinstance(rain, (int, float)) or rain < 0.0:
            rain = precip

        # Wind speed validation (>= 0 km/h)
        wind = current.get("wind_speed_10m", 0.0)
        if wind is None or not isinstance(wind, (int, float)) or wind < 0.0:
            raise ValueError(f"Invalid wind speed measurement: {wind}")

        weather_code = current.get("weather_code", 0)
        condition_str, icon = WMO_CODE_MAP.get(weather_code, ("Variable conditions", "🌤️"))

        # Open-Meteo returns interval in seconds (e.g. 900s = 15min)
        interval_sec = current.get("interval", 900)
        interval_min = round(interval_sec / 60) if interval_sec else 15

        now_utc = datetime.now(timezone.utc).isoformat()

        doc = {
            "location_name": self.location_name,
            "latitude": round(float(self.latitude), 4),
            "longitude": round(float(self.longitude), 4),
            "observation_time": observation_time,
            "retrieval_time": now_utc,
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "attribution": SOURCE_ATTRIBUTION,
            "data_type": "model_based_current_conditions",
            "data_source_type": "weather_model_estimate",
            "is_direct_station_measurement": False,
            "spatial_scale": SPATIAL_SCALE,
            "is_forecast": False,
            "temperature_c": round(float(temp), 1),
            "relative_humidity_pct": round(float(humidity), 1),
            "precipitation_mm": round(float(precip), 2),
            "rain_mm": round(float(rain), 2),
            "precipitation_accumulation_interval_seconds": interval_sec,
            "precipitation_accumulation_interval_minutes": interval_min,
            "precipitation_description": f"Preceding {interval_min}-minute interval accumulated precipitation (mm)",
            "wind_speed_kmh": round(float(wind), 1),
            "weather_code": int(weather_code),
            "weather_condition": condition_str,
            "weather_icon": icon,
            "units": {
                "temperature": "°C",
                "relative_humidity": "%",
                "precipitation": "mm",
                "rain": "mm",
                "wind_speed": "km/h",
                "interval": "seconds"
            },
            "disclaimer": (
                "Latest weather conditions provided by Open-Meteo weather models for the Hyderabad city-center coordinates. "
                "These are model-based estimates, not direct measurements from a local weather station. "
                f"Recent precipitation represents accumulation over the preceding {interval_min}-minute interval, "
                "not an instantaneous precipitation rate. "
                "Historical 1-km spatial risk grid scoring operates independently."
            )
        }
        return doc

    def store_observation(self, doc: Dict[str, Any], db=None) -> Dict[str, Any]:
        """
        Stores observation in MongoDB with duplicate-prevention via unique compound index.
        Returns storage action status (upserted, matched, or error).
        """
        active_db = db if db is not None else default_db
        if active_db is None:
            raise ConnectionError("MongoDB database connection is not available")

        col = active_db[COLLECTION_NAME]

        # Ensure unique index on location_name and observation_time
        col.create_index(
            [("location_name", pymongo.ASCENDING), ("observation_time", pymongo.ASCENDING)],
            unique=True
        )

        filter_query = {
            "location_name": doc["location_name"],
            "observation_time": doc["observation_time"]
        }

        # Exclude _id from $set payload if present
        set_payload = {k: v for k, v in doc.items() if k != "_id"}

        res = col.update_one(filter_query, {"$set": set_payload}, upsert=True)

        return {
            "status": "success",
            "upserted": bool(res.upserted_id is not None),
            "matched_count": res.matched_count,
            "modified_count": res.modified_count,
            "observation_time": doc["observation_time"],
            "total_stored_observations": col.count_documents({})
        }

    def fetch_and_store_weather(self, db=None) -> Dict[str, Any]:
        """Orchestrates fetch, validation, and storage pipeline."""
        raw_data = self.fetch_weather_from_provider()
        doc = self.validate_and_parse_observation(raw_data)
        storage_res = self.store_observation(doc, db=db)
        return {
            "status": "success",
            "observation": doc,
            "storage": storage_res
        }

    def get_latest_observation(self, db=None) -> Dict[str, Any]:
        """
        Retrieves the latest weather observation from MongoDB and evaluates data freshness.
        """
        active_db = db if db is not None else default_db
        if active_db is None:
            return {
                "status": "unavailable",
                "message": "Database connection unavailable",
                "data": None
            }

        col = active_db[COLLECTION_NAME]
        latest = col.find_one({}, sort=[("observation_time", pymongo.DESCENDING)])

        if not latest:
            return {
                "status": "unavailable",
                "freshness": "unavailable",
                "message": "No weather observations recorded yet. Run scripts/fetch_latest_weather.py to initialize.",
                "data": None
            }

        # Remove Mongo ObjectId for JSON serialization
        if "_id" in latest:
            latest["_id"] = str(latest["_id"])

        # Freshness evaluation
        freshness = "older_weather_data"
        freshness_label = "Older Weather Data"
        try:
            obs_dt = datetime.fromisoformat(latest["observation_time"])
            # If naive, assume IST (UTC+5:30)
            if obs_dt.tzinfo is None:
                ist_tz = timezone(timedelta(hours=5, minutes=30))
                obs_dt = obs_dt.replace(tzinfo=ist_tz)
            now_dt = datetime.now(obs_dt.tzinfo)
            diff_hours = (now_dt - obs_dt).total_seconds() / 3600.0
            if diff_hours <= 4.0:
                freshness = "recently_updated_model_data"
                freshness_label = "Recently Updated Model Data"
            else:
                freshness = "older_weather_data"
                freshness_label = "Older Weather Data"
        except Exception:
            freshness = "unknown"
            freshness_label = "Weather Data"

        return {
            "status": "success",
            "freshness": freshness,
            "freshness_label": freshness_label,
            "data_source_type": "weather_model_estimate",
            "is_direct_station_measurement": False,
            "data": latest,
            "source": latest.get("source", SOURCE_NAME),
            "attribution": latest.get("attribution", SOURCE_ATTRIBUTION),
            "spatial_scale": latest.get("spatial_scale", SPATIAL_SCALE),
            "disclaimer": latest.get("disclaimer")
        }

    def get_weather_history(self, limit: int = 24, db=None) -> Dict[str, Any]:
        """Retrieves recent weather observations sorted by time descending."""
        active_db = db if db is not None else default_db
        if active_db is None:
            return {"status": "unavailable", "observations": [], "total_records": 0}

        col = active_db[COLLECTION_NAME]
        cursor = col.find({}, sort=[("observation_time", pymongo.DESCENDING)]).limit(limit)

        records = []
        for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            records.append(doc)

        return {
            "status": "success",
            "total_records": col.count_documents({}),
            "returned_records": len(records),
            "observations": records
        }

    def get_weather_summary(self, db=None) -> Dict[str, Any]:
        """Aggregates observation count, extremes, and provider freshness."""
        active_db = db if db is not None else default_db
        if active_db is None:
            return {"status": "unavailable", "summary": None}

        col = active_db[COLLECTION_NAME]
        total = col.count_documents({})
        if total == 0:
            return {
                "status": "unavailable",
                "message": "No weather observations recorded",
                "summary": None,
                "grid_integration_assessment": self.get_grid_integration_assessment()
            }

        latest = col.find_one({}, sort=[("observation_time", pymongo.DESCENDING)])
        earliest = col.find_one({}, sort=[("observation_time", pymongo.ASCENDING)])

        # Sample recent observations for 24-hr metrics
        recent_cursor = col.find({}, sort=[("observation_time", pymongo.DESCENDING)]).limit(24)
        temps = []
        precips = []
        for r in recent_cursor:
            if r.get("temperature_c") is not None:
                temps.append(float(r["temperature_c"]))
            if r.get("precipitation_mm") is not None:
                precips.append(float(r["precipitation_mm"]))

        summary = {
            "total_observations_recorded": total,
            "latest_observation_time": latest.get("observation_time") if latest else None,
            "earliest_observation_time": earliest.get("observation_time") if earliest else None,
            "current_temperature_c": latest.get("temperature_c") if latest else None,
            "current_weather_condition": latest.get("weather_condition") if latest else None,
            "recent_24h_min_temp_c": min(temps) if temps else None,
            "recent_24h_max_temp_c": max(temps) if temps else None,
            "recent_cumulative_precip_mm": round(sum(precips), 2) if precips else 0.0,
            "provider": SOURCE_NAME,
            "attribution": SOURCE_ATTRIBUTION
        }

        return {
            "status": "success",
            "summary": summary,
            "grid_integration_assessment": self.get_grid_integration_assessment()
        }

    @staticmethod
    def get_grid_integration_assessment() -> Dict[str, Any]:
        """
        Rigorous assessment on spatial grid integration feasibility.
        Documented rule: A single city-center weather station cannot be applied
        across 791 individual 1-km cells as local runoff or inundation measurements.
        """
        return {
            "spatial_scale": "city_level_aggregate",
            "spatial_coverage": "Point coordinate (17.3850°N, 78.4867°E)",
            "grid_assignment_allowed": False,
            "decision_rationale": (
                "Open-Meteo observations provide accurate citywide ambient weather conditions "
                "for Hyderabad. However, convective precipitation varies sharply across the "
                "791 km² study boundary. Replicating a single weather point across all 791 1-km cells "
                "would fabricate false spatial variance and falsely distort localized catchment flood evidence. "
                "Therefore, weather observations are maintained strictly as city-level environmental context, "
                "leaving the approved 1-km IUPS multi-hazard scoring formula and historical CHIRPS baselines uncorrupted."
            ),
            "iups_weights_affected": False,
            "ml_models_affected": False
        }
