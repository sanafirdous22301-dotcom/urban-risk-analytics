"""
Test Suite: Phase 2 Dynamic Risk Grid & Score Recalculation Verification
Tests determinism, complete 791 cell coverage (741 scored, 50 unscored),
missing evidence preservation, MongoDB upsert idempotency, and API integration.
"""
import sys
from pathlib import Path
import math

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.grid_recalculation_service import GridRecalculationService, recalculate_grid, DEFAULT_WEIGHTS
from backend.services.iups_service import assess_plot_iups, load_integrated_grid
import pymongo
import urllib.request
import json

def test_recalculation_determinism_and_invariants():
    print("Testing recalculation determinism and mathematical invariants...")
    df1 = recalculate_grid()
    df2 = recalculate_grid()

    assert len(df1) == 791, f"Expected 791 rows, got {len(df1)}"
    assert len(df2) == 791, f"Expected 791 rows, got {len(df2)}"

    scored1 = df1[df1["priority_score_0_100"].notna()]
    unscored1 = df1[df1["priority_score_0_100"].isna()]
    assert len(scored1) == 741, f"Expected 741 scored cells, got {len(scored1)}"
    assert len(unscored1) == 50, f"Expected 50 unscored cells, got {len(unscored1)}"

    # Invariant: all 50 unscored cells must have screening_priority == 'Not scored'
    assert (unscored1["screening_priority"] == "Not scored").all(), "All 50 unscored cells must be 'Not scored'"

    # Determinism across runs
    scored_diff = (df1["priority_score_0_100"].fillna(-1) - df2["priority_score_0_100"].fillna(-1)).abs().max()
    assert scored_diff == 0.0, f"Recalculation non-deterministic: max diff {scored_diff}"
    print("  [PASS] Determinism & Invariants verified (741 scored, 50 unscored).")

def test_missing_evidence_preservation():
    print("Testing missing evidence preservation...")
    df = recalculate_grid()
    # Cells with hazard_component_count == 0 must NEVER have a priority score
    zero_hazard = df[df["hazard_component_count"] == 0]
    assert len(zero_hazard) == 50, f"Expected 50 zero-hazard cells, got {len(zero_hazard)}"
    assert zero_hazard["priority_score_0_100"].isna().all(), "Zero-hazard cells must remain NaN"

    # Missing flood evidence: 765 cells should have NaN flood_evidence_score
    missing_flood = df[df["flood_evidence_score"].isna()]
    assert len(missing_flood) == 765, f"Expected 765 missing flood evidence cells, got {len(missing_flood)}"
    print("  [PASS] Missing evidence preserved (never replaced with 0 or low risk).")

def test_mongodb_duplicate_prevention():
    print("Testing MongoDB collection duplicate prevention...")
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)
    db = client["urban_risk_db"]
    col = db["priority_grid_cells"]

    count = col.count_documents({})
    assert count == 791, f"Expected exactly 791 documents in priority_grid_cells, found {count}"

    # Verify unique grid_ids
    unique_ids = col.distinct("grid_id")
    assert len(unique_ids) == 791, f"Expected 791 unique grid_ids, found {len(unique_ids)}"

    # Verify run logs
    run_col = db["grid_recalculation_runs"]
    run_count = run_col.count_documents({})
    assert run_count >= 1, "Expected at least 1 run log entry"
    print(f"  [PASS] MongoDB collection has exactly 791 unique documents and {run_count} audit run logs.")

def test_dynamic_api_endpoints():
    print("Testing dynamic API endpoints on http://127.0.0.1:8000 ...")
    base_url = "http://127.0.0.1:8000"

    # Test /api/assessments/priority-grid/top
    req1 = urllib.request.Request(f"{base_url}/api/assessments/priority-grid/top?limit=800")
    with urllib.request.urlopen(req1, timeout=5) as res1:
        assert res1.status == 200, f"Expected 200, got {res1.status}"
        data = json.loads(res1.read().decode())
    assert "last_calculated_at" in data, "Response missing last_calculated_at"
    assert data.get("source_type") == "dynamic_mongodb_grid", f"Expected dynamic_mongodb_grid, got {data.get('source_type')}"
    assert data["total_scored_cells"] == 741, f"Expected 741 scored cells, got {data.get('total_scored_cells')}"
    assert len(data["top_priority_cells"]) == 741, f"Expected 741 top priority cells, got {len(data['top_priority_cells'])}"

    # Test /api/assessments/summary
    req2 = urllib.request.Request(f"{base_url}/api/assessments/summary")
    with urllib.request.urlopen(req2, timeout=5) as res2:
        assert res2.status == 200, f"Expected 200, got {res2.status}"
        sum_data = json.loads(res2.read().decode())
    assert "last_calculated_at" in sum_data, "Summary missing last_calculated_at"
    assert sum_data.get("recalculation_status") == "active", f"Expected active status, got {sum_data.get('recalculation_status')}"

    # Test plot assessment integration
    plot_res = assess_plot_iups(17.3616, 78.4747)
    assert plot_res["priority_score"] is not None, "Plot assessment returned None for Charminar"
    assert 0 <= plot_res["priority_score"] <= 100, "Plot priority score out of range"
    print("  [PASS] Dynamic API endpoints and plot assessment verified successfully.")

if __name__ == "__main__":
    test_recalculation_determinism_and_invariants()
    test_missing_evidence_preservation()
    test_mongodb_duplicate_prevention()
    test_dynamic_api_endpoints()
    print("\nALL PHASE 2 VERIFICATION TESTS PASSED SUCCESSFULLY!")
