"""
scripts/migrate_dataset_metadata.py
Phase 1 Metadata Migration for dataset_versions.
STRICT INVARIANTS:
1. Every filter includes BOTH _id and dataset_id: {"_id": doc_id, "dataset_id": expected_id}.
2. Protected fields remain 100% unchanged:
   _id, dataset_id, dataset_name, source_name, file_path, version_label, record_count, retrieved_at.
3. Record 10 source_name is preserved verbatim as 'Rainfall processed source'.
4. Additive fields only under $set.
5. Idempotent: Subsequent executions produce modified_count == 0.
"""

import sys
from pymongo import MongoClient

PROTECTED_FIELDS = [
    "_id", "dataset_id", "dataset_name", "source_name", 
    "file_path", "version_label", "record_count", "retrieved_at"
]

METADATA_UPDATES = {
    1: {
        "expected_dataset_id": 1,
        "set_fields": {
            "source_product": "MODIS Satellite Land Surface Temperature 1-km Baseline",
            "observation_period": {"start_date": "2018-01-01", "end_date": "2018-12-31"},
            "observation_description": "2018 MODIS satellite Land Surface Temperature observations",
            "source_publication_date": None,
            "temporal_coverage": "2018 Calendar Year",
            "is_real_time": False,
            "is_forecast": False
        }
    },
    9: {
        "expected_dataset_id": 9,
        "set_fields": {
            "source_product": "Surface Urban Heat Island (UHI) Multi-Year Baseline",
            "observation_period": {"start_year": 2003, "end_year": 2018},
            "observation_description": "Multi-year summer daytime and nighttime surface UHI baseline",
            "source_publication_date": None,
            "temporal_coverage": "2003–2018 Summer Baseline",
            "is_real_time": False,
            "is_forecast": False
        }
    },
    10: {
        "expected_dataset_id": 10,
        "set_fields": {
            # Note: source_name remains "Rainfall processed source" unchanged
            "source_product": "CHIRPS v3.0 Daily COG Raster Extraction",
            "observation_period": {"storm_dates": ["2020-09-25", "2021-10-08"]},
            "observation_description": "CHIRPS v3.0 daily raster extraction for two historical extreme precipitation events",
            "raster_samples_count": 84,
            "distinct_storm_dates_count": 2,
            "source_publication_date": None,
            "temporal_coverage": "Historical Storm Events (September 2020 & October 2021)",
            "is_real_time": False,
            "is_forecast": False
        }
    },
    11: {
        "expected_dataset_id": 11,
        "set_fields": {
            "source_product": "OpenStreetMap Civic Amenities Spatial Snapshot",
            "observation_period": {"snapshot_date": None, "description": "Civic amenities spatial extract"},
            "observation_description": "Civic infrastructure points snapshot; original query date unrecorded",
            "source_publication_date": None,
            "temporal_coverage": "Civic Amenities Snapshot",
            "is_real_time": False,
            "is_forecast": False
        }
    },
    12: {
        "expected_dataset_id": 12,
        "set_fields": {
            "source_product": "OpenStreetMap Road Network Spatial Snapshot",
            "observation_period": {"snapshot_date": None, "description": "Road network spatial extract"},
            "observation_description": "Road network nodes snapshot; original query date unrecorded",
            "source_publication_date": None,
            "temporal_coverage": "Road Network Snapshot",
            "is_real_time": False,
            "is_forecast": False
        }
    },
    13: {
        "expected_dataset_id": 13,
        "set_fields": {
            "source_product": "National Flood Inventory (Hyderabad District Archive)",
            "observation_period": {"start_year": 1969, "end_year": 2022},
            "observation_description": "National historical flood event inventory (Hyderabad district subset)",
            "source_publication_date": None,
            "temporal_coverage": "1969–2022 Disaster Archive",
            "is_real_time": False,
            "is_forecast": False
        }
    }
}

def execute_migration_on_collection(col):
    """Core migration function applicable to any collection (isolated test or production)."""
    # 1. Pre-validation of 6 expected document identities
    before_docs = {doc["_id"]: doc for doc in col.find({})}
    if len(before_docs) != 6:
        raise RuntimeError(f"ABORT: Expected 6 documents in target collection, found {len(before_docs)}.")

    for doc_id, cfg in METADATA_UPDATES.items():
        doc = before_docs.get(doc_id)
        if not doc:
            raise RuntimeError(f"ABORT: Missing expected document _id={doc_id}.")
        if doc.get("dataset_id") != cfg["expected_dataset_id"]:
            raise RuntimeError(f"ABORT: dataset_id mismatch for _id={doc_id}: expected {cfg['expected_dataset_id']}, found {doc.get('dataset_id')}.")

    total_modified = 0

    # 2. Additive updates with dual-key filter
    for doc_id, cfg in METADATA_UPDATES.items():
        update_filter = {
            "_id": doc_id,
            "dataset_id": cfg["expected_dataset_id"]
        }
        res = col.update_one(update_filter, {"$set": cfg["set_fields"]})
        assert res.matched_count == 1, f"Failed match on {update_filter}"
        assert res.modified_count in (0, 1), f"Unexpected modified_count {res.modified_count} on {update_filter}"
        total_modified += res.modified_count

    # 3. Post-validation: Protected fields immutability check
    after_docs = {doc["_id"]: doc for doc in col.find({})}
    for doc_id, before in before_docs.items():
        after = after_docs[doc_id]
        for field in PROTECTED_FIELDS:
            before_val = before.get(field)
            after_val = after.get(field)
            assert before_val == after_val, (
                f"FATAL: Protected field '{field}' altered in doc _id={doc_id}! '{before_val}' -> '{after_val}'"
            )

    # Specific Record 10 verification
    rec10 = after_docs[10]
    assert rec10["source_name"] == "Rainfall processed source", "Record 10 source_name was altered!"
    assert rec10["source_product"] == "CHIRPS v3.0 Daily COG Raster Extraction"

    return total_modified

def test_migration_isolated():
    """Run migration test against an isolated disposable database using pre-migration backup data."""
    client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
    prod_db = client["urban_risk_db"]
    test_db = client["urban_risk_migration_test_db"]
    test_col = test_db["dataset_versions_test"]

    # Clean any stale test database
    client.drop_database("urban_risk_migration_test_db")

    # Find the earliest pre-migration backup collection to test unmigrated -> migrated transition
    backup_cols = [c for c in prod_db.list_collection_names() if c.startswith("dataset_versions_backup_")]
    if backup_cols:
        source_col = prod_db[sorted(backup_cols)[0]]
        base_docs = list(source_col.find({}))
    else:
        # Fallback to current prod docs
        base_docs = list(prod_db["dataset_versions"].find({}))
        # Strip additive fields to simulate pre-migration state
        for d in base_docs:
            for k in list(d.keys()):
                if k not in PROTECTED_FIELDS:
                    del d[k]

    assert len(base_docs) == 6, f"Expected 6 base docs, found {len(base_docs)}"
    test_col.insert_many([d.copy() for d in base_docs])

    # Run pass 1 on isolated collection (must modify all 6 unmigrated docs)
    mod1 = execute_migration_on_collection(test_col)
    print(f"Isolated Test Pass 1: modified {mod1}/6 documents.")
    assert mod1 == 6, f"Expected 6 modifications on first run, got {mod1}"

    # Run pass 2 on isolated collection (Idempotency test: must modify 0 docs)
    mod2 = execute_migration_on_collection(test_col)
    print(f"Isolated Test Pass 2: modified {mod2}/6 documents.")
    assert mod2 == 0, f"Expected 0 modifications on second run, got {mod2}"

    # Drop isolated test database
    client.drop_database("urban_risk_migration_test_db")
    print("Isolated test database dropped cleanly.")
    print("MIGRATION ISOLATION & IDEMPOTENCY TEST PASSED.")

def run_production_migration():
    """Execute migration against urban_risk_db.dataset_versions."""
    client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
    prod_col = client["urban_risk_db"]["dataset_versions"]
    print("Executing production migration on urban_risk_db.dataset_versions...")
    mod = execute_migration_on_collection(prod_col)
    print(f"Production migration completed. Modified documents: {mod}/6.")
    return mod

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-only":
        test_migration_isolated()
    else:
        # Run isolated test first, then production
        test_migration_isolated()
        run_production_migration()
