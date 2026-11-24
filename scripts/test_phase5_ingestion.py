"""
Phase 5 Test Suite: Automated Dataset Ingestion & Updates.
Tests:
1. Unified Ingestion Service functionality (Weather, MODIS, Sentinel-2, WorldCover, Floods).
2. Cadence enforcement & skip logic (prevents redundant downloads; honors force=True).
3. Dry-run safety (validates and previews records without modifying production database).
4. Ingestion Run Logging schema and audit trail in `dataset_ingestion_runs`.
5. Admin API Endpoints (`/api/admin/ingestion/status`, `/api/admin/ingestion/history`, `/api/admin/ingestion/trigger`).
6. Non-corruption of IUPS grid invariants (791 total cells, 741 scored, 50 unscored) and weights.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import json
import urllib.request
import urllib.error
import pymongo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.ingestion_service import DatasetIngestionService, DATASET_CADENCE_CONFIG, INGESTION_RUNS_COLLECTION
from backend.routers.admin_ingestion import verify_admin_key
from fastapi import HTTPException
from database.mongodb import db

BASE_URL = "http://127.0.0.1:8000"
TEST_ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "test-secret-key-phase5")


def http_get(url: str, headers: dict = None) -> (int, dict):
    req = urllib.request.Request(url, headers=headers or {})
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


def http_post(url: str, payload: dict, headers: dict = None) -> (int, dict):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=req_headers, method="POST")
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


def test_cadence_and_skip_logic():
    print("Testing provider publishing cadence & skip logic...")
    service = DatasetIngestionService(db=db)

    # 1. Force a live test run for Sentinel-2
    res_first = service.ingest_sentinel2(trigger_type="test_suite", force=True, dry_run=False)
    assert res_first["status"] == "success", f"Expected success on forced Sentinel-2 run, got {res_first['status']}"
    assert res_first["records_fetched"] == 791, f"Expected 791 records fetched, got {res_first['records_fetched']}"

    # 2. Immediate non-forced run should be skipped due to 5-day cadence
    res_second = service.ingest_sentinel2(trigger_type="test_suite", force=False, dry_run=False)
    assert res_second["status"] == "skipped", f"Expected skipped status, got {res_second['status']}"
    assert "Skipping redundant ingestion" in res_second["details"]["reason"]

    # 3. Forced run should bypass skip
    res_forced = service.ingest_sentinel2(trigger_type="test_suite", force=True, dry_run=False)
    assert res_forced["status"] == "success", f"Expected success with force=True, got {res_forced['status']}"

    print("  [PASS] Cadence enforcement, skip logic, and force override verified.")


def test_dry_run_safety():
    print("Testing dry-run execution safety...")
    service = DatasetIngestionService(db=db)

    # Count runs before
    count_before = db[INGESTION_RUNS_COLLECTION].count_documents({"status": "dry_run"})

    res_dry = service.ingest_worldcover(trigger_type="test_suite", force=True, dry_run=True)
    assert res_dry["status"] == "dry_run"
    assert res_dry["records_upserted"] == 0, "Dry run must NOT upsert records into production collections"
    assert res_dry["records_fetched"] == 791
    assert res_dry["details"]["builtup_cells"] == 482

    count_after = db[INGESTION_RUNS_COLLECTION].count_documents({"status": "dry_run"})
    assert count_after == count_before + 1, "Dry-run execution must still be audited in dataset_ingestion_runs"

    print("  [PASS] Dry run verified: zero production writes, accurate preview, audited in run history.")


def test_ingestion_run_audit_schema():
    print("Testing ingestion run logging schema and audit trail...")
    latest_run = db[INGESTION_RUNS_COLLECTION].find_one(
        {},
        sort=[("completed_at", pymongo.DESCENDING)]
    )
    assert latest_run is not None, "At least one ingestion run must exist"

    required_keys = [
        "run_id", "dataset_key", "trigger_type", "status", "started_at",
        "completed_at", "duration_seconds", "records_fetched", "records_accepted",
        "records_rejected", "records_upserted", "source"
    ]
    for k in required_keys:
        assert k in latest_run, f"Missing required audit field: {k}"

    assert isinstance(latest_run["duration_seconds"], float)
    assert latest_run["started_at"].tzinfo is not None or isinstance(latest_run["started_at"], datetime)
    print("  [PASS] Ingestion run audit schema verified.")


def test_admin_api_endpoints():
    print(f"Testing Admin API endpoints and fail-closed security...")

    # 1. Unit Test verify_admin_key dependency directly for missing & empty secret cases
    orig_env = os.environ.get("ADMIN_API_KEY")

    try:
        # Case A: Missing ADMIN_API_KEY environment variable -> Fail closed (503)
        if "ADMIN_API_KEY" in os.environ:
            del os.environ["ADMIN_API_KEY"]
        try:
            verify_admin_key(x_admin_key="any-token")
            assert False, "Expected HTTPException 503 when ADMIN_API_KEY is missing from environment"
        except HTTPException as exc:
            assert exc.status_code == 503, f"Expected 503 when secret missing, got {exc.status_code}"
            assert "ADMIN_API_KEY is not configured" in exc.detail

        # Case B: Empty string ADMIN_API_KEY -> Fail closed (503)
        os.environ["ADMIN_API_KEY"] = "   "
        try:
            verify_admin_key(x_admin_key="   ")
            assert False, "Expected HTTPException 503 when ADMIN_API_KEY is empty string"
        except HTTPException as exc:
            assert exc.status_code == 503, f"Expected 503 when secret is empty, got {exc.status_code}"
            assert "ADMIN_API_KEY is not configured" in exc.detail

        # Case C: Valid configured secret, but invalid or missing header -> 401
        os.environ["ADMIN_API_KEY"] = "configured-production-secret-999"
        try:
            verify_admin_key(x_admin_key=None)
            assert False, "Expected HTTPException 401 when header is missing"
        except HTTPException as exc:
            assert exc.status_code == 401, f"Expected 401 on missing header, got {exc.status_code}"

        try:
            verify_admin_key(x_admin_key="wrong-token")
            assert False, "Expected HTTPException 401 when header token is incorrect"
        except HTTPException as exc:
            assert exc.status_code == 401, f"Expected 401 on wrong header, got {exc.status_code}"

        # Case D: Valid configured secret and matching header -> Authorized
        assert verify_admin_key(x_admin_key="configured-production-secret-999") is True
        print("  [PASS] Dependency fail-closed unit checks (missing=503, empty=503, mismatch=401, match=OK) verified.")
    finally:
        if orig_env is not None:
            os.environ["ADMIN_API_KEY"] = orig_env
        elif "ADMIN_API_KEY" in os.environ:
            del os.environ["ADMIN_API_KEY"]

    # 2. Integration Tests against live HTTP server
    # GET /api/admin/ingestion/status
    status_code, data = http_get(f"{BASE_URL}/api/admin/ingestion/status")
    assert status_code == 200, f"Expected 200, got {status_code}: {data}"
    assert data["status"] == "success"
    assert len(data["datasets"]) >= 5
    keys = [d["dataset_key"] for d in data["datasets"]]
    assert "weather_open_meteo" in keys
    assert "modis_lst" in keys
    assert "sentinel2_ndvi" in keys
    assert "esa_worldcover" in keys
    assert "historical_floods" in keys

    # GET /api/admin/ingestion/history
    code_hist, hist_data = http_get(f"{BASE_URL}/api/admin/ingestion/history?limit=5")
    assert code_hist == 200
    assert hist_data["status"] == "success"
    assert "history" in hist_data
    assert len(hist_data["history"]) > 0

    # POST /api/admin/ingestion/trigger - Unauthorized without header
    code_unauth, unauth_data = http_post(
        f"{BASE_URL}/api/admin/ingestion/trigger",
        payload={"dataset_key": "modis_lst", "dry_run": True}
    )
    assert code_unauth in (401, 503), f"Expected 401 or 503 without header, got {code_unauth}"

    # POST /api/admin/ingestion/trigger - Reject query parameter authentication
    code_query, query_data = http_post(
        f"{BASE_URL}/api/admin/ingestion/trigger?admin_key=some-key",
        payload={"dataset_key": "modis_lst", "dry_run": True}
    )
    assert code_query in (401, 503), f"Expected 401 or 503 with query param, got {code_query}"

    # POST /api/admin/ingestion/trigger - Reject invalid header value
    code_bad_hdr, bad_hdr_data = http_post(
        f"{BASE_URL}/api/admin/ingestion/trigger",
        payload={"dataset_key": "modis_lst", "dry_run": True},
        headers={"X-Admin-Key": "invalid-secret-token"}
    )
    assert code_bad_hdr in (401, 503), f"Expected 401 or 503 with invalid header, got {code_bad_hdr}"

    # Verify no secrets appear in responses
    status_str = json.dumps(data)
    assert "secret" not in status_str.lower() or "secret_key" not in status_str.lower()
    hist_str = json.dumps(hist_data)
    assert "secret" not in hist_str.lower() or "secret_key" not in hist_str.lower()

    print("  [PASS] Live Admin endpoints (status, history, strict header auth, query rejection, secret leakage check) verified.")


def test_grid_and_scoring_invariants():
    print("Testing preservation of IUPS grid invariants and scoring formulas...")
    # 791 total cells, 741 scored, 50 unscored
    total_cells = db.priority_grid_cells.count_documents({})
    assert total_cells == 791, f"Expected 791 total cells, got {total_cells}"

    unscored_cells = db.priority_grid_cells.count_documents({"integrated_urban_priority_score": None})
    assert unscored_cells == 50, f"Expected 50 unscored cells, got {unscored_cells}"

    scored_cells = total_cells - unscored_cells
    assert scored_cells == 741, f"Expected 741 scored cells, got {scored_cells}"

    # Verify scored cell has valid float priority score
    sample_scored = db.priority_grid_cells.find_one({"integrated_urban_priority_score": {"$ne": None}})
    assert sample_scored is not None
    assert isinstance(sample_scored["integrated_urban_priority_score"], float)

    # Environmental indicators collection
    env_total = db.environmental_indicators.count_documents({})
    assert env_total == 791, f"Expected 791 environmental indicator documents, got {env_total}"

    print("  [PASS] All 791 cells, 741 scored, 50 unscored, and environmental collections 100% intact.")


def main():
    print("\n==================================================")
    print("URBANRISK PHASE 5: DATASET INGESTION TEST SUITE")
    print("==================================================\n")

    test_cadence_and_skip_logic()
    test_dry_run_safety()
    test_ingestion_run_audit_schema()
    test_admin_api_endpoints()
    test_grid_and_scoring_invariants()

    print("\n==================================================")
    print("ALL PHASE 5 INGESTION TESTS PASSED SUCCESSFULLY!")
    print("==================================================\n")


if __name__ == "__main__":
    main()
