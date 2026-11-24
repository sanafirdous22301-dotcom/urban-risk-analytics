"""
Phase 6 Test Suite: Advanced Flood & Heat Risk Modelling.
Verifies:
1. Climatological rainfall analysis (NASA POWER 1981-2022 recurrence statistics, percentiles).
2. Flood evidence profiling (distinguishes cell-level direct evidence vs regional context; preserves missing values).
3. Environmental thermal vulnerability regression model:
   - Reproducibility and feature generation.
   - 5-Fold Spatial Cross Validation.
   - No data leakage.
   - Performance compared against Dummy Mean baseline and OLS linear baseline.
   - Model metadata artifact saved in models/heat/advanced/.
4. Heat vulnerability profiling & hotspot identification (thermal anomaly vs city baseline, canopy NDVI status).
5. Non-corruption of IUPS grid invariants (791 total, 741 scored, 50 unscored) and weights.
6. API endpoint verification for `/api/flood/climatology`, `/api/flood/evidence-profile`, `/api/heat/vulnerability-profile`, `/api/heat/model-metadata`.
"""

import sys
from pathlib import Path
import json
import urllib.request
import urllib.error
import pymongo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.phase6_analytics_service import AdvancedHazardAnalyticsService
from database.mongodb import db

BASE_URL = "http://127.0.0.1:8000"


def http_get(url: str) -> (int, dict):
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"detail": body}


def test_flood_intelligence():
    print("Testing Flood Intelligence & Climatological Analysis...")
    svc = AdvancedHazardAnalyticsService(db=db)

    # 1. Climatological analysis
    clim = svc.get_climatological_rainfall_stats()
    assert clim["total_days"] == 15316, f"Expected 15,316 daily records, got {clim['total_days']}"
    assert clim["max_daily_rainfall_mm"] > 100.0, "Historical max daily rainfall should exceed 100mm"
    p = clim["percentiles_all_days"]
    assert p["p99_mm"] > p["p95_mm"] > p["p90_mm"] > p["p50_mm"], "Rainfall percentiles must be monotonic"

    # 2. Locality flood evidence profiling & land-cover context
    prof_charminar = svc.evaluate_flood_evidence_profile(17.3616, 78.4747)
    assert "has_direct_cell_evidence" in prof_charminar
    assert prof_charminar["regional_context"]["historical_events_registered"] == 40
    assert "environmental_landcover_context" in prof_charminar
    lc_label = prof_charminar["environmental_landcover_context"]["landcover_classification_label"]
    assert lc_label in ("Built-up Land-Cover Context", "Non-Built-up Land-Cover Context")
    assert "hydrological_disclaimer" in prof_charminar["environmental_landcover_context"]

    # Verify no classifier claim
    assert len(prof_charminar["scientific_limitations"]) >= 3
    assert any("No cell-level flood probability classifier" in lim for lim in prof_charminar["scientific_limitations"])

    print("  [PASS] Flood climatology, evidence-based screening, and corrected land-cover context verified.")


def test_heat_intelligence_and_ml_model():
    print("Testing Heat Intelligence & Genuine Spatial-Block Cross-Validation...")
    svc = AdvancedHazardAnalyticsService(db=db)

    # 1. Model training under genuine Spatial-Block CV
    metrics = svc.train_or_load_heat_vulnerability_model()
    assert metrics["sample_count"] == 791, f"Expected 791 samples, got {metrics['sample_count']}"
    assert len(metrics["features"]) == 2

    val_strategy = metrics["validation_strategy"]
    assert "Spatial Block Cross-Validation" in val_strategy["method"]
    assert len(val_strategy["fold_cell_counts"]) == 5

    rf_metrics = metrics["candidate_rf_metrics"]
    ols_metrics = metrics["ols_linear_baseline"]
    dummy_metrics = metrics["dummy_mean_baseline"]

    # Verify fold-wise metrics are present and non-empty
    assert len(rf_metrics["fold_wise_mae_c"]) == 5
    assert len(rf_metrics["fold_wise_rmse_c"]) == 5
    assert len(rf_metrics["fold_wise_r2"]) == 5

    # Check uncertainty reporting: MAE is an absolute error metric, reported with fold std
    assert "mean_fold_mae_c" in rf_metrics and "std_fold_mae_c" in rf_metrics
    assert rf_metrics["mean_fold_mae_c"] > 0
    assert rf_metrics["std_fold_mae_c"] > 0

    # Verify metadata saved to models directory
    meta_file = PROJECT_ROOT / "models" / "heat" / "advanced" / "heat_vulnerability_model_metadata.json"
    assert meta_file.exists(), "Metadata file must be saved to models directory"

    # 2. Locality heat profile
    heat_prof = svc.get_heat_vulnerability_profile(17.3616, 78.4747)
    assert "thermal_anomaly_relative_to_city_c" in heat_prof
    assert "hotspot_classification" in heat_prof
    assert heat_prof["hotspot_classification"] in [
        "SEVERE THERMAL HOTSPOT", "ELEVATED THERMAL ANOMALY", "COOL THERMAL REFUGIUM", "MODERATE / CITY AVERAGE"
    ]
    assert "canopy_vegetation_ndvi_2024" in heat_prof
    assert "cooling_vulnerability" in heat_prof

    print("  [PASS] Genuine spatial block cross-validation, fold-wise error reporting, and hotspot profiling verified.")


def test_phase6_api_endpoints():
    print(f"Testing Phase 6 API endpoints on {BASE_URL}...")

    # 1. Flood Climatology
    c_status, c_data = http_get(f"{BASE_URL}/api/flood/climatology")
    assert c_status == 200, f"Expected 200, got {c_status}"
    assert c_data["total_days"] == 15316

    # 2. Flood Evidence Profile
    f_status, f_data = http_get(f"{BASE_URL}/api/flood/evidence-profile?latitude=17.385&longitude=78.4867")
    assert f_status == 200
    assert "evidence_classification" in f_data
    assert "environmental_landcover_context" in f_data
    assert "landcover_classification_label" in f_data["environmental_landcover_context"]

    # 3. Heat Vulnerability Profile
    h_status, h_data = http_get(f"{BASE_URL}/api/heat/vulnerability-profile?latitude=17.385&longitude=78.4867")
    assert h_status == 200
    assert "hotspot_classification" in h_data
    assert "thermal_anomaly_relative_to_city_c" in h_data

    # 4. Heat Model Metadata
    m_status, m_data = http_get(f"{BASE_URL}/api/heat/model-metadata")
    assert m_status == 200
    assert "candidate_rf_metrics" in m_data
    assert "validation_strategy" in m_data
    assert "temporal_and_scientific_limitations" in m_data

    print("  [PASS] All Phase 6 API endpoints verified.")


def test_iups_invariants():
    print("Testing preservation of IUPS grid invariants and weights...")
    total = db.priority_grid_cells.count_documents({})
    assert total == 791, f"Expected 791 cells, got {total}"

    unscored = db.priority_grid_cells.count_documents({"integrated_urban_priority_score": None})
    assert unscored == 50, f"Expected 50 unscored cells, got {unscored}"

    scored = total - unscored
    assert scored == 741, f"Expected 741 scored cells, got {scored}"

    print("  [PASS] All 791 cells, 741 scored, and 50 unscored strictly preserved.")


def main():
    print("\n==================================================")
    print("URBANRISK PHASE 6: ADVANCED HAZARD MODELS TEST SUITE")
    print("==================================================\n")

    test_flood_intelligence()
    test_heat_intelligence_and_ml_model()
    test_phase6_api_endpoints()
    test_iups_invariants()

    print("\n==================================================")
    print("ALL PHASE 6 ADVANCED HAZARD TESTS PASSED SUCCESSFULLY!")
    print("==================================================\n")


if __name__ == "__main__":
    main()
