"""
scripts/backup_dataset_versions.py
Dual-target pre-migration backup for urban_risk_db.dataset_versions.
STRICTLY NON-DESTRUCTIVE: Aborts if targets exist. Never drops existing collections.
"""

import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import bson.json_util
from pymongo import MongoClient

EXPECTED_PAIRS = [(1, 1), (9, 9), (10, 10), (11, 11), (12, 12), (13, 13)]
BACKUP_DIR = Path(__file__).resolve().parents[1] / "database" / "backups"

def compute_docs_hash(docs):
    # Sort docs by _id for deterministic canonical hashing
    sorted_docs = sorted(docs, key=lambda d: d["_id"])
    serialized = bson.json_util.dumps(sorted_docs, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def run_backup():
    client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=3000)
    db = client["urban_risk_db"]
    source_col = db["dataset_versions"]

    # 1. Verify source collection state
    count = source_col.count_documents({})
    if count != 6:
        raise RuntimeError(f"ABORT: Expected 6 documents in dataset_versions, found {count}.")

    existing_docs = list(source_col.find({}))
    actual_pairs = [(d["_id"], d.get("dataset_id")) for d in sorted(existing_docs, key=lambda x: x["_id"])]
    if actual_pairs != EXPECTED_PAIRS:
        raise RuntimeError(f"ABORT: Document (_id, dataset_id) pairs {actual_pairs} do not match expected {EXPECTED_PAIRS}.")

    source_hash = compute_docs_hash(existing_docs)

    # 2. Check collision on targets
    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_col_name = f"dataset_versions_backup_{timestamp_str}"
    
    if backup_col_name in db.list_collection_names():
        raise FileExistsError(f"ABORT: Backup collection '{backup_col_name}' already exists.")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    json_path = BACKUP_DIR / f"{backup_col_name}.json"
    if json_path.exists():
        raise FileExistsError(f"ABORT: Backup file '{json_path}' already exists.")

    # 3. Create MongoDB collection backup
    backup_col = db[backup_col_name]
    insert_res = backup_col.insert_many([doc.copy() for doc in existing_docs])
    if len(insert_res.inserted_ids) != 6:
        raise RuntimeError(f"ABORT: Failed to insert 6 documents into {backup_col_name}.")

    # Duplicate indexes on backup collection for fidelity
    for idx in source_col.list_indexes():
        if idx["name"] != "_id_":
            backup_col.create_index(list(idx["key"].items()), name=idx["name"])

    # Verify MongoDB backup collection
    db_backup_docs = list(backup_col.find({}))
    db_backup_pairs = [(d["_id"], d.get("dataset_id")) for d in sorted(db_backup_docs, key=lambda x: x["_id"])]
    if db_backup_pairs != EXPECTED_PAIRS:
        raise RuntimeError("ABORT: ID mismatch in MongoDB backup collection.")
    db_backup_hash = compute_docs_hash(db_backup_docs)
    if db_backup_hash != source_hash:
        raise RuntimeError(f"ABORT: Content hash mismatch in MongoDB backup collection ({db_backup_hash} vs {source_hash}).")

    # 4. Create BSON JSON backup
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(bson.json_util.dumps(sorted(existing_docs, key=lambda d: d["_id"]), indent=2))

    # Verify JSON backup
    with open(json_path, "r", encoding="utf-8") as f:
        file_docs = bson.json_util.loads(f.read())
    file_pairs = [(d["_id"], d.get("dataset_id")) for d in sorted(file_docs, key=lambda x: x["_id"])]
    if file_pairs != EXPECTED_PAIRS:
        raise RuntimeError("ABORT: ID mismatch in JSON file backup.")
    file_hash = compute_docs_hash(file_docs)
    if file_hash != source_hash:
        raise RuntimeError(f"ABORT: Content hash mismatch in JSON file backup ({file_hash} vs {source_hash}).")

    print("BACKUP VERIFICATION SUCCESSFUL:")
    print(f" - Verified Documents: 6 / 6")
    print(f" - Canonical SHA-256:  {source_hash}")
    print(f" - MongoDB Collection: urban_risk_db.{backup_col_name}")
    print(f" - JSON Archive File:  {json_path.resolve()}")
    return backup_col_name, str(json_path.resolve()), source_hash

if __name__ == "__main__":
    run_backup()
