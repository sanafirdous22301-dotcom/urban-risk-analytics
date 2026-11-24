import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import socket
socket.gethostname = lambda: "localhost"

from pathlib import Path
from pymongo import MongoClient
from bson import json_util
import json

# Verify the existing backup
backup = Path("atlas_backup_before_migration/20261121_002637")
summary_file = backup / "backup_summary.json"

if not summary_file.exists():
    raise FileNotFoundError("Backup summary not found.")

summary = json.loads(summary_file.read_text(encoding="utf-8"))

print("\n========== BACKUP VERIFICATION ==========")
for name, info in summary.items():
    file = backup / f"{name}.json"
    if not file.exists():
        raise FileNotFoundError(f"Missing backup file: {file}")

    docs = json_util.loads(file.read_text(encoding="utf-8"))
    print(f"{name}: expected {info['documents']}, verified {len(docs)}")

# Inspect local database
from database.mongodb import db as local_db

print("\n========== LOCAL DATABASE ==========")

for name in sorted(local_db.list_collection_names()):
    collection = local_db[name]
    print(f"\n{name}: {collection.count_documents({})} documents")
    for index in collection.list_indexes():
        print("  INDEX:", dict(index))

# Inspect Atlas
uri = input("\nPaste your NEW Atlas URI: ").strip()
client = MongoClient(uri, serverSelectionTimeoutMS=20000)

try:
    client.admin.command("ping")
    atlas_db = client["urban_risk_db"]

    print("\n========== ATLAS DATABASE ==========")

    for name in sorted(atlas_db.list_collection_names()):
        collection = atlas_db[name]
        print(f"\n{name}: {collection.count_documents({})} documents")
        for index in collection.list_indexes():
            print("  INDEX:", dict(index))

finally:
    client.close()

print("\n========== AUDIT COMPLETED ==========")
print("No database records were modified.")

