"""
scripts/test_phase1_transparency.py
Verification test suite for Phase 1 Data Transparency, Temporal Awareness, and Risk Consistency.
"""

import math
import json
import urllib.request
try:
    import pytest
except ImportError:
    pytest = None
from pymongo import MongoClient

BASE_URL = "http://127.0.0.1:8000"

def http_get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def http_post(path, payload):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_database_metadata_exactness():
    """Verify all 6 documents in dataset_versions for exact temporal and provenance metadata."""
    client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
    col = client["urban_risk_db"]["dataset_versions"]
    assert col.count_documents({}) == 6

    # 1. MODIS Heat
    rec1 = col.find_one({"_id": 1, "dataset_id": 1})
    assert rec1 is not None
    assert rec1["dataset_name"] == "Hyderabad MODIS Heat"
    assert rec1["source_name"] == "MODIS 2018"
    assert rec1["source_product"] == "MODIS Satellite Land Surface Temperature 1-km Baseline"
    assert rec1["observation_period"] == {"start_date": "2018-01-01", "end_date": "2018-12-31"}
    assert rec1["source_publication_date"] is None
    assert rec1["is_real_time"] is False
    assert rec1["is_forecast"] is False

    # 9. Yale Heat
    rec9 = col.find_one({"_id": 9, "dataset_id": 9})
    assert rec9 is not None
    assert rec9["dataset_name"] == "Hyderabad Yale Urban Heat"
    assert rec9["source_name"] == "Yale Urban Heat Dataset"
    assert rec9["source_product"] == "Surface Urban Heat Island (UHI) Multi-Year Baseline"
    assert rec9["observation_period"] == {"start_year": 2003, "end_year": 2018}
    assert rec9["source_publication_date"] is None
    assert rec9["is_real_time"] is False
    assert rec9["is_forecast"] is False

    # 10. Rainfall (Protected source_name verified verbatim)
    rec10 = col.find_one({"_id": 10, "dataset_id": 10})
    assert rec10 is not None
    assert rec10["dataset_name"] == "Hyderabad Rainfall"
    assert rec10["source_name"] == "Rainfall processed source"
    assert rec10["source_product"] == "CHIRPS v3.0 Daily COG Raster Extraction"
    assert rec10["observation_period"] == {"storm_dates": ["2020-09-25", "2021-10-08"]}
    assert rec10["raster_samples_count"] == 84
    assert rec10["distinct_storm_dates_count"] == 2
    assert rec10["source_publication_date"] is None
    assert rec10["is_real_time"] is False
    assert rec10["is_forecast"] is False

    # 11. Infrastructure Points
    rec11 = col.find_one({"_id": 11, "dataset_id": 11})
    assert rec11 is not None
    assert rec11["source_product"] == "OpenStreetMap Civic Amenities Spatial Snapshot"
    assert rec11["observation_period"]["snapshot_date"] is None
    assert rec11["source_publication_date"] is None
    assert rec11["is_real_time"] is False

    # 12. Road Network
    rec12 = col.find_one({"_id": 12, "dataset_id": 12})
    assert rec12 is not None
    assert rec12["source_product"] == "OpenStreetMap Road Network Spatial Snapshot"
    assert rec12["observation_period"]["snapshot_date"] is None
    assert rec12["source_publication_date"] is None
    assert rec12["is_real_time"] is False

    # 13. Historical Flood Events
    rec13 = col.find_one({"_id": 13, "dataset_id": 13})
    assert rec13 is not None
    assert rec13["source_product"] == "National Flood Inventory (Hyderabad District Archive)"
    assert rec13["observation_period"] == {"start_year": 1969, "end_year": 2022}
    assert rec13["source_publication_date"] is None
    assert rec13["is_real_time"] is False


def test_assessment_endpoint_temporal_and_ml_disambiguation():
    """Verify POST /api/assessments/evaluate for coordinate (17.3850, 78.4867)."""
    status, data = http_post("/api/assessments/evaluate", {
        "latitude": 17.3850,
        "longitude": 78.4867,
        "radius_m": 1000
    })
    assert status == 200

    cats = data["category_assessments"]
    heat = cats["heat_risk"]
    assert heat["score_value"] == 81.2
    assert heat["classification"] == "HIGH"
    assert heat["score_scale"] == "0-100"

    ml_est = heat["ml_estimate"]
    assert ml_est is not None
    assert ml_est["estimate_type"] == "ILLUSTRATIVE_REGRESSION_ESTIMATE"
    assert ml_est["input_assumed_nighttime_temp_c"] == 24.5
    assert ml_est["input_nature"] == "Assumed nominal nighttime temperature baseline of 24.5°C; not a measured temperature."
    assert ml_est["is_forecast"] is False
    assert math.isclose(ml_est["predicted_daytime_temp_c"], 34.1, abs_tol=0.2)
    assert math.isclose(ml_est["diurnal_temperature_difference_c"], 9.6, abs_tol=0.2)
    assert ml_est["heat_risk_level"] == "High"

    flood = cats["flood_risk"]
    assert flood["score_value"] is None
    assert flood["classification"] == "REGIONAL CONTEXT ONLY"
    assert flood["storm_dates"] == ["2020-09-25", "2021-10-08"]
    assert flood["raster_samples_count"] == 84
    assert "CHIRPS raster extraction" in flood["rainfall_coverage_note"]
    assert "India Flood Inventory v3 (IMD Disasters Archive)" in flood["source"]

    # Verify IUPS composite priority
    iups = data["integrated_priority_assessment"]
    assert iups["grid"]["grid_id"] == "26_13"
    assert math.isclose(iups["priority_score"], 64.141, abs_tol=0.01)
    assert iups["priority_band"] == "Higher screening priority"


def test_assessment_endpoint_flood_evidence_present():
    """Verify an assessment where flood evidence exists (e.g. cell 14_12 at 17.3730, 78.3752)."""
    status, data = http_post("/api/assessments/evaluate", {
        "latitude": 17.3730,
        "longitude": 78.3752,
        "radius_m": 1000
    })
    assert status == 200
    flood = data["category_assessments"]["flood_risk"]
    assert flood["score_value"] == 88.5
    assert flood["classification"] == "HIGH"
    assert "India Flood Inventory v3 (IMD Disasters Archive)" in flood["source"]


def test_ml_predict_endpoint_user_input():
    """Verify POST /api/ml/predict with user-supplied nighttime temperature (26.0°C)."""
    status, data = http_post("/api/ml/predict", {
        "latitude": 17.3850,
        "longitude": 78.4867,
        "nighttime_temp_c": 26.0
    })
    assert status == 200
    assert data["status"] == "success"
    assert data["estimate_type"] == "REGRESSION_INFERENCE"
    assert data["input_nature"] == "User-supplied input parameter"
    assert data["is_forecast"] is False
    assert data["is_real_time"] is False
    assert data["baseline_satellite_training_year"] == 2018

    pred = data["prediction"]
    assert math.isclose(pred["predicted_daytime_temp_c"], 35.2, abs_tol=0.2)
    assert math.isclose(pred["diurnal_temperature_difference_c"], 9.2, abs_tol=0.2)
    assert pred["heat_risk_level"] == "High"


def test_flood_summary_endpoint():
    """Verify GET /api/flood/summary additive temporal attributes and accurate terminology."""
    status, data = http_get("/api/flood/summary")
    assert status == 200
    assert data["status"] == "operational"
    assert data["storm_events"] == ["2020-09-25", "2021-10-08"]
    assert data["raster_samples_count"] == 84
    assert data["is_real_time"] is False
    assert data["is_forecast"] is False
    assert "CHIRPS v3.0" in data["rainfall_data_nature"]


def test_heat_summary_endpoint():
    """Verify GET /api/heat/summary additive temporal badges."""
    status, data = http_get("/api/heat/summary")
    assert status == 200
    assert data["status"] == "operational"
    assert data["modis_observation_year"] == 2018
    assert data["yale_observation_period"] == "2003–2018"
    assert data["is_real_time"] is False
    assert data["is_forecast"] is False


def test_infrastructure_summary_endpoint():
    """Verify GET /api/infrastructure/summary snapshot notice."""
    status, data = http_get("/api/infrastructure/summary")
    assert status == 200
    assert data["status"] == "operational"
    assert "unrecorded" in data["data_source_nature"]
    assert data["is_real_time"] is False


def test_unscored_cells_preservation():
    """Verify that 50 peripheral grid cells retain unscored status."""
    import pandas as pd
    from pathlib import Path
    grid_csv = Path(__file__).resolve().parents[1] / "data" / "processed" / "integrated_urban_risk" / "integrated_urban_risk_priority_grid_1km.csv"
    df = pd.read_csv(grid_csv)
    unscored = df[df["priority_score_0_100"].isna()]
    assert len(unscored) == 50, f"Expected 50 unscored cells, found {len(unscored)}"
    assert (unscored["hazard_component_count"] == 0).all()
    assert (unscored["screening_priority"] == "Not scored").all() or (unscored["screening_priority"].isna()).all()


def test_frontend_tooltip_and_labels():
    """Verify frontend HTML and JS contain approved tooltip and placeholder text."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    index_html = (root / "frontend" / "html" / "index.html").read_text(encoding="utf-8")
    script_js = (root / "frontend" / "js" / "script.js").read_text(encoding="utf-8")

    # Static HTML placeholder verification
    assert 'id="homePriorityBadge">EVALUATING...<' in index_html
    assert 'id="homeFloodBadge">EVALUATING...<' in index_html
    assert 'id="homeHeatBadge">EVALUATING...<' in index_html
    assert 'id="homeInfraBadge">EVALUATING...<' in index_html

    # Rainfall label
    assert "84 Raster Samples · 2 Historical Storm Dates" in index_html

    # Approved unscored tooltip
    expected_tooltip = "This grid cell has insufficient flood or satellite thermal hazard evidence to calculate a priority score. Lack of available evidence does not indicate low vulnerability."
    assert expected_tooltip in script_js


if __name__ == "__main__":
    print("Running Phase 1 Verification Tests...")
    test_database_metadata_exactness()
    print(" - [PASS] Database Metadata Exactness")
    test_assessment_endpoint_temporal_and_ml_disambiguation()
    print(" - [PASS] Assessment Endpoint Temporal & ML Disambiguation (Null Flood Score)")
    test_assessment_endpoint_flood_evidence_present()
    print(" - [PASS] Assessment Endpoint Flood Evidence Present (Valid Score & High Class)")
    test_ml_predict_endpoint_user_input()
    print(" - [PASS] ML Predict User Input")
    test_flood_summary_endpoint()
    print(" - [PASS] Flood Summary Endpoint")
    test_heat_summary_endpoint()
    print(" - [PASS] Heat Summary Endpoint")
    test_infrastructure_summary_endpoint()
    print(" - [PASS] Infrastructure Summary Endpoint")
    test_unscored_cells_preservation()
    print(" - [PASS] Unscored Cells Preservation")
    test_frontend_tooltip_and_labels()
    print(" - [PASS] Frontend Tooltip & Placeholders")
    print("\nALL PHASE 1 TRANSPARENCY TESTS PASSED SUCCESSFULLY!")
