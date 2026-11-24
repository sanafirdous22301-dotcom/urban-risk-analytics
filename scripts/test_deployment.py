import json
import sys
from pathlib import Path
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import home, database_health, system_status
from backend.routers.flood import get_flood_summary
from backend.routers.heat import get_heat_summary
from backend.routers.infrastructure import get_infrastructure_summary
from backend.routers.ml import (
    HeatPredictRequest,
    UHIPredictRequest,
    predict_temperature,
    predict_alias,
    predict_uhi,
    ml_model_information
)
from backend.routers.assessments import assess_plot, get_iups_summary, evaluate_coordinates, CoordinateAssessmentRequest
from backend.routers.locations import get_plot_locations
from backend.routers.datasets import get_datasets
from backend.routers.map_layers import get_infrastructure, get_roads
from backend.services.iups_service import assess_plot_iups
from database.mongodb import check_mongodb_connection, db
from database.counters import initialize_counter


def run_comprehensive_tests():
    print("=" * 70)
    print(" URBAN RISK ANALYTICS & ML DEPLOYMENT - COMPREHENSIVE SYSTEM VERIFICATION")
    print("=" * 70)

    passed = 0
    failed = 0
    total = 0

    def record_test(name, success, detail=""):
        nonlocal passed, failed, total
        total += 1
        if success:
            passed += 1
            print(f"[{total:02d}] PASS - {name}")
            if detail:
                print(f"       {detail}")
        else:
            failed += 1
            print(f"[{total:02d}] FAIL - {name}")
            if detail:
                print(f"       ERROR: {detail}")

    # -------------------------------------------------------------
    # 1. DATABASE & MONGODB VERIFICATION
    # -------------------------------------------------------------
    print("\n--- 1. DATABASE & MONGODB INTEGRATION ---")

    # Test 1: MongoDB Ping
    try:
        ping_res = check_mongodb_connection()
        record_test("MongoDB Live Connectivity", ping_res.get("ok") == 1.0, f"Database: {db.name}, Ping: {ping_res.get('ok')}")
    except Exception as e:
        record_test("MongoDB Live Connectivity", False, str(e))

    # Test 2: Nine Collections Existence & Counts
    expected_collections = [
        "dataset_versions",
        "spatial_locations",
        "model_runs",
        "hazard_observations",
        "flood_events",
        "infrastructure_assets",
        "road_segments",
        "risk_assessments",
        "resource_priorities"
    ]
    try:
        existing_cols = db.list_collection_names()
        missing = [c for c in expected_collections if c not in existing_cols]
        counts = {c: db[c].count_documents({}) for c in expected_collections}
        detail = ", ".join([f"{k}: {v}" for k, v in counts.items()])
        record_test("Nine Migrated MongoDB Collections", len(missing) == 0, f"All 9 present. Counts: {detail}")
    except Exception as e:
        record_test("Nine Migrated MongoDB Collections", False, str(e))

    # Test 3: Counters Sequence Initialization
    try:
        initialize_counter("location_id", "spatial_locations", "location_id")
        initialize_counter("dataset_id", "dataset_versions", "dataset_id")
        counters = list(db.counters.find())
        c_map = {c["_id"]: c["sequence_value"] for c in counters}
        record_test("MongoDB Sequence Counters", "location_id" in c_map and "dataset_id" in c_map, f"Counters primed: location_id={c_map.get('location_id')}, dataset_id={c_map.get('dataset_id')}")
    except Exception as e:
        record_test("MongoDB Sequence Counters", False, str(e))

    # -------------------------------------------------------------
    # 2. MACHINE LEARNING & PREDICTION VERIFICATION
    # -------------------------------------------------------------
    print("\n--- 2. MACHINE LEARNING DEPLOYMENT ---")

    # Test 4: ML Model Info
    try:
        info = ml_model_information()
        models = info.get("active_models", [])
        record_test("ML Model Catalog", len(models) >= 2 and all(m["loaded"] for m in models), f"Active models: {[m['name'] for m in models]}")
    except Exception as e:
        record_test("ML Model Catalog", False, str(e))

    # Test 5: Standard Prediction (POST /api/ml/predict)
    try:
        req = HeatPredictRequest(latitude=17.3850, longitude=78.4867, nighttime_temp_c=24.5)
        res = predict_temperature(req)
        p = res["prediction"]
        record_test("ML Predict Daytime Surface Temperature", res["status"] == "success" and p["predicted_daytime_temp_c"] > 0, f"Predicted: {p['predicted_daytime_temp_c']}°C (Diurnal Delta: +{p['diurnal_temperature_difference_c']}°C, Risk: {p['heat_risk_level']})")
    except Exception as e:
        record_test("ML Predict Daytime Surface Temperature", False, str(e))

    # Test 6: Root Prediction Alias (POST /predict)
    try:
        req = HeatPredictRequest(latitude=17.4375, longitude=78.4482, nighttime_temp_c=28.0)
        res = predict_alias(req)
        record_test("ML Predict Root Alias (/predict)", res["status"] == "success", f"Predicted: {res['prediction']['predicted_daytime_temp_c']}°C, Risk: {res['prediction']['heat_risk_level']}")
    except Exception as e:
        record_test("ML Predict Root Alias (/predict)", False, str(e))

    # Test 7: UHI Prediction (POST /api/ml/predict/uhi)
    try:
        req = UHIPredictRequest(latitude=17.3850, longitude=78.4867, nighttime_uhi=1.5)
        res = predict_uhi(req)
        record_test("ML Predict Urban Heat Island Anomaly", res["status"] == "success", f"Predicted Daytime UHI: {res['prediction']['predicted_daytime_uhi_anomaly_c']}°C anomaly")
    except Exception as e:
        record_test("ML Predict Urban Heat Island Anomaly", False, str(e))

    # Test 8: Pydantic Validation - Latitude Boundary
    try:
        HeatPredictRequest(latitude=195.0, longitude=78.4867, nighttime_temp_c=24.5)
        record_test("ML Input Validation (Latitude > 90)", False, "Failed: Out of bounds latitude was accepted")
    except ValidationError as ve:
        record_test("ML Input Validation (Latitude > 90)", True, f"Correctly rejected with HTTP 422 validation: {ve.errors()[0]['msg']}")
    except Exception as e:
        record_test("ML Input Validation (Latitude > 90)", False, str(e))

    # Test 9: Pydantic Validation - Longitude Boundary
    try:
        HeatPredictRequest(latitude=17.3850, longitude=-250.0, nighttime_temp_c=24.5)
        record_test("ML Input Validation (Longitude < -180)", False, "Failed: Out of bounds longitude was accepted")
    except ValidationError as ve:
        record_test("ML Input Validation (Longitude < -180)", True, f"Correctly rejected with HTTP 422 validation: {ve.errors()[0]['msg']}")
    except Exception as e:
        record_test("ML Input Validation (Longitude < -180)", False, str(e))

    # -------------------------------------------------------------
    # 3. SPATIAL & MULTI-HAZARD RISK ANALYTICS
    # -------------------------------------------------------------
    print("\n--- 3. SPATIAL & MULTI-HAZARD ANALYTICS ---")

    # Test 10: Precomputed IUPS Grid Service
    try:
        iups = assess_plot_iups(17.3850, 78.4867)
        record_test("IUPS Grid Service (Local Precomputed 1-km Grid)", iups["status"] == "success", f"Grid ID: {iups['grid']['grid_id']}, Priority Score: {iups['priority_score']}, Band: {iups['priority_band']}")
    except Exception as e:
        record_test("IUPS Grid Service (Local Precomputed 1-km Grid)", False, str(e))

    # Test 11: Citywide IUPS Summary
    try:
        summary = get_iups_summary()
        record_test("Citywide IUPS Summary API", summary["grid_cells"] == 791 and summary["available_priority_scores"] == 741, f"Total Cells: {summary['grid_cells']}, Scored: {summary['available_priority_scores']}, Weights: {summary['weights']}")
    except Exception as e:
        record_test("Citywide IUPS Summary API", False, str(e))

    # Test 12: Saved Plots Listing
    try:
        plots = get_plot_locations()
        record_test("Spatial Locations Listing (/api/locations/plots)", plots["total"] > 0, f"Total saved plot locations: {plots['total']}")
    except Exception as e:
        record_test("Spatial Locations Listing (/api/locations/plots)", False, str(e))

    # Test 13: Plot Assessment Generation (Plot #1)
    try:
        assessment = assess_plot(1)
        record_test("Plot Spatial Assessment (/api/assessments/plots/1)", assessment["assessment_type"] == "spatial_evidence_summary", f"Infrastructure within 1km: {len(assessment['infrastructure']['summary_within_1km'])}, Road points: {assessment['road_network']['candidate_points_in_bbox']}, Hazard obs: {len(assessment['hazard_observations'])}, Historical floods: {assessment['historical_flood_context']['matching_event_count']}")
    except Exception as e:
        record_test("Plot Spatial Assessment (/api/assessments/plots/1)", False, str(e))

    # Test 14: Map Layers Infrastructure Spatial Query ($geoWithin)
    try:
        infra = get_infrastructure(78.4, 17.3, 78.5, 17.4)
        record_test("Map Infrastructure GeoJSON Layer", infra["type"] == "FeatureCollection" and infra["total"] > 0, f"Features returned within bounding box: {infra['total']}")
    except Exception as e:
        record_test("Map Infrastructure GeoJSON Layer", False, str(e))

    # Test 15: Map Layers Roads Spatial Query ($geoWithin)
    try:
        roads = get_roads(78.4, 17.3, 78.5, 17.4)
        record_test("Map Roads GeoJSON Layer", roads["type"] == "FeatureCollection" and roads["total"] > 0, f"Features returned within bounding box: {roads['total']}")
    except Exception as e:
        record_test("Map Roads GeoJSON Layer", False, str(e))

    # Test 16: Datasets Registry
    try:
        datasets = get_datasets()
        record_test("Datasets Registry (/api/datasets/)", datasets["total"] > 0, f"Registered datasets in MongoDB: {datasets['total']}")
    except Exception as e:
        record_test("Datasets Registry (/api/datasets/)", False, str(e))

    # -------------------------------------------------------------
    # 4. FASTAPI PLATFORM HEALTH & SYSTEM STATUS
    # -------------------------------------------------------------
    print("\n--- 4. FASTAPI PLATFORM HEALTH & STATUS ---")

    # Test 17: Root Home Endpoint
    try:
        h = home()
        record_test("FastAPI Home Endpoint (/)", h["status"] == "success" and h["ml_model_deployed"] is True, f"Status: {h['status']}, ML Deployed: {h['ml_model_deployed']}")
    except Exception as e:
        record_test("FastAPI Home Endpoint (/)", False, str(e))

    # Test 18: Database Health Endpoint
    try:
        dh = database_health()
        record_test("Database Health Endpoint (/health/db)", dh["status"] == "connected", f"Database: {dh['database']}, Version: {dh['mongodb_version']}, Ping: {dh['ping']}")
    except Exception as e:
        record_test("Database Health Endpoint (/health/db)", False, str(e))

    # Test 19: System Status Endpoint
    try:
        sys_stat = system_status()
        record_test("System Status Endpoint (/api/system-status)", sys_stat["status"] == "connected" and len(sys_stat["table_counts"]) == 9, f"Status: {sys_stat['status']}, Tracked collections: {len(sys_stat['table_counts'])}")
    except Exception as e:
        record_test("System Status Endpoint (/api/system-status)", False, str(e))

    # -------------------------------------------------------------
    # 5. DEDICATED MODULE SUMMARIES & PERSISTENCE VERIFICATION
    # -------------------------------------------------------------
    print("\n--- 5. DEDICATED MODULE SUMMARIES & PERSISTENCE ---")

    # Test 20: Flood Intelligence Summary
    try:
        fl_sum = get_flood_summary()
        record_test("Flood Summary Endpoint (/api/flood/summary)", fl_sum["status"] == "operational" and fl_sum["total_flood_events"] == 40, f"Total Floods: {fl_sum['total_flood_events']}, Fatalities: {fl_sum['fatalities_total']}, Rainfall Obs: {fl_sum['rainfall_observations']['total_records']}")
    except Exception as e:
        record_test("Flood Summary Endpoint (/api/flood/summary)", False, str(e))

    # Test 21: Urban Heat Intelligence Summary
    try:
        ht_sum = get_heat_summary()
        record_test("Heat Summary Endpoint (/api/heat/summary)", ht_sum["status"] == "operational" and ht_sum["total_heat_observations"] == 14530, f"Total Heat Obs: {ht_sum['total_heat_observations']}, MODIS Day Mean: {ht_sum['datasets']['modis']['daytime_temp_c']['mean']}°C, ML Status: {ht_sum['ml_deployment']['status']}")
    except Exception as e:
        record_test("Heat Summary Endpoint (/api/heat/summary)", False, str(e))

    # Test 22: Infrastructure Intelligence Summary
    try:
        inf_sum = get_infrastructure_summary()
        record_test("Infrastructure Summary Endpoint (/api/infrastructure/summary)", inf_sum["status"] == "operational" and inf_sum["infrastructure_assets"]["total_records"] == 2083, f"Assets: {inf_sum['infrastructure_assets']['total_records']}, Roads: {inf_sum['road_network']['total_records']}")
    except Exception as e:
        record_test("Infrastructure Summary Endpoint (/api/infrastructure/summary)", False, str(e))

    # Test 23: Model Runs Collection Persistence
    try:
        mr_cnt = db.model_runs.count_documents({})
        record_test("MongoDB Persistence: model_runs", mr_cnt >= 1, f"Registered model runs: {mr_cnt}")
    except Exception as e:
        record_test("MongoDB Persistence: model_runs", False, str(e))

    # Test 24: Risk Assessments Collection Persistence
    try:
        ra_cnt = db.risk_assessments.count_documents({})
        record_test("MongoDB Persistence: risk_assessments", ra_cnt >= 1, f"Stored plot assessments: {ra_cnt}")
    except Exception as e:
        record_test("MongoDB Persistence: risk_assessments", False, str(e))

    # Test 25: Resource Priorities Collection Persistence
    try:
        rp_cnt = db.resource_priorities.count_documents({})
        record_test("MongoDB Persistence: resource_priorities", rp_cnt >= 1, f"Stored resource priorities: {rp_cnt}")
    except Exception as e:
        record_test("MongoDB Persistence: resource_priorities", False, str(e))

    # Test 26: Three-Category Risk Assessment (/api/assessments/evaluate)
    try:
        eval_res = evaluate_coordinates(CoordinateAssessmentRequest(latitude=17.3616, longitude=78.4747))
        cats = eval_res.get("category_assessments", {})
        has_3 = "flood_risk" in cats and "heat_risk" in cats and "infrastructure_risk" in cats
        f_cls = cats.get("flood_risk", {}).get("classification")
        h_cls = cats.get("heat_risk", {}).get("classification")
        i_cls = cats.get("infrastructure_risk", {}).get("classification")
        record_test(
            "Three Category Assessments (/api/assessments/evaluate)",
            has_3 and f_cls in ["LOW", "MEDIUM", "HIGH", "REGIONAL CONTEXT ONLY"] and h_cls in ["LOW", "MEDIUM", "HIGH"] and i_cls in ["LOW", "MEDIUM", "HIGH"],
            f"Flood: {f_cls}, Heat: {h_cls} ({cats.get('heat_risk', {}).get('score_value')}/100), Infra: {i_cls} ({cats.get('infrastructure_risk', {}).get('score_value')}/100)"
        )
    except Exception as e:
        record_test("Three Category Assessments (/api/assessments/evaluate)", False, str(e))

    print("\n" + "=" * 70)
    print(f" TOTAL TESTS RUN: {total} | PASSED: {passed} | FAILED: {failed} ({round(passed / total * 100, 1)}%)")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
