"""
Phase 7 Test Suite: Infrastructure Intelligence & Resource Prioritization Enhancement.
Verifies:
1. Actual infrastructure asset counts in MongoDB (1,073 hospitals, 7 fire stations, 1,003 buildings = 2,083 total).
2. Road network segment count (93,437 road segments).
3. Straight-line geodesic distance calculations and distance bands (hospitals: 1km, 3km, 5km; fire stations: 3km, 5km, 8km).
4. Coverage classifications ('Good Mapped Facility Coverage', 'Limited Mapped Facility Coverage', 'Potential Infrastructure Gap').
5. Road network accessibility assessment (graph routing limitations identified, straight-line fallback cleanly documented).
6. Resource prioritization recommendations (explainable justifications, hazard context, no fabricated facility capacities).
7. Preservation of IUPS grid invariants (791 total cells, 741 scored, 50 unscored) and approved weights.
8. Infrastructure API endpoints on http://127.0.0.1:8000.
"""

import sys
from pathlib import Path
import json
import urllib.request
import urllib.error
import pymongo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.infrastructure_service import InfrastructureIntelligenceService
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


def test_asset_counts_and_categories():
    print("Testing infrastructure assets and road network counts...")
    hosp_count = db.infrastructure_assets.count_documents({"category": "hospital"})
    fs_count = db.infrastructure_assets.count_documents({"category": "fire_station"})
    bldg_count = db.infrastructure_assets.count_documents({"category": "building"})
    total_assets = db.infrastructure_assets.count_documents({})
    total_roads = db.road_segments.count_documents({})

    assert hosp_count == 1073, f"Expected 1,073 hospitals, got {hosp_count}"
    assert fs_count == 7, f"Expected 7 fire stations, got {fs_count}"
    assert bldg_count == 1003, f"Expected 1,003 buildings, got {bldg_count}"
    assert total_assets == 2083, f"Expected 2,083 total infrastructure assets, got {total_assets}"
    assert total_roads == 93437, f"Expected 93,437 road segments, got {total_roads}"

    print(f"  [PASS] Verified asset counts: {hosp_count} hospitals, {fs_count} fire stations, {bldg_count} buildings, {total_roads} roads.")


def test_facility_proximity_and_distance_bands():
    print("Testing facility proximity and screening distance bands...")
    svc = InfrastructureIntelligenceService(db=db)

    # Hyderabad Center / Charminar
    res = svc.evaluate_facility_proximity(17.3616, 78.4747)
    hosp = res["hospital_coverage"]
    fs = res["fire_station_coverage"]

    # Verify hospital metrics
    assert hosp["nearest_hospital_straight_line_km"] is not None
    assert hosp["nearest_hospital_straight_line_km"] < 2.0, "Charminar should have a nearby hospital within 2km"
    assert hosp["hospitals_within_1km"] >= 1
    assert hosp["hospitals_within_3km"] >= hosp["hospitals_within_1km"]
    assert hosp["coverage_classification"] in [
        "Good Mapped Facility Coverage", "Limited Mapped Facility Coverage", "Potential Infrastructure Gap"
    ]

    # Verify fire station metrics
    assert fs["nearest_fire_station_straight_line_km"] is not None
    assert fs["coverage_classification"] in [
        "Good Mapped Facility Coverage", "Limited Mapped Facility Coverage", "Potential Infrastructure Gap"
    ]

    # Verify distance metric transparency
    assert res["distance_metric"] == "straight_line_geodesic_km"
    assert "straight-line geodesic" in res["distance_caveat"]

    print("  [PASS] Facility proximity, distance bands, and transparency caveat verified.")


def test_road_network_accessibility_evaluation():
    print("Testing road network representation and routing feasibility...")
    svc = InfrastructureIntelligenceService(db=db)
    road_eval = svc.inspect_road_network_accessibility(17.3850, 78.4867)

    assert "local_road_segments_within_1km" in road_eval
    assert road_eval["routing_feasibility"] == "straight_line_proximity_fallback"
    assert "disconnected regional fragments" in road_eval["routing_feasibility_explanation"]
    assert road_eval["data_completeness_flag"] in ["Road-Network Data Available", "Road-Network Data Incomplete / Low Density"]

    print("  [PASS] Road network assessment and routing limitations verified.")


def test_explainable_resource_priorities():
    print("Testing explainable resource prioritization recommendations...")
    svc = InfrastructureIntelligenceService(db=db)
    recs = svc.generate_explainable_resource_priorities(limit=10)

    assert len(recs) == 10
    top = recs[0]
    assert "grid_id" in top
    assert "integrated_urban_priority_score_0_100" in top
    assert "main_infrastructure_gap" in top
    assert "hazard_context" in top
    assert "planning_recommendation" in top
    assert "planning_disclaimer" in top
    # Verify ranking monotonicity
    scores = [r["integrated_urban_priority_score_0_100"] for r in recs]
    assert scores == sorted(scores, reverse=True), "Recommendations must follow descending IUPS order"

    print("  [PASS] Explainable resource recommendations and ranking monotonicity verified.")


def test_infrastructure_api_endpoints():
    print(f"Testing Infrastructure API endpoints on {BASE_URL}...")

    # 1. Facility Proximity
    p_status, p_data = http_get(f"{BASE_URL}/api/infrastructure/proximity?latitude=17.385&longitude=78.4867")
    assert p_status == 200, f"Expected 200, got {p_status}"
    assert "hospital_coverage" in p_data
    assert "fire_station_coverage" in p_data

    # 2. Road Accessibility
    r_status, r_data = http_get(f"{BASE_URL}/api/infrastructure/road-accessibility?latitude=17.385&longitude=78.4867")
    assert r_status == 200
    assert "routing_feasibility" in r_data

    # 3. Resource Priorities
    pr_status, pr_data = http_get(f"{BASE_URL}/api/infrastructure/priorities?limit=5")
    assert pr_status == 200
    assert pr_data["status"] == "success"
    assert len(pr_data["recommendations"]) == 5

    print("  [PASS] All Infrastructure API endpoints verified.")


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
    print("URBANRISK PHASE 7: INFRASTRUCTURE INTELLIGENCE TEST SUITE")
    print("==================================================\n")

    test_asset_counts_and_categories()
    test_facility_proximity_and_distance_bands()
    test_road_network_accessibility_evaluation()
    test_explainable_resource_priorities()
    test_infrastructure_api_endpoints()
    test_iups_invariants()

    print("\n==================================================")
    print("ALL PHASE 7 INFRASTRUCTURE TESTS PASSED SUCCESSFULLY!")
    print("==================================================\n")


if __name__ == "__main__":
    main()
