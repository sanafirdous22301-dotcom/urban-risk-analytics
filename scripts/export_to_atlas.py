"""
MongoDB Local to Atlas Migration Utility
URBANRISK -- Integrated Urban Risk Analytics Platform

This script safely transfers all 9 collections and their spatial 2dsphere indexes
from your local MongoDB (urban_risk_db) to your MongoDB Atlas cluster.

Usage:
    python scripts/export_to_atlas.py --atlas-uri "mongodb+srv://<user>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"
"""

import argparse
import sys
from pymongo import MongoClient

COLLECTIONS = [
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

def migrate_to_atlas(atlas_uri: str, db_name: str = "urban_risk_db"):
    print("=" * 65)
    print(" URBANRISK -- Safe MongoDB Local to Atlas Transfer")
    print("=" * 65)

    # 1. Connect to Local MongoDB
    print("\n[1/4] Connecting to Local MongoDB (mongodb://127.0.0.1:27017/)...")
    try:
        local_client = MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=4000)
        local_client.admin.command("ping")
        local_db = local_client[db_name]
        print(f"      Connected to local database: '{db_name}'.")
    except Exception as e:
        print(f"      ERROR: Could not connect to local MongoDB: {e}")
        sys.exit(1)

    # 2. Connect to MongoDB Atlas
    print("\n[2/4] Connecting to MongoDB Atlas cluster...")
    try:
        atlas_client = MongoClient(atlas_uri, serverSelectionTimeoutMS=10000)
        atlas_client.admin.command("ping")
        atlas_db = atlas_client[db_name]
        print(f"      Connected to MongoDB Atlas: '{db_name}'.")
    except Exception as e:
        print(f"      ERROR: Could not connect to MongoDB Atlas: {e}")
        print("      Check your username, password, and Atlas IP Access List (0.0.0.0/0).")
        sys.exit(1)

    # 3. Transfer Collections Safely
    print("\n[3/4] Transferring collections...")
    for col_name in COLLECTIONS:
        doc_count = local_db[col_name].count_documents({})
        if doc_count == 0:
            print(f"      Skipping empty collection: {col_name}")
            continue

        print(f"      Transferring '{col_name}' ({doc_count:,} documents)...", end="", flush=True)
        cursor = local_db[col_name].find({})
        batch = []
        inserted = 0

        # Drop existing Atlas collection before re-populating to prevent duplicates
        atlas_db[col_name].drop()

        for doc in cursor:
            batch.append(doc)
            if len(batch) >= 1000:
                atlas_db[col_name].insert_many(batch)
                inserted += len(batch)
                batch = []

        if batch:
            atlas_db[col_name].insert_many(batch)
            inserted += len(batch)

        print(f" Done ({inserted:,} inserted).")

    # 4. Recreate Essential Spatial Indexes
    print("\n[4/4] Creating geospatial 2dsphere indexes on Atlas...")
    try:
        atlas_db.infrastructure_assets.create_index([("geom", "2dsphere")])
        print("      Created 2dsphere index on 'infrastructure_assets.geom'.")
    except Exception as e:
        print(f"      Notice for infrastructure_assets: {e}")

    try:
        atlas_db.road_segments.create_index([("geom", "2dsphere")])
        print("      Created 2dsphere index on 'road_segments.geom'.")
    except Exception as e:
        print(f"      Notice for road_segments: {e}")

    print("\n" + "=" * 65)
    print(" TRANSFER COMPLETE! MongoDB Atlas is ready for Render deployment.")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transfer local MongoDB to Atlas")
    parser.add_argument("--atlas-uri", required=True, help="MongoDB Atlas connection string")
    parser.add_argument("--database", default="urban_risk_db", help="Database name (default: urban_risk_db)")
    args = parser.parse_args()

    migrate_to_atlas(args.atlas_uri, args.database)
