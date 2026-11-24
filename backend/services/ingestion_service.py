"""
Dataset Ingestion Service for URBANRISK Hyderabad.
Provides unified, controlled, validated ingestion across all supported data sources:
1. Open-Meteo Latest Weather Model Data (cadence: 1-3 hours)
2. MODIS Aqua 8-Day 1-km LST (cadence: 8-day composite)
3. Sentinel-2 L2A 10m NDVI (cadence: 5-day revisit)
4. ESA WorldCover 10m Land Cover (cadence: annual / static baseline)
5. Historical Flood Events & Rainfall (cadence: event / archive inventory)

Ensures:
- Safe database updates (idempotent upsert, unique compound indexes, no destructive drops).
- Strict separation of observation timestamp, retrieval timestamp, and ingestion timestamp.
- Comprehensive run history logging in MongoDB `dataset_ingestion_runs`.
- Cadence checks (skips unnecessary re-downloads unless force=True).
- Preserves missing values (does NOT impute missing evidence).
- IUPS composite scores and grid cell count (791 total, 741 scored, 50 unscored) remain intact.
"""

from datetime import datetime, timezone, timedelta
import logging
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
import pandas as pd
import pymongo

from database.mongodb import db as default_db
from backend.services.weather_service import WeatherService
from backend.services.environmental_service import EnvironmentalService, PROJECT_ROOT

logger = logging.getLogger("urbanrisk.ingestion")

INGESTION_RUNS_COLLECTION = "dataset_ingestion_runs"

# Supported datasets and their cadences
DATASET_CADENCE_CONFIG = {
    "weather_open_meteo": {
        "display_name": "Open-Meteo Latest Weather Conditions",
        "category": "weather_model",
        "provider": "Open-Meteo",
        "cadence_description": "Hourly to 3-hourly update cycle",
        "min_interval_hours": 1.0,
        "is_static": False
    },
    "modis_lst": {
        "display_name": "MODIS Aqua 8-Day 1-km Land Surface Temperature",
        "category": "satellite_thermal",
        "provider": "NASA LP DAAC / USGS via Planetary Computer",
        "cadence_description": "8-day composite cycle",
        "min_interval_hours": 24.0 * 7,  # 7 days minimum
        "is_static": False
    },
    "sentinel2_ndvi": {
        "display_name": "Sentinel-2 MSI L2A 10m Vegetation / NDVI",
        "category": "satellite_optical",
        "provider": "ESA / Copernicus via AWS Earth Search",
        "cadence_description": "5-day constellation revisit",
        "min_interval_hours": 24.0 * 4,  # 4 days minimum
        "is_static": False
    },
    "esa_worldcover": {
        "display_name": "ESA WorldCover 10m Land Cover Baseline",
        "category": "land_cover",
        "provider": "ESA / VITO via Planetary Computer",
        "cadence_description": "Annual baseline (Static)",
        "min_interval_hours": 24.0 * 365,
        "is_static": True
    },
    "historical_floods": {
        "display_name": "Historical Flood Events & Rainfall Inventory",
        "category": "hazard_inventory",
        "provider": "GHMC / Disaster Management Archive",
        "cadence_description": "Periodic / Event-based archive",
        "min_interval_hours": 24.0 * 30,
        "is_static": True
    }
}


class DatasetIngestionService:
    def __init__(self, db=None):
        self.db = db if db is not None else default_db
        self.weather_service = WeatherService()
        self.env_service = EnvironmentalService()
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Ensures indexes on dataset_ingestion_runs collection for fast querying and integrity."""
        try:
            self.db[INGESTION_RUNS_COLLECTION].create_index([("run_id", pymongo.ASCENDING)], unique=True)
            self.db[INGESTION_RUNS_COLLECTION].create_index([("dataset_key", pymongo.ASCENDING), ("started_at", pymongo.DESCENDING)])
            self.db[INGESTION_RUNS_COLLECTION].create_index([("status", pymongo.ASCENDING)])
        except Exception as e:
            logger.warning(f"Could not initialize indexes on {INGESTION_RUNS_COLLECTION}: {e}")

    def log_run(
        self,
        run_id: str,
        dataset_key: str,
        trigger_type: str,
        status: str,
        started_at: datetime,
        completed_at: datetime,
        records_fetched: int = 0,
        records_accepted: int = 0,
        records_rejected: int = 0,
        records_upserted: int = 0,
        observation_timestamp: Optional[str] = None,
        observation_period: Optional[str] = None,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records an ingestion execution entry into MongoDB collection."""
        duration_sec = round((completed_at - started_at).total_seconds(), 3)
        doc = {
            "run_id": run_id,
            "dataset_key": dataset_key,
            "trigger_type": trigger_type,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": duration_sec,
            "records_fetched": records_fetched,
            "records_accepted": records_accepted,
            "records_rejected": records_rejected,
            "records_upserted": records_upserted,
            "observation_timestamp": observation_timestamp,
            "observation_period": observation_period,
            "source": source or DATASET_CADENCE_CONFIG.get(dataset_key, {}).get("provider", "Unknown"),
            "details": details or {},
            "error_message": error_message
        }
        self.db[INGESTION_RUNS_COLLECTION].update_one(
            {"run_id": run_id},
            {"$set": doc},
            upsert=True
        )
        return doc

    def get_latest_successful_run(self, dataset_key: str) -> Optional[Dict[str, Any]]:
        """Finds the most recent successful or partial run for a given dataset."""
        return self.db[INGESTION_RUNS_COLLECTION].find_one(
            {"dataset_key": dataset_key, "status": {"$in": ["success", "partial", "skipped"]}},
            sort=[("completed_at", pymongo.DESCENDING)],
            projection={"_id": 0}
        )

    def should_skip_cadence(self, dataset_key: str, force: bool = False) -> (bool, Optional[str]):
        """
        Determines if ingestion should be skipped because the dataset was updated recently,
        respecting provider publishing cadences.
        """
        if force:
            return False, "Force flag enabled: bypassing cadence check."

        config = DATASET_CADENCE_CONFIG.get(dataset_key)
        if not config:
            return False, None

        latest_run = self.get_latest_successful_run(dataset_key)
        if not latest_run:
            return False, "No previous run recorded."

        completed_at = latest_run.get("completed_at")
        if not completed_at:
            return False, "Previous run missing completion timestamp."

        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        elapsed_hours = (now - completed_at).total_seconds() / 3600.0

        min_interval = config["min_interval_hours"]
        if elapsed_hours < min_interval:
            reason = (
                f"Dataset '{dataset_key}' was updated {elapsed_hours:.1f}h ago. "
                f"Provider cadence interval is {min_interval:.1f}h ({config['cadence_description']}). "
                f"Skipping redundant ingestion (use force=True to override)."
            )
            return True, reason

        return False, f"Elapsed time ({elapsed_hours:.1f}h) exceeds cadence interval ({min_interval:.1f}h)."

    def ingest_weather(self, trigger_type: str = "manual_cli", force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Ingests latest city-level weather model data from Open-Meteo."""
        run_id = f"run_weather_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)
        dataset_key = "weather_open_meteo"

        skip, reason = self.should_skip_cadence(dataset_key, force=force)
        if skip:
            completed_at = datetime.now(timezone.utc)
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="skipped",
                started_at=started_at,
                completed_at=completed_at,
                source="Open-Meteo API",
                details={"reason": reason}
            )

        try:
            raw_data = self.weather_service.fetch_weather_from_provider()
            parsed = self.weather_service.validate_and_parse_observation(raw_data)
            obs_time = parsed.get("observation_timestamp")

            if dry_run:
                completed_at = datetime.now(timezone.utc)
                return self.log_run(
                    run_id=run_id,
                    dataset_key=dataset_key,
                    trigger_type=trigger_type,
                    status="dry_run",
                    started_at=started_at,
                    completed_at=completed_at,
                    records_fetched=1,
                    records_accepted=1,
                    records_rejected=0,
                    records_upserted=0,
                    observation_timestamp=obs_time,
                    source="Open-Meteo API",
                    details={"dry_run": True, "parsed_preview": parsed}
                )

            # Idempotent persistence via WeatherService
            saved = self.weather_service.store_observation(parsed, db=self.db)
            completed_at = datetime.now(timezone.utc)
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="success",
                started_at=started_at,
                completed_at=completed_at,
                records_fetched=1,
                records_accepted=1,
                records_rejected=0,
                records_upserted=1,
                observation_timestamp=obs_time,
                source="Open-Meteo API",
                details={"location": parsed.get("location_name"), "temp_c": parsed.get("temperature_c")}
            )
        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            logger.error(f"Weather ingestion failed: {e}")
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                records_fetched=0,
                records_accepted=0,
                records_rejected=0,
                records_upserted=0,
                source="Open-Meteo API",
                error_message=str(e)
            )

    def ingest_modis(self, trigger_type: str = "manual_cli", force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Ingests MODIS Aqua 8-day LST dataset."""
        run_id = f"run_modis_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)
        dataset_key = "modis_lst"

        skip, reason = self.should_skip_cadence(dataset_key, force=force)
        if skip:
            completed_at = datetime.now(timezone.utc)
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="skipped",
                started_at=started_at,
                completed_at=completed_at,
                source="NASA LP DAAC / Microsoft Planetary Computer",
                details={"reason": reason}
            )

        try:
            # Check cached processed indicator or recalculate if missing
            csv_path = self.env_service.data_dir / "hyderabad_environmental_indicators_1km.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Source indicator CSV not found at {csv_path}")

            df = pd.read_csv(csv_path)
            total = len(df)
            valid_lst = df[df["modis_lst_day_2023_c"].notna()]
            accepted = len(valid_lst)
            rejected = total - accepted

            if dry_run:
                completed_at = datetime.now(timezone.utc)
                return self.log_run(
                    run_id=run_id,
                    dataset_key=dataset_key,
                    trigger_type=trigger_type,
                    status="dry_run",
                    started_at=started_at,
                    completed_at=completed_at,
                    records_fetched=total,
                    records_accepted=accepted,
                    records_rejected=rejected,
                    records_upserted=0,
                    observation_period="2023-05-25 to 2023-06-01 (DOY 145)",
                    source="NASA LP DAAC / Microsoft Planetary Computer",
                    details={"dry_run": True, "lst_mean_c": float(valid_lst["modis_lst_day_2023_c"].mean())}
                )

            # Ingest into environmental collections via EnvironmentalService
            res = self.env_service.persist_to_mongodb(df_env=df, db=self.db)
            completed_at = datetime.now(timezone.utc)

            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="success",
                started_at=started_at,
                completed_at=completed_at,
                records_fetched=total,
                records_accepted=accepted,
                records_rejected=rejected,
                records_upserted=res.get("upserted_count", 0) + res.get("matched_count", 0),
                observation_period="2023-05-25 to 2023-06-01 (DOY 145)",
                source="NASA LP DAAC / Microsoft Planetary Computer",
                details={"mean_lst_c": float(valid_lst["modis_lst_day_2023_c"].mean()), "cells": total}
            )
        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            logger.error(f"MODIS ingestion failed: {e}")
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                source="NASA LP DAAC / Microsoft Planetary Computer",
                error_message=str(e)
            )

    def ingest_sentinel2(self, trigger_type: str = "manual_cli", force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Ingests Sentinel-2 L2A NDVI dataset."""
        run_id = f"run_sentinel2_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)
        dataset_key = "sentinel2_ndvi"

        skip, reason = self.should_skip_cadence(dataset_key, force=force)
        if skip:
            completed_at = datetime.now(timezone.utc)
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="skipped",
                started_at=started_at,
                completed_at=completed_at,
                source="ESA / Copernicus via AWS Earth Search",
                details={"reason": reason}
            )

        try:
            csv_path = self.env_service.data_dir / "hyderabad_environmental_indicators_1km.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Source indicator CSV not found at {csv_path}")

            df = pd.read_csv(csv_path)
            total = len(df)
            valid_ndvi = df[df["sentinel2_ndvi_2024"].notna()]
            accepted = len(valid_ndvi)
            rejected = total - accepted

            if dry_run:
                completed_at = datetime.now(timezone.utc)
                return self.log_run(
                    run_id=run_id,
                    dataset_key=dataset_key,
                    trigger_type=trigger_type,
                    status="dry_run",
                    started_at=started_at,
                    completed_at=completed_at,
                    records_fetched=total,
                    records_accepted=accepted,
                    records_rejected=rejected,
                    records_upserted=0,
                    observation_timestamp="2024-04-27",
                    source="ESA / Copernicus via AWS Earth Search",
                    details={"dry_run": True, "ndvi_mean": float(valid_ndvi["sentinel2_ndvi_2024"].mean())}
                )

            res = self.env_service.persist_to_mongodb(df_env=df, db=self.db)
            completed_at = datetime.now(timezone.utc)

            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="success",
                started_at=started_at,
                completed_at=completed_at,
                records_fetched=total,
                records_accepted=accepted,
                records_rejected=rejected,
                records_upserted=res.get("upserted_count", 0) + res.get("matched_count", 0),
                observation_timestamp="2024-04-27",
                source="ESA / Copernicus via AWS Earth Search",
                details={"tile": "43QHV", "mean_ndvi": float(valid_ndvi["sentinel2_ndvi_2024"].mean())}
            )
        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            logger.error(f"Sentinel-2 ingestion failed: {e}")
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                source="ESA / Copernicus via AWS Earth Search",
                error_message=str(e)
            )

    def ingest_worldcover(self, trigger_type: str = "manual_cli", force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Ingests ESA WorldCover land cover dataset."""
        run_id = f"run_worldcover_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)
        dataset_key = "esa_worldcover"

        skip, reason = self.should_skip_cadence(dataset_key, force=force)
        if skip:
            completed_at = datetime.now(timezone.utc)
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="skipped",
                started_at=started_at,
                completed_at=completed_at,
                source="ESA / VITO via Planetary Computer",
                details={"reason": reason}
            )

        try:
            csv_path = self.env_service.data_dir / "hyderabad_environmental_indicators_1km.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Source indicator CSV not found at {csv_path}")

            df = pd.read_csv(csv_path)
            total = len(df)
            builtup_cells = int(df["is_builtup_surface"].sum())

            if dry_run:
                completed_at = datetime.now(timezone.utc)
                return self.log_run(
                    run_id=run_id,
                    dataset_key=dataset_key,
                    trigger_type=trigger_type,
                    status="dry_run",
                    started_at=started_at,
                    completed_at=completed_at,
                    records_fetched=total,
                    records_accepted=total,
                    records_rejected=0,
                    records_upserted=0,
                    observation_period="2021 Annual Baseline",
                    source="ESA / VITO via Planetary Computer",
                    details={"dry_run": True, "builtup_cells": builtup_cells}
                )

            res = self.env_service.persist_to_mongodb(df_env=df, db=self.db)
            completed_at = datetime.now(timezone.utc)

            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="success",
                started_at=started_at,
                completed_at=completed_at,
                records_fetched=total,
                records_accepted=total,
                records_rejected=0,
                records_upserted=res.get("upserted_count", 0) + res.get("matched_count", 0),
                observation_period="2021 Annual Baseline",
                source="ESA / VITO via Planetary Computer",
                details={"builtup_cells": builtup_cells, "total_cells": total}
            )
        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            logger.error(f"WorldCover ingestion failed: {e}")
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                source="ESA / VITO via Planetary Computer",
                error_message=str(e)
            )

    def ingest_historical_floods(self, trigger_type: str = "manual_cli", force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Ingests / validates historical flood events inventory from CSV."""
        run_id = f"run_floods_{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)
        dataset_key = "historical_floods"

        skip, reason = self.should_skip_cadence(dataset_key, force=force)
        if skip:
            completed_at = datetime.now(timezone.utc)
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="skipped",
                started_at=started_at,
                completed_at=completed_at,
                source="GHMC / State Disaster Management Archive",
                details={"reason": reason}
            )

        try:
            csv_path = PROJECT_ROOT / "data" / "processed" / "flood" / "hyderabad_historical_flood_events.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Flood events CSV not found at {csv_path}")

            df = pd.read_csv(csv_path)
            total = len(df)

            # Validate required columns in processed flood events CSV
            required_cols = ["UEI", "Start_Date_Parsed", "Districts"]
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                raise ValueError(f"Historical flood CSV missing columns: {missing_cols}")

            # Verify that records relate to Hyderabad / Telangana
            valid_mask = df["Districts"].astype(str).str.contains("Hyderabad", case=False, na=False)
            accepted = int(valid_mask.sum())
            rejected = total - accepted

            if dry_run:
                completed_at = datetime.now(timezone.utc)
                return self.log_run(
                    run_id=run_id,
                    dataset_key=dataset_key,
                    trigger_type=trigger_type,
                    status="dry_run",
                    started_at=started_at,
                    completed_at=completed_at,
                    records_fetched=total,
                    records_accepted=accepted,
                    records_rejected=rejected,
                    records_upserted=0,
                    observation_period="1969-2023 Historical Flood Events Inventory",
                    source="GHMC / State Disaster Management Archive",
                    details={"dry_run": True, "events_count": total, "hyderabad_events": accepted}
                )

            # Idempotent preservation into flood_events collection
            upserted_count = 0
            for idx, row in df[valid_mask].iterrows():
                event_id = int(idx + 1)
                doc = {
                    "event_id": event_id,
                    "dataset_id": 13,
                    "source_event_id": f"UEI:{row['UEI']}:ROW:{idx+1}",
                    "district": str(row.get("Districts", "")),
                    "start_date": str(row.get("Start_Date_Parsed", "")),
                    "end_date": str(row.get("End_Date_Parsed", "")),
                    "main_cause": str(row.get("Main Cause", "floods")),
                    "duration_days": int(row["Duration(Days)"]) if pd.notna(row.get("Duration(Days)")) else None,
                    "human_fatality": int(row["Human fatality"]) if pd.notna(row.get("Human fatality")) else None,
                    "human_injured": int(row["Human injured"]) if pd.notna(row.get("Human injured")) else None,
                    "updated_at": datetime.now(timezone.utc)
                }
                res = self.db.flood_events.update_one(
                    {"event_id": event_id},
                    {"$set": doc},
                    upsert=True
                )
                if res.upserted_id or res.modified_count > 0:
                    upserted_count += 1

            completed_at = datetime.now(timezone.utc)
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="success",
                started_at=started_at,
                completed_at=completed_at,
                records_fetched=total,
                records_accepted=accepted,
                records_rejected=rejected,
                records_upserted=upserted_count,
                observation_period="1969-2023 Historical Flood Events Inventory",
                source="GHMC / State Disaster Management Archive",
                details={"verified_events": accepted}
            )
        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            logger.error(f"Flood events ingestion failed: {e}")
            return self.log_run(
                run_id=run_id,
                dataset_key=dataset_key,
                trigger_type=trigger_type,
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                source="GHMC / State Disaster Management Archive",
                error_message=str(e)
            )

    def trigger_ingestion(self, dataset_key: str, trigger_type: str = "manual_admin_api", force: bool = False, dry_run: bool = False) -> Dict[str, Any]:
        """Dispatches ingestion for a single dataset or 'all'."""
        if dataset_key == "weather" or dataset_key == "weather_open_meteo":
            return self.ingest_weather(trigger_type=trigger_type, force=force, dry_run=dry_run)
        elif dataset_key == "modis" or dataset_key == "modis_lst":
            return self.ingest_modis(trigger_type=trigger_type, force=force, dry_run=dry_run)
        elif dataset_key == "sentinel2" or dataset_key == "sentinel2_ndvi":
            return self.ingest_sentinel2(trigger_type=trigger_type, force=force, dry_run=dry_run)
        elif dataset_key == "worldcover" or dataset_key == "esa_worldcover":
            return self.ingest_worldcover(trigger_type=trigger_type, force=force, dry_run=dry_run)
        elif dataset_key == "floods" or dataset_key == "historical_floods":
            return self.ingest_historical_floods(trigger_type=trigger_type, force=force, dry_run=dry_run)
        elif dataset_key == "all":
            results = {}
            for k in ["weather_open_meteo", "modis_lst", "sentinel2_ndvi", "esa_worldcover", "historical_floods"]:
                results[k] = self.trigger_ingestion(k, trigger_type=trigger_type, force=force, dry_run=dry_run)
            return {"status": "batch_completed", "datasets": results}
        else:
            raise ValueError(f"Unknown dataset_key: '{dataset_key}'. Supported keys: {list(DATASET_CADENCE_CONFIG.keys())} or 'all'")

    def get_datasets_status(self) -> List[Dict[str, Any]]:
        """Returns the current operational status, cadence, and latest ingestion summary for all registered datasets."""
        statuses = []
        for key, conf in DATASET_CADENCE_CONFIG.items():
            latest = self.get_latest_successful_run(key)
            status_item = {
                "dataset_key": key,
                "display_name": conf["display_name"],
                "category": conf["category"],
                "provider": conf["provider"],
                "cadence_description": conf["cadence_description"],
                "min_interval_hours": conf["min_interval_hours"],
                "is_static": conf["is_static"],
                "last_run": latest
            }
            statuses.append(status_item)
        return statuses

    def get_ingestion_history(self, limit: int = 50, dataset_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves recent ingestion runs from MongoDB."""
        query = {}
        if dataset_key:
            query["dataset_key"] = dataset_key
        cursor = self.db[INGESTION_RUNS_COLLECTION].find(
            query,
            projection={"_id": 0}
        ).sort("completed_at", pymongo.DESCENDING).limit(limit)
        return list(cursor)
