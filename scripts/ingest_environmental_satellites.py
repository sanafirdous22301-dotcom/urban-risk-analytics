"""
Administrative CLI Script: Ingest and Process Updated Satellite Environmental Intelligence.
Samples remote authoritative COGs:
1. MODIS Aqua 2023 Summer LST (NASA LP DAAC)
2. Sentinel-2 2024 Pre-Monsoon NDVI (ESA/Copernicus)
3. ESA WorldCover 2021 Built-Up (ESA)
Saves processed indicators to data/processed/environmental/ and MongoDB urban_risk_db.
"""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.environmental_service import EnvironmentalService
from pymongo import MongoClient


def main():
    parser = argparse.ArgumentParser(
        description="Ingest and process updated satellite environmental indicators for Hyderabad."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and validate data without saving to MongoDB."
    )
    parser.add_argument(
        "--mongo-uri",
        type=str,
        default="mongodb://127.0.0.1:27017/",
        help="MongoDB connection URI"
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default="urban_risk_db",
        help="MongoDB database name"
    )
    args = parser.parse_args()

    print("======================================================================")
    print(" URBANRISK — SATELLITE ENVIRONMENTAL INTELLIGENCE INGESTION")
    print("======================================================================")

    service = EnvironmentalService()
    print("Starting remote satellite COG sampling across 791 1-km grid cells...")
    print("  - MODIS LST Day:   NASA LP DAAC / Planetary Computer (MYD11A2.061, Summer 2023)")
    print("  - Sentinel-2 NDVI: ESA / Copernicus via AWS Earth Search (April 2024)")
    print("  - ESA WorldCover:  ESA / Planetary Computer (2021 v200, 10m Built-up)")

    try:
        df = service.extract_satellite_indicators(save_csv=True)
        print(f"\n[SUCCESS] Extracted indicators for all {len(df)} cells:")
        valid_lst = df["modis_lst_day_2023_c"].dropna()
        valid_ndvi = df["sentinel2_ndvi_2024"].dropna()
        builtup_count = df["is_builtup_surface"].sum()

        print(f"  - MODIS LST Day 2023:  {len(valid_lst)} valid cells | Mean: {valid_lst.mean():.2f}°C (Min: {valid_lst.min():.2f}°C, Max: {valid_lst.max():.2f}°C)")
        print(f"  - Sentinel-2 NDVI 2024: {len(valid_ndvi)} valid cells | Mean: {valid_ndvi.mean():.3f} (Min: {valid_ndvi.min():.3f}, Max: {valid_ndvi.max():.3f})")
        print(f"  - ESA Built-Up 2021:   {builtup_count} core built-up cells ({builtup_count/len(df)*100:.1f}%)")
        print(f"  - Saved to CSV:        {service.output_csv_path}")

        if args.dry_run:
            print("\n[DRY RUN] Dry run enabled — MongoDB writes skipped.")
            return

        client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=3000)
        db = client[args.db_name]
        storage_res = service.persist_to_mongodb(df, db)

        print("\n[DATABASE PERSISTENCE]")
        print(f"  - Collection:          {storage_res['collection']}")
        print(f"  - Matched:             {storage_res['matched_count']}")
        print(f"  - Modified:            {storage_res['modified_count']}")
        print(f"  - Upserted:            {storage_res['upserted_count']}")
        print(f"  - Total Stored:        {storage_res['total_documents']}")
        print(f"  - Catalog Registered:  {storage_res['catalog_datasets_registered']}")
        print("\nSATELLITE ENVIRONMENTAL INTELLIGENCE INGESTION COMPLETED SUCCESSFULLY.")

    except Exception as e:
        print(f"\n[ERROR] Environmental ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
