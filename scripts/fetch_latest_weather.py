"""
Administrative CLI Script: Fetch and Store Latest Weather Observations.
Controlled manual update command for URBANRISK Hyderabad.
"""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.weather_service import WeatherService
from pymongo import MongoClient


def main():
    parser = argparse.ArgumentParser(
        description="Fetch latest weather observations for Hyderabad and store in MongoDB."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and validate weather data without saving to MongoDB."
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
    print(" URBANRISK — CONTROLLED WEATHER UPDATE (OPEN-METEO MODEL DATA)")
    print("======================================================================")

    service = WeatherService()
    print(f"Connecting to Open-Meteo for coordinates ({service.latitude}°N, {service.longitude}°E)...")

    try:
        raw_data = service.fetch_weather_from_provider()
        doc = service.validate_and_parse_observation(raw_data)
        print("  [SUCCESS] Successfully fetched and validated model-based weather data:")
        print(f"    - Model Time:        {doc['observation_time']}")
        print(f"    - Temperature:       {doc['temperature_c']} °C")
        print(f"    - Relative Humidity: {doc['relative_humidity_pct']} %")
        print(f"    - Recent Precip:     {doc['precipitation_mm']} mm (Preceding {doc['precipitation_accumulation_interval_minutes']}-min interval)")
        print(f"    - Rain:              {doc['rain_mm']} mm")
        print(f"    - Wind Speed:        {doc['wind_speed_kmh']} km/h")
        print(f"    - Condition:         {doc['weather_icon']} {doc['weather_condition']} (Code: {doc['weather_code']})")
        print(f"    - Data Type:         {doc['data_type']} ({doc['data_source_type']})")
        print(f"    - Attribution:       {doc['attribution']}")

        if args.dry_run:
            print("\n[DRY RUN] Dry run mode enabled — no database writes executed.")
            return

        client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=3000)
        db = client[args.db_name]
        storage_res = service.store_observation(doc, db=db)

        print("\n  [DATABASE PERSISTENCE]")
        print(f"    - Upserted New:      {storage_res['upserted']}")
        print(f"    - Matched Count:     {storage_res['matched_count']}")
        print(f"    - Modified Count:    {storage_res['modified_count']}")
        print(f"    - Total Stored:      {storage_res['total_stored_observations']}")
        print("\nWEATHER OBSERVATION STORED SUCCESSFULLY.")

    except Exception as e:
        print(f"\n[ERROR] Weather update failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
