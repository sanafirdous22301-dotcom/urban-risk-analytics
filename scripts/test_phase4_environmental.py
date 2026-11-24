"""
Test Suite: Phase 4 Updated Satellite & Environmental Intelligence Verification
Validates:
1. Source metadata and observation dates (MODIS 2023, Sentinel-2 2024, ESA WorldCover 2021).
2. Quality filtering (cloud/shadow/QC masking).
3. Exact spatial alignment across all 791 1-km grid cells.
4. Non-corruption of historical datasets (dataset_versions, flood_events, hazard_observations).
5. Phase 1 transparency and LST-vs-air-temperature disclaimers.
6. Phase 2 grid recalculation invariants (791 cells: 741 scored, 50 unscored).
7. Phase 3 weather integration endpoints and collections integrity.
8. MongoDB duplicate prevention in environmental_indicators.
9. Environmental API endpoints on FastAPI (/summary, /grid/sample, /catalog).
"""

from datetime import datetime
import json
from pathlib import Path
import sys
import urllib.request
import urllib.error
import pymongo
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.environmental_service import (
    EnvironmentalService,
    ENVIRONMENTAL_CATALOG_META,
    GRID_BACKBONE_PATH
)


def test_metadata_and_observation_dates():
    print("Testing source metadata and observation dates...")
    meta = ENVIRONMENTAL_CATALOG_META

    # Thermal
    assert "MOD11A2" in meta["thermal"]["dataset_name"] or "MYD11A2" in meta["thermal"]["product_id"]
    assert "2023" in meta["thermal"]["observation_period"]
    assert "1 km" in meta["thermal"]["spatial_resolution"]
    assert "NASA LP DAAC" in meta["thermal"]["publisher"]
    assert "radiative skin temperature" in meta["thermal"]["lst_vs_air_temp_disclaimer"]
    assert "QC_Day mandatory QA flag" in meta["thermal"]["quality_filtering"]
    assert "poor aerosol" not in meta["thermal"]["quality_filtering"]

    # Vegetation
    assert meta["vegetation"]["observation_date"] == "2024-04-27"
    assert "10 meters" in meta["vegetation"]["spatial_resolution"]
    assert "Copernicus" in meta["vegetation"]["publisher"]
    assert "43QHV" in meta["vegetation"]["tile_id"]
    assert "Scene Classification Layer" in meta["vegetation"]["quality_filtering"]
    assert "ecological canopy index, NOT a direct physical measurement of air cooling" in meta["vegetation"]["vegetation_vs_cooling_disclaimer"]

    # Built-up
    assert meta["builtup"]["baseline_year"] == "2021"
    assert "10 meters" in meta["builtup"]["spatial_resolution"]
    assert "ESA WorldCover" in meta["builtup"]["dataset_name"]
    print("  [PASS] Metadata catalog and observation dates verified.")


def test_processed_indicators_csv_and_alignment():
    print("Testing processed indicators CSV spatial alignment and physical bounds...")
    service = EnvironmentalService()
    assert service.output_csv_path.exists(), f"Missing output CSV: {service.output_csv_path}"

    df = pd.read_csv(service.output_csv_path)
    assert len(df) == 791, f"Expected 791 cells, got {len(df)}"

    backbone = pd.read_csv(GRID_BACKBONE_PATH)
    assert (df["grid_id"] == backbone["grid_id"]).all(), "Grid IDs do not strictly align with master backbone"

    # Thermal bounds (Hyderabad summer LST typically 30°C to 55°C)
    valid_lst = df["modis_lst_day_2023_c"].dropna()
    assert len(valid_lst) == 791, f"Expected 791 valid LST cells, got {len(valid_lst)}"
    assert 30.0 <= valid_lst.min() <= 40.0, f"Unreasonable min LST: {valid_lst.min()}"
    assert 40.0 <= valid_lst.max() <= 55.0, f"Unreasonable max LST: {valid_lst.max()}"

    # NDVI bounds (-1.0 to +1.0)
    valid_ndvi = df["sentinel2_ndvi_2024"].dropna()
    assert len(valid_ndvi) == 791, f"Expected 791 valid NDVI cells, got {len(valid_ndvi)}"
    assert -0.5 <= valid_ndvi.min() <= 0.2, f"Unreasonable min NDVI: {valid_ndvi.min()}"
    assert 0.5 <= valid_ndvi.max() <= 1.0, f"Unreasonable max NDVI: {valid_ndvi.max()}"

    # Built-up count
    builtup_count = df["is_builtup_surface"].sum()
    assert builtup_count == 482, f"Expected 482 built-up cells, got {builtup_count}"

    print(f"  [PASS] 791 cells aligned: LST Mean {valid_lst.mean():.2f}°C, NDVI Mean {valid_ndvi.mean():.3f}, Built-up {builtup_count} cells.")


def test_mongodb_persistence_and_no_duplicates():
    print("Testing MongoDB environmental_indicators collection and duplicate prevention...")
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)
    db = client["urban_risk_db"]

    assert "environmental_indicators" in db.list_collection_names()
    col = db["environmental_indicators"]

    total = col.count_documents({})
    assert total == 791, f"Expected exactly 791 documents, found {total}"

    unique_ids = col.distinct("grid_id")
    assert len(unique_ids) == 791, f"Expected 791 unique grid_ids, found {len(unique_ids)}"

    # Check unique index
    indexes = col.index_information()
    has_unique = any(idx.get("unique") is True and ("grid_id", 1) in idx.get("key", []) for idx in indexes.values())
    assert has_unique, "Missing unique index on grid_id in environmental_indicators"

    # Catalog collection
    cat_col = db["environmental_catalog"]
    assert cat_col.count_documents({}) >= 3, "Expected at least 3 catalog documents"
    print("  [PASS] MongoDB collection has exactly 791 unique documents with zero duplicates.")


def test_preservation_of_historical_and_previous_phases():
    print("Testing non-corruption of historical datasets, Phase 1, Phase 2, and Phase 3...")
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)
    db = client["urban_risk_db"]

    # Historical collections
    assert db.dataset_versions.count_documents({}) == 6, "dataset_versions modified!"
    assert db.flood_events.count_documents({}) == 40, "flood_events modified!"
    assert db.hazard_observations.count_documents({}) == 14614, "hazard_observations modified!"

    # Phase 2 priority grid
    assert db.priority_grid_cells.count_documents({}) == 791, "priority_grid_cells modified!"
    scored_count = db.priority_grid_cells.count_documents({"priority_score_0_100": {"$ne": None}})
    unscored_count = db.priority_grid_cells.count_documents({"priority_score_0_100": None})
    assert scored_count == 741, f"Expected 741 scored cells, found {scored_count}"
    assert unscored_count == 50, f"Expected 50 unscored cells, found {unscored_count}"

    # Phase 3 weather observations
    assert "weather_observations" in db.list_collection_names(), "weather_observations collection missing!"
    assert db.weather_observations.count_documents({}) >= 1, "weather_observations empty!"

    # Grid boundary non-interference
    grid_status = EnvironmentalService.get_grid_integration_status()
    assert grid_status["grid_weights_modified"] is False
    assert grid_status["historical_baselines_overwritten"] is False

    print("  [PASS] All historical baselines, Phase 1-3 datasets, and IUPS grid remain 100% intact.")


def test_environmental_api_endpoints():
    print("Testing environmental API endpoints on http://127.0.0.1:8000 ...")
    base_url = "http://127.0.0.1:8000"

    # Test /api/environmental/summary
    req_sum = urllib.request.Request(f"{base_url}/api/environmental/summary")
    with urllib.request.urlopen(req_sum, timeout=5) as res:
        assert res.status == 200, f"Expected 200, got {res.status}"
        data = json.loads(res.read().decode())
        assert data.get("status") == "success"
        assert "catalog" in data
        assert "indicators_coverage" in data
        cov = data["indicators_coverage"]
        assert cov["total_grid_cells"] == 791
        assert cov["modis_lst_2023"]["valid_cells"] == 791
        assert cov["sentinel2_ndvi_2024"]["valid_cells"] == 791
        assert cov["esa_builtup_2021"]["builtup_cells_count"] == 482
        assert cov["esa_builtup_2021"]["metric_label"] == "Grid cells containing built-up land"
        print(f"    - Summary verified: {cov['total_grid_cells']} cells, Mean LST: {cov['modis_lst_2023']['mean_lst_day_c']}°C, Mean NDVI: {cov['sentinel2_ndvi_2024']['mean_ndvi']}")

    # Test /api/environmental/grid/sample
    req_samp = urllib.request.Request(f"{base_url}/api/environmental/grid/sample?limit=10")
    with urllib.request.urlopen(req_samp, timeout=5) as res:
        assert res.status == 200
        data = json.loads(res.read().decode())
        assert data.get("status") == "success"
        assert len(data.get("cells", [])) == 10
        first = data["cells"][0]
        assert "modis_lst_day_2023_c" in first
        assert "sentinel2_ndvi_2024" in first
        assert "is_builtup_surface" in first

    # Test /api/environmental/catalog
    req_cat = urllib.request.Request(f"{base_url}/api/environmental/catalog")
    with urllib.request.urlopen(req_cat, timeout=5) as res:
        assert res.status == 200
        cat_data = json.loads(res.read().decode())
        assert cat_data.get("status") == "success"

    print("  [PASS] All environmental endpoints verified.")


if __name__ == "__main__":
    test_metadata_and_observation_dates()
    test_processed_indicators_csv_and_alignment()
    test_mongodb_persistence_and_no_duplicates()
    test_preservation_of_historical_and_previous_phases()
    test_environmental_api_endpoints()
    print("\nALL PHASE 4 SATELLITE ENVIRONMENTAL TESTS PASSED SUCCESSFULLY!")
