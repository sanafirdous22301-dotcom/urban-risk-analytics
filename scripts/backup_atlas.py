
import socket

# Work around the Unicode Windows hostname.
# This changes the hostname only inside this Python process.
socket.gethostname = lambda: "localhost"

from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from bson import json_util
import json

backup_dir = (
    Path("atlas_backup_before_migration")
    / datetime.now().strftime("%Y%m%d_%H%M%S")
)
backup_dir.mkdir(parents=True, exist_ok=True)

uri = input("Paste your NEW Atlas URI: ").strip()

client = MongoClient(uri, serverSelectionTimeoutMS=20000)

try:
    client.admin.command("ping")
    db = client["urban_risk_db"]

    print("\nAtlas connection successful.")
    summary = {}

    for name in db.list_collection_names():
        collection = db[name]

        documents = list(collection.find({}))
        indexes = list(collection.list_indexes())

        (backup_dir / f"{name}.json").write_text(
            json_util.dumps(documents, indent=2),
            encoding="utf-8"
        )

        (backup_dir / f"{name}_indexes.json").write_text(
            json_util.dumps(indexes, indent=2),
            encoding="utf-8"
        )

        summary[name] = {
            "documents": len(documents),
            "indexes": len(indexes)
        }

        print(
            f"Backed up {name}: "
            f"{len(documents)} documents, "
            f"{len(indexes)} indexes"
        )

    (backup_dir / "backup_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8"
    )

    print("\nBACKUP COMPLETED")
    print("Location:", backup_dir.resolve())
    print(
        "Total documents:",
        sum(item["documents"] for item in summary.values())
    )

finally:
    client.close()
