"""
Test Suite: Phase 3 Latest Weather Data Integration Verification
Tests API connectivity, response validation, MongoDB persistence, duplicate prevention,
temporal metadata, endpoint behavior, and spatial grid non-interference invariants.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error
import pymongo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.weather_service import WeatherService, WMO_CODE_MAP


def test_weather_service_validation_and_parsing():
    print("Testing WeatherService validation and response parsing...")
    service = WeatherService()

    # Test with valid mock data
    mock_raw = {
        "current": {
            "time": "2026-11-24T15:00",
            "temperature_2m": 30.5,
            "relative_humidity_2m": 42.0,
            "precipitation": 0.0,
            "rain": 0.0,
            "wind_speed_10m": 8.5,
            "weather_code": 2
        }
    }

    doc = service.validate_and_parse_observation(mock_raw)
    assert doc["temperature_c"] == 30.5
    assert doc["relative_humidity_pct"] == 42.0
    assert doc["precipitation_mm"] == 0.0
    assert doc["weather_condition"] == "Partly cloudy"
    assert doc["weather_icon"] == "⛅"
    assert doc["spatial_scale"] == "city_level_aggregate"
    assert doc["is_forecast"] is False
    assert doc["data_type"] == "model_based_current_conditions"
    assert doc["data_source_type"] == "weather_model_estimate"
    assert doc["is_direct_station_measurement"] is False
    assert doc["precipitation_accumulation_interval_minutes"] == 15
    assert "model-based estimates, not direct measurements from a local weather station" in doc["disclaimer"]
    assert "not an instantaneous precipitation rate" in doc["disclaimer"]

    # Test error handling on missing current block
    try:
        service.validate_and_parse_observation({})
        assert False, "Should have failed on missing 'current' block"
    except ValueError:
        pass

    # Test error handling on out-of-bounds temperature
    try:
        bad_temp = {"current": {"time": "2026-11-24T15:00", "temperature_2m": 120.0, "relative_humidity_2m": 50}}
        service.validate_and_parse_observation(bad_temp)
        assert False, "Should have failed on out-of-bounds temperature"
    except ValueError:
        pass

    print("  [PASS] Validation and parsing verified.")


def test_mongodb_persistence_and_duplicate_prevention():
    print("Testing MongoDB persistence and duplicate prevention in weather_observations...")
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)
    db = client["urban_risk_db"]
    col = db["weather_observations"]

    service = WeatherService()

    # Initial state count
    initial_count = col.count_documents({})

    test_time = "2026-11-24T12:00"
    test_doc = {
        "location_name": service.location_name,
        "latitude": service.latitude,
        "longitude": service.longitude,
        "observation_time": test_time,
        "retrieval_time": datetime.now(timezone.utc).isoformat(),
        "source": "Open-Meteo Weather API",
        "attribution": "Weather data by Open-Meteo.com under CC BY 4.0",
        "data_type": "model_based_current_conditions",
        "data_source_type": "weather_model_estimate",
        "is_direct_station_measurement": False,
        "spatial_scale": "city_level_aggregate",
        "is_forecast": False,
        "temperature_c": 29.8,
        "relative_humidity_pct": 45.0,
        "precipitation_mm": 0.0,
        "rain_mm": 0.0,
        "wind_speed_kmh": 6.2,
        "weather_code": 1,
        "weather_condition": "Mainly clear",
        "weather_icon": "🌤️",
        "units": {"temperature": "°C", "relative_humidity": "%", "precipitation": "mm", "wind_speed": "km/h"}
    }

    # First write -> upsert
    res1 = service.store_observation(test_doc, db=db)
    assert col.count_documents({}) == initial_count + (1 if res1["upserted"] else 0)

    # Second write for same observation_time -> update existing, NO duplicate
    res2 = service.store_observation(test_doc, db=db)
    assert res2["upserted"] is False, "Repeated write should match, not insert new"
    assert res2["matched_count"] == 1, "Should have matched existing record"

    # Verify unique index exists
    indexes = col.index_information()
    has_unique = any(
        idx.get("unique") is True and ("location_name", 1) in idx.get("key", [])
        for idx in indexes.values()
    )
    assert has_unique, "Missing unique compound index on weather_observations"

    print("  [PASS] MongoDB persistence and duplicate prevention verified.")


def test_historical_dataset_preservation():
    print("Testing non-interference with historical flood and priority grid datasets...")
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)
    db = client["urban_risk_db"]

    # Verify flood_events intact
    flood_count = db.flood_events.count_documents({})
    assert flood_count == 40, f"Expected exactly 40 flood_events, found {flood_count}"

    # Verify hazard_observations intact
    hazard_count = db.hazard_observations.count_documents({})
    assert hazard_count == 14614, f"Expected 14614 hazard_observations, found {hazard_count}"

    # Verify priority_grid_cells intact
    grid_count = db.priority_grid_cells.count_documents({})
    assert grid_count == 791, f"Expected 791 priority_grid_cells, found {grid_count}"

    print("  [PASS] Historical datasets strictly preserved without modification.")


def test_spatial_grid_integration_boundary():
    print("Testing spatial grid integration boundary assessment...")
    assessment = WeatherService.get_grid_integration_assessment()
    assert assessment["grid_assignment_allowed"] is False
    assert assessment["spatial_scale"] == "city_level_aggregate"
    assert assessment["iups_weights_affected"] is False
    assert assessment["ml_models_affected"] is False
    print("  [PASS] Spatial grid integration boundary explicitly confirmed.")


def test_weather_api_endpoints():
    print("Testing weather API endpoints on http://127.0.0.1:8000 ...")
    base_url = "http://127.0.0.1:8000"

    # Test /api/weather/current
    req = urllib.request.Request(f"{base_url}/api/weather/current")
    with urllib.request.urlopen(req, timeout=5) as res:
        assert res.status == 200, f"Expected 200, got {res.status}"
        data = json.loads(res.read().decode())
        assert data.get("status") == "success"
        assert data.get("freshness") in ["recently_updated_model_data", "older_weather_data", "fresh", "stale"]
        assert data.get("data_source_type") == "weather_model_estimate"
        assert data.get("is_direct_station_measurement") is False
        assert "model-based estimates, not direct measurements from a local weather station" in data.get("disclaimer", "")
        assert "data" in data and data["data"] is not None
        obs = data["data"]
        assert "temperature_c" in obs
        assert "relative_humidity_pct" in obs
        assert "observation_time" in obs
        assert obs.get("data_type") == "model_based_current_conditions"
        assert data.get("spatial_scale") == "city_level_aggregate"
        assert "Open-Meteo" in data.get("source", "")
        print(f"    - Current weather: {obs['temperature_c']}°C, {obs['relative_humidity_pct']}%, condition: {obs['weather_condition']}")

    # Test /api/weather/history
    req_hist = urllib.request.Request(f"{base_url}/api/weather/history?limit=5")
    with urllib.request.urlopen(req_hist, timeout=5) as res_hist:
        assert res_hist.status == 200
        hist_data = json.loads(res_hist.read().decode())
        assert hist_data.get("status") == "success"
        assert len(hist_data.get("observations", [])) >= 1

    # Test /api/weather/summary
    req_sum = urllib.request.Request(f"{base_url}/api/weather/summary")
    with urllib.request.urlopen(req_sum, timeout=5) as res_sum:
        assert res_sum.status == 200
        sum_data = json.loads(res_sum.read().decode())
        assert sum_data.get("status") == "success"
        assert "summary" in sum_data
        assert "grid_integration_assessment" in sum_data
        assert sum_data["grid_integration_assessment"]["grid_assignment_allowed"] is False

    print("  [PASS] All weather endpoints verified.")


if __name__ == "__main__":
    test_weather_service_validation_and_parsing()
    test_mongodb_persistence_and_duplicate_prevention()
    test_historical_dataset_preservation()
    test_spatial_grid_integration_boundary()
    test_weather_api_endpoints()
    print("\nALL PHASE 3 WEATHER INTEGRATION TESTS PASSED SUCCESSFULLY!")
