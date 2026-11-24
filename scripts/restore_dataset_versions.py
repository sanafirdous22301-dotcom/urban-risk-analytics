"""
scripts/restore_dataset_versions.py
Controlled, atomic restoration for urban_risk_db.dataset_versions.
STAGING -> VALIDATION -> FORENSIC ARCHIVE -> ATOMIC RENAME.
NEVER automatically triggered on test failure. Requires explicit interactive confirmation.
"""

import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import bson.json_util
from pymongo import MongoClient

EXPECTED_PAIRS = [(1, 1), (9, 9), (10, 10), (11, 11), (12, 12), (13, 13)]

def compute_docs_hash(docs):
    sorted_docs = sorted(docs, key=lambda d: d["_id"])
    serialized = bson.json_util.dumps(sorted_docs, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def restore_from_collection(backup_col_name: str, force_confirm: bool = False):
    client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
    db = client["urban_risk_db"]

    # 1. Validate source backup collection
    if backup_col_name not in db.list_collection_names():
        raise FileNotFoundError(f"ABORT: Backup collection '{backup_col_name}' does not exist in urban_risk_db.")

    backup_docs = list(db[backup_col_name].find({}))
    if len(backup_docs) != 6:
        raise ValueError(f"ABORT: Backup collection contains {len(backup_docs)} docs, expected 6.")

    backup_pairs = [(d["_id"], d.get("dataset_id")) for d in sorted(backup_docs, key=lambda x: x["_id"])]
    if backup_pairs != EXPECTED_PAIRS:
        raise ValueError(f"ABORT: Backup ID pairs {backup_pairs} do not match expected {EXPECTED_PAIRS}.")

    backup_hash = compute_docs_hash(backup_docs)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    staging_col_name = "dataset_versions_restore_staging"
    forensic_col_name = f"dataset_versions_pre_restore_forensic_{timestamp_str}"

    # 2. Check collision on staging and forensic targets (NO DROP)
    if staging_col_name in db.list_collection_names():
        raise FileExistsError(f"ABORT: Staging collection '{staging_col_name}' already exists. Refusing to drop.")
    if forensic_col_name in db.list_collection_names():
        raise FileExistsError(f"ABORT: Forensic archive '{forensic_col_name}' already exists. Refusing to drop.")

    # 3. Restore into staging collection
    staging_col = db[staging_col_name]
    staging_col.insert_many([d.copy() for d in backup_docs])

    # Replicate required secondary indexes on staging collection before rename
    active_col = db["dataset_versions"]
    for idx in active_col.list_indexes():
        if idx["name"] != "_id_":
            staging_col.create_index(list(idx["key"].items()), name=idx["name"])

    # Validate staging collection integrity
    staged_docs = list(staging_col.find({}))
    if compute_docs_hash(staged_docs) != backup_hash:
        raise RuntimeError("ABORT: Staging collection content hash mismatch.")

    # 4. Forensic archive of currently active dataset_versions
    active_docs = list(active_col.find({}))
    forensic_col = db[forensic_col_name]
    if active_docs:
        forensic_col.insert_many([d.copy() for d in active_docs])
        for idx in active_col.list_indexes():
            if idx["name"] != "_id_":
                forensic_col.create_index(list(idx["key"].items()), name=idx["name"])
        print(f" - Forensic snapshot archived to: urban_risk_db.{forensic_col_name}")

    # 5. Explicit Confirmation Requirement
    if not force_confirm:
        confirm = input(f"Type 'CONFIRM_RESTORE' to atomically replace dataset_versions from {backup_col_name}: ")
        if confirm.strip() != "CONFIRM_RESTORE":
            raise RuntimeError("Restoration aborted by user.")

    # 6. Controlled atomic rename (dropTarget=True)
    try:
        staging_col.rename("dataset_versions", dropTarget=True)
    except Exception as e:
        # Rollback attempt from forensic snapshot if rename failed
        if forensic_col_name in db.list_collection_names():
            forensic_col.rename("dataset_versions", dropTarget=True)
        raise RuntimeError(f"Rename failed: {e}. Active collection restored from forensic snapshot.")

    # 7. Final post-restoration verification
    restored_docs = list(db["dataset_versions"].find({}))
    assert len(restored_docs) == 6, f"Post-restore count was {len(restored_docs)}"
    assert compute_docs_hash(restored_docs) == backup_hash, "Post-restore hash mismatch"

    print("RESTORE SUCCESSFUL:")
    print(f" - Active collection 'dataset_versions' restored from {backup_col_name}")
    print(f" - Verified 6 documents, full content hash: {backup_hash}")
    print(f" - Forensic backup preserved at: {forensic_col_name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore_dataset_versions.py <backup_collection_name>")
        sys.exit(1)
    restore_from_collection(sys.argv[1])
