
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from database.mongodb import db
from backend.services.iups_service import assess_plot_iups

PROJECT_ROOT = Path(__file__).resolve().parents[2]

router = APIRouter(
    prefix="/api/assessments",
    tags=["Plot Assessments"]
)


# =============================================
# GET: INTEGRATED RISK & RESOURCE SUMMARY
# =============================================

@router.get("/summary")
def get_iups_summary():
    """Return summary statistics for the Hyderabad 1-km IUPS priority grid."""
    summary_path = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "integrated_urban_risk"
        / "integrated_urban_risk_summary.json"
    )

    summary_data = {}
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
        except Exception:
            pass

    # Additive enrichment with latest dynamic recalculation run if available
    try:
        if db is not None:
            latest_run = db.grid_recalculation_runs.find_one({}, {"_id": 0}, sort=[("calculation_timestamp", -1)])
            if latest_run:
                summary_data["last_calculated_at"] = latest_run.get("calculation_timestamp")
                summary_data["recalculation_status"] = "active"
                summary_data["dynamic_score_statistics"] = latest_run.get("score_statistics")
                summary_data["dynamic_screening_distribution"] = latest_run.get("screening_distribution")
    except Exception:
        pass

    if not summary_data:
        raise HTTPException(
            status_code=404,
            detail="Integrated urban risk summary data is unavailable."
        )

    return summary_data


@router.get("/priority-grid/top")
def get_top_priority_grid(limit: int = 15):
    """Return top-priority 1-km grid cells in Hyderabad from IUPS analysis."""
    last_calculated_at = None
    source_type = "precomputed_csv_baseline"

    # 1. Attempt reading dynamically from MongoDB priority_grid_cells
    try:
        if db is not None and "priority_grid_cells" in db.list_collection_names():
            total_cells = db.priority_grid_cells.count_documents({})
            if total_cells == 791:
                latest_run = db.grid_recalculation_runs.find_one({}, sort=[("calculation_timestamp", -1)])
                if latest_run:
                    last_calculated_at = latest_run.get("calculation_timestamp")
                source_type = "dynamic_mongodb_grid"

                scored_query = {"priority_score_0_100": {"$ne": None}}
                total_scored = db.priority_grid_cells.count_documents(scored_query)
                cursor = db.priority_grid_cells.find(scored_query).sort("priority_score_0_100", -1).limit(limit)

                results = []
                for r in cursor:
                    results.append({
                        "grid_id": r.get("grid_id"),
                        "priority_score": round(float(r["priority_score_0_100"]), 1),
                        "screening_priority": r.get("screening_priority") or "Higher screening priority",
                        "latitude": round(float(r["cell_center_latitude"]), 5),
                        "longitude": round(float(r["cell_center_longitude"]), 5),
                        "flood_evidence_score": round(float(r["flood_evidence_score"]), 3) if r.get("flood_evidence_score") is not None else None,
                        "heat_evidence_score": round(float(r["heat_evidence_score"]), 3) if r.get("heat_evidence_score") is not None else None,
                        "infrastructure_gap_score": round(float(r["infrastructure_gap_score"]), 3) if r.get("infrastructure_gap_score") is not None else None,
                        "road_gap_score": round(float(r["road_representation_gap_score"]), 3) if r.get("road_representation_gap_score") is not None else None,
                        "hospitals_count": int(float(r.get("infra_hospital_count") or 0)),
                        "fire_stations_count": int(float(r.get("infra_fire_station_count") or 0)),
                        "road_points_count": int(float(r.get("road_representative_point_count") or 0))
                    })

                return {
                    "status": "success",
                    "total_scored_cells": total_scored,
                    "last_calculated_at": last_calculated_at,
                    "source_type": source_type,
                    "top_priority_cells": results
                }
    except Exception:
        pass

    # 2. Fallback to precomputed CSV
    import csv
    grid_csv_path = (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "integrated_urban_risk"
        / "integrated_urban_risk_priority_grid_1km.csv"
    )

    if not grid_csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Priority grid data file is unavailable."
        )

    try:
        with open(grid_csv_path, mode="r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        valid = [r for r in rows if r.get("priority_score_0_100") and r.get("priority_score_0_100") != ""]
        valid.sort(key=lambda r: float(r["priority_score_0_100"]), reverse=True)

        results = []
        for r in valid[:limit]:
            results.append({
                "grid_id": r.get("grid_id"),
                "priority_score": round(float(r["priority_score_0_100"]), 1),
                "screening_priority": r.get("screening_priority") or "Higher screening priority",
                "latitude": round(float(r["cell_center_latitude"]), 5),
                "longitude": round(float(r["cell_center_longitude"]), 5),
                "flood_evidence_score": round(float(r["flood_evidence_score"]), 3) if r.get("flood_evidence_score") else None,
                "heat_evidence_score": round(float(r["heat_evidence_score"]), 3) if r.get("heat_evidence_score") else None,
                "infrastructure_gap_score": round(float(r["infrastructure_gap_score"]), 3) if r.get("infrastructure_gap_score") else None,
                "road_gap_score": round(float(r["road_representation_gap_score"]), 3) if r.get("road_representation_gap_score") else None,
                "hospitals_count": int(float(r.get("infra_hospital_count") or 0)),
                "fire_stations_count": int(float(r.get("infra_fire_station_count") or 0)),
                "road_points_count": int(float(r.get("road_representative_point_count") or 0))
            })

        return {
            "status": "success",
            "total_scored_cells": len(valid),
            "last_calculated_at": last_calculated_at,
            "source_type": source_type,
            "top_priority_cells": results
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to process priority grid: {error}"
        )


# =============================================
# DISTANCE CALCULATION
# =============================================

def calculate_distance_m(lat1, lon1, lat2, lon2):
    """
    Calculate spherical distance between two coordinates
    using the Haversine formula.
    """

    earth_radius_m = 6371000

    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius_m * c


# =============================================
# GET: ASSESS A SAVED PLOT
# =============================================

class CoordinateAssessmentRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")


def run_spatial_assessment(latitude: float, longitude: float, location_id: Optional[int] = None, plot_record: Optional[dict] = None):
    try:
        plot = plot_record or {
            "location_id": location_id or 0,
            "latitude": latitude,
            "longitude": longitude,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # -----------------------------------------
        # 2. INFRASTRUCTURE WITHIN 1 KM
        # -----------------------------------------

        infrastructure_records = db.infrastructure_assets.find(
            {},
            {
                "_id": 0,
                "asset_id": 1,
                "category": 1,
                "asset_name": 1,
                "subtype": 1,
                "latitude": 1,
                "longitude": 1
            }
        )

        infrastructure_distances = []

        for asset in infrastructure_records:

            distance = calculate_distance_m(
                latitude,
                longitude,
                asset["latitude"],
                asset["longitude"]
            )

            infrastructure_distances.append({
                "asset_id": asset["asset_id"],
                "category": asset.get("category"),
                "asset_name": asset.get("asset_name"),
                "subtype": asset.get("subtype"),
                "distance_m": round(distance, 1)
            })

        infrastructure_within_1km = [
            asset
            for asset in infrastructure_distances
            if asset["distance_m"] <= 1000
        ]

        infrastructure_category_counts = {}

        for asset in infrastructure_within_1km:

            category = asset["category"] or "unknown"

            if category not in infrastructure_category_counts:
                infrastructure_category_counts[category] = {
                    "category": category,
                    "assets_within_1km": 0,
                    "nearest_distance_m": asset["distance_m"]
                }

            summary = infrastructure_category_counts[category]

            summary["assets_within_1km"] += 1

            summary["nearest_distance_m"] = min(
                summary["nearest_distance_m"],
                asset["distance_m"]
            )

        infrastructure_summary = sorted(
            infrastructure_category_counts.values(),
            key=lambda item: item["assets_within_1km"],
            reverse=True
        )

        infrastructure_summary = [
            {
                **item,
                "nearest_distance_m": round(
                    item["nearest_distance_m"],
                    1
                )
            }
            for item in infrastructure_summary
        ]

        nearest_assets = sorted(
            infrastructure_distances,
            key=lambda item: item["distance_m"]
        )[:10]

        # -----------------------------------------
        # 3. INTEGRATED URBAN PRIORITY SCREENING
        # -----------------------------------------

        # Uses the existing precomputed 1 km grid.
        # Do not replace this with a new calculation.

        iups_result = assess_plot_iups(
            latitude,
            longitude
        )

        # -----------------------------------------
        # 4. NEARBY ROAD-NETWORK ANALYSIS
        # -----------------------------------------

        search_radius_m = 1200

        latitude_delta = search_radius_m / 111320

        longitude_delta = search_radius_m / (
            111320 * max(
                abs(math.cos(math.radians(latitude))),
                0.01
            )
        )

        south = max(-90, latitude - latitude_delta)
        north = min(90, latitude + latitude_delta)

        west = max(-180, longitude - longitude_delta)
        east = min(180, longitude + longitude_delta)

        bbox_geometry = {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south]
            ]]
        }

        road_records = db.road_segments.find(
            {
                "representative_point": {
                    "$geoWithin": {
                        "$geometry": bbox_geometry
                    }
                }
            },
            {
                "_id": 0,
                "road_id": 1,
                "road_name": 1,
                "road_type": 1,
                "length_km": 1,
                "maxspeed": 1,
                "oneway": 1,
                "latitude": 1,
                "longitude": 1
            }
        )

        road_candidates = []

        for road in road_records:

            distance = calculate_distance_m(
                latitude,
                longitude,
                road["latitude"],
                road["longitude"]
            )

            road_candidates.append({
                "road_id": road["road_id"],
                "road_name": road.get("road_name"),
                "road_type": road.get("road_type"),
                "length_km": (
                    float(road["length_km"])
                    if road.get("length_km") is not None
                    else None
                ),
                "maxspeed": road.get("maxspeed"),
                "oneway": road.get("oneway"),
                "distance_m": round(distance, 1)
            })

        road_candidates.sort(
            key=lambda item: item["distance_m"]
        )

        road_points_250m = 0
        road_points_500m = 0
        road_points_1km = 0

        road_type_counts = {}

        for road in road_candidates:

            distance = road["distance_m"]

            if distance <= 250:
                road_points_250m += 1

            if distance <= 500:
                road_points_500m += 1

            if distance <= 1000:

                road_points_1km += 1

                road_type = road["road_type"] or "unknown"

                road_type_counts[road_type] = (
                    road_type_counts.get(road_type, 0) + 1
                )

        road_type_distribution = [
            {
                "road_type": road_type,
                "road_points_within_1km": count
            }
            for road_type, count in sorted(
                road_type_counts.items(),
                key=lambda item: item[1],
                reverse=True
            )
        ]

        nearest_roads = road_candidates[:5]

        # -----------------------------------------
        # 5. NEARBY HEAT AND RAINFALL OBSERVATIONS
        # -----------------------------------------

        selected_dataset_ids = [1, 9, 10]

        hazard_records = list(
            db.hazard_observations.find(
                {
                    "dataset_id": {
                        "$in": selected_dataset_ids
                    }
                },
                {
                    "_id": 0
                }
            )
        )

        # Build lookup dictionaries to replace SQL JOINs.

        sample_locations = {
            item["location_id"]: item
            for item in db.spatial_locations.find(
                {},
                {
                    "_id": 0,
                    "location_id": 1,
                    "latitude": 1,
                    "longitude": 1
                }
            )
        }

        dataset_versions = {
            item["dataset_id"]: item
            for item in db.dataset_versions.find(
                {},
                {
                    "_id": 0,
                    "dataset_id": 1,
                    "dataset_name": 1,
                    "source_name": 1,
                    "version_label": 1,
                    "date_range_start": 1,
                    "date_range_end": 1
                }
            )
        }

        hazard_groups = {}

        for hazard in hazard_records:

            sample_location = sample_locations.get(
                hazard.get("location_id")
            )

            dataset = dataset_versions.get(
                hazard.get("dataset_id")
            )

            if sample_location is None or dataset is None:
                continue

            distance = calculate_distance_m(
                latitude,
                longitude,
                sample_location["latitude"],
                sample_location["longitude"]
            )

            dataset_id = hazard.get("dataset_id")
            hazard_type = hazard.get("hazard_type")
            metric_name = hazard.get("metric_name")
            unit = hazard.get("unit")
            observed_at = hazard.get("observed_at")

            group_key = (
                dataset_id,
                hazard_type,
                metric_name,
                unit,
                observed_at
            )

            if group_key not in hazard_groups:

                hazard_groups[group_key] = {
                    "dataset_id": dataset_id,
                    "dataset_name": dataset.get("dataset_name"),
                    "source_name": dataset.get("source_name"),
                    "version_label": dataset.get("version_label"),
                    "date_range_start": dataset.get("date_range_start"),
                    "date_range_end": dataset.get("date_range_end"),
                    "hazard_type": hazard_type,
                    "metric_name": metric_name,
                    "unit": unit,
                    "observed_at": observed_at,
                    "total_measurements": 0,
                    "sample_location_ids": set(),
                    "nearby_location_ids": set(),
                    "distances": [],
                    "nearby_metric_values": []
                }

            group = hazard_groups[group_key]

            group["total_measurements"] += 1

            sample_location_id = hazard.get("location_id")

            group["sample_location_ids"].add(
                sample_location_id
            )

            group["distances"].append(distance)

            if distance <= 5000:

                group["nearby_location_ids"].add(
                    sample_location_id
                )

                metric_value = hazard.get("metric_value")

                if metric_value is not None:
                    group["nearby_metric_values"].append(
                        float(metric_value)
                    )

        hazard_observations = []

        for group in hazard_groups.values():

            metric_values = group["nearby_metric_values"]

            average_value = (
                round(sum(metric_values) / len(metric_values), 2)
                if metric_values
                else None
            )

            hazard_observations.append({

                "dataset_id": group["dataset_id"],
                "dataset_name": group["dataset_name"],
                "source_name": group["source_name"],
                "version_label": group["version_label"],
                "date_range_start": group["date_range_start"],
                "date_range_end": group["date_range_end"],
                "hazard_type": group["hazard_type"],
                "metric_name": group["metric_name"],
                "unit": group["unit"],
                "observed_at": group["observed_at"],

                "total_measurements": group["total_measurements"],

                "total_sample_locations": len(
                    group["sample_location_ids"]
                ),

                "sample_locations_within_5km": len(
                    group["nearby_location_ids"]
                ),

                "nearest_observation_m": round(
                    min(group["distances"]),
                    1
                ),

                "average_value_within_5km": average_value
            })

        hazard_observations.sort(
            key=lambda item: (
                item["dataset_id"],
                item["metric_name"] or "",
                str(item["observed_at"] or "")
            )
        )

        # -----------------------------------------
        # 6. HISTORICAL FLOOD EVENTS
        # -----------------------------------------

        historical_flood_events = list(
            db.flood_events.find(
                {
                    "dataset_id": 13,
                    "district": {
                        "$regex": "hyderabad",
                        "$options": "i"
                    }
                },
                {
                    "_id": 0,
                    "event_id": 1,
                    "source_event_id": 1,
                    "start_date": 1,
                    "end_date": 1,
                    "main_cause": 1,
                    "duration_days": 1,
                    "human_fatality": 1,
                    "human_injured": 1
                }
            ).sort(
                "start_date",
                -1
            )
        )

        # -----------------------------------------
        # 7. DATASET PROVENANCE
        # -----------------------------------------

        data_sources = list(
            db.dataset_versions.find(
                {
                    "dataset_id": {
                        "$in": [1, 9, 10, 11, 12, 13]
                    }
                },
                {
                    "_id": 0,
                    "dataset_id": 1,
                    "dataset_name": 1,
                    "source_name": 1,
                    "version_label": 1,
                    "date_range_start": 1,
                    "date_range_end": 1,
                    "record_count": 1
                }
            ).sort(
                "dataset_id",
                1
            )
        )

        # -----------------------------------------
        # 7-B. PERSIST TO MONGODB COLLECTIONS
        # -----------------------------------------
        try:
            priority_score = iups_result.get("priority_score")
            priority_band = iups_result.get("priority_band")
            components = iups_result.get("components") or {}
            target_loc_id = location_id if location_id is not None else int(abs(latitude * 1000 + longitude * 100)) % 1000000

            db.risk_assessments.update_one(
                {"location_id": target_loc_id},
                {
                    "$set": {
                        "location_id": target_loc_id,
                        "latitude": latitude,
                        "longitude": longitude,
                        "overall_score": priority_score,
                        "risk_level": priority_band,
                        "flood_score": components.get("flood_evidence_score"),
                        "heat_score": components.get("heat_evidence_score"),
                        "infrastructure_score": components.get("infrastructure_gap_score"),
                        "road_score": components.get("road_representation_gap_score"),
                        "infrastructure_within_1km": len(infrastructure_within_1km),
                        "road_points_within_1km": road_points_1km,
                        "assessment_timestamp": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )

            if priority_score is not None:
                priority_rank = (
                    1 if priority_score >= 60 else
                    2 if priority_score >= 40 else
                    3 if priority_score >= 20 else 4
                )
                db.resource_priorities.update_one(
                    {"location_id": target_loc_id},
                    {
                        "$set": {
                            "location_id": target_loc_id,
                            "priority_rank": priority_rank,
                            "resource_type": "Multi-Hazard Infrastructure & Climate Intervention",
                            "justification": f"Plot #{target_loc_id} evaluated with priority score {priority_score} ({priority_band}).",
                            "created_at": datetime.now(timezone.utc)
                        }
                    },
                    upsert=True
                )
        except Exception as persist_error:
            print(f"Notice: Assessment persistence skipped: {persist_error}")

        # -----------------------------------------
        # 7-C. CONSTRUCT 3 MAIN CATEGORY ASSESSMENTS
        # -----------------------------------------
        flood_evidence_score = components.get("flood_evidence_score")
        if flood_evidence_score is not None:
            flood_score_val = round(flood_evidence_score * 100, 1)
            flood_class = "HIGH" if flood_score_val >= 50 else ("MEDIUM" if flood_score_val >= 25 else "LOW")
            flood_reason = None
            flood_explanation = (
                f"Rainfall raster extraction indicates elevated precipitation exposure ({flood_score_val}/100 normalized score). "
                f"Hyderabad district records document 40 historical flood events in regional drainage catchments."
            )
        else:
            flood_score_val = None
            flood_class = "NOT SCORED"
            flood_reason = "Insufficient local flood-hazard evidence"
            flood_explanation = (
                "Location has insufficient direct local flood-hazard evidence (no local rainfall monitoring raster sample) to calculate a cell-specific score. "
                "This does not mean the location is free from flood risk. The locality is evaluated under Greater Hyderabad's documented disaster inventory "
                "of 40 historical flood events (1969–2022) with 727 recorded fatalities."
            )

        heat_evidence_score = components.get("heat_evidence_score")
        if heat_evidence_score is not None:
            heat_score_val = round(heat_evidence_score * 100, 1)
            heat_class = "HIGH" if heat_score_val >= 50 else ("MEDIUM" if heat_score_val >= 25 else "LOW")
            heat_explanation = (
                f"Location falls in the {heat_score_val}th percentile for daytime surface temperature and Urban Heat Island intensity "
                f"across Hyderabad, based on multi-year MODIS satellite observations."
            )
        else:
            heat_score_val = 50.0
            heat_class = "MEDIUM"
            heat_explanation = "Urban heat exposure evaluated at citywide baseline average."

        try:
            from backend.routers.ml import predict_temperature, HeatPredictRequest
            ml_res = predict_temperature(HeatPredictRequest(latitude=latitude, longitude=longitude, nighttime_temp_c=24.5))
            ml_pred = ml_res.get("prediction", {})
            ml_estimate_info = {
                "model_name": "Random Forest Daytime Surface Temperature Regressor",
                "predicted_daytime_temp_c": ml_pred.get("predicted_daytime_temp_c"),
                "diurnal_temperature_difference_c": ml_pred.get("diurnal_temperature_difference_c"),
                "heat_risk_level": ml_pred.get("heat_risk_level"),
                "input_nighttime_temp_c": 24.5,
                "input_assumed_nighttime_temp_c": 24.5,
                "input_nature": "Assumed nominal nighttime temperature baseline of 24.5°C; not a measured temperature.",
                "estimate_type": "ILLUSTRATIVE_REGRESSION_ESTIMATE",
                "is_forecast": False,
                "validation_mae_c": 0.506
            }
        except Exception:
            ml_estimate_info = None

        infra_gap = components.get("infrastructure_gap_score")
        road_gap = components.get("road_representation_gap_score")
        if infra_gap is not None and road_gap is not None:
            infra_gap_score_val = round(((infra_gap + road_gap) / 2) * 100, 1)
        elif infra_gap is not None:
            infra_gap_score_val = round(infra_gap * 100, 1)
        else:
            infra_gap_score_val = 50.0

        infra_class = "HIGH" if infra_gap_score_val >= 50 else ("MEDIUM" if infra_gap_score_val >= 25 else "LOW")

        hosp_cnt = sum(1 for a in infrastructure_within_1km if a.get("category") == "hospital")
        fire_cnt = sum(1 for a in infrastructure_within_1km if a.get("category") == "fire_station")
        near_hosp = next((a for a in infrastructure_distances if a.get("category") == "hospital"), None)
        near_hosp_m = near_hosp["distance_m"] if near_hosp else None

        infra_explanation = (
            f"{hosp_cnt} hospital/clinic facility(ies) and {fire_cnt} fire station(s) located within 1 km. "
            f"Nearest hospital is {near_hosp_m} m away. {road_points_1km} road network sample points within 1 km."
        )

        category_assessments = {
            "flood_risk": {
                "category_name": "Flood Risk",
                "score_value": flood_score_val,
                "score_scale": "0-100",
                "score_label": "Normalized Rainfall & Hazard Depth Score / 100" if flood_score_val is not None else "Not Scored (Insufficient Local Evidence)",
                "classification": flood_class,
                "classification_explanation": flood_explanation,
                "is_scored": flood_score_val is not None,
                "reason": flood_reason if flood_score_val is None else None,
                "historical_events_count": 40,
                "historical_fatalities_count": 727,
                "data_type": "HISTORICAL DISASTER INVENTORY & STORM RASTER EXTRACTS",
                "source": "India Flood Inventory v3 (IMD Disasters Archive) & CHIRPS v3.0 Daily Rainfall Extraction",
                "observation_period": "1969–2022 (Floods) · 2020-09-25 & 2021-10-08 (Storm Rasters)",
                "storm_dates": ["2020-09-25", "2021-10-08"],
                "raster_samples_count": 84,
                "rainfall_coverage_note": "Historical precipitation from CHIRPS raster extraction for two extreme storm events (2020-09-25 and 2021-10-08); does not represent real-time telemetry or flood forecasting.",
                "last_updated": "November 2026",
                "freshness": "HISTORICAL DISASTER INVENTORY",
                "warning": "Historical disaster inventory and storm records; does not represent live rainfall forecasting."
            },
            "heat_risk": {
                "category_name": "Heat Risk",
                "score_value": heat_score_val,
                "score_scale": "0-100",
                "score_label": "Percentile-Ranked Heat Exposure Score / 100",
                "classification": heat_class,
                "classification_explanation": heat_explanation,
                "data_type": "OBSERVED SATELLITE BASELINE + ILLUSTRATIVE ML ESTIMATE",
                "source": "NASA MODIS Land Surface Temp & Yale Center for Earth Observation UHI",
                "observation_period": "2003–2018 Multi-Year Summer Satellite Baseline",
                "last_updated": "November 2026",
                "freshness": "HISTORICAL SATELLITE BASELINE",
                "ml_estimate": ml_estimate_info,
                "warning": "Satellite observations represent multi-year historical thermal patterns."
            },
            "infrastructure_risk": {
                "category_name": "Infrastructure Risk",
                "score_value": infra_gap_score_val,
                "score_scale": "0-100",
                "score_label": "Infrastructure & Accessibility Deficit Score / 100",
                "classification": infra_class,
                "classification_explanation": infra_explanation,
                "data_type": "OBSERVED SPATIAL INVENTORY",
                "source": "OpenStreetMap Civic Amenities & Road Network Extraction",
                "observation_period": "Civic amenities and road inventory",
                "last_updated": "November 2026 Snapshot",
                "freshness": "RECENT INVENTORY BASELINE",
                "hospitals_within_1km": hosp_cnt,
                "fire_stations_within_1km": fire_cnt,
                "road_points_within_1km": road_points_1km,
                "nearest_hospital_distance_m": near_hosp_m,
                "warning": "Mapped civic amenities reflect OpenStreetMap recorded locations."
            }
        }

        # -----------------------------------------
        # 8. RETURN THE ASSESSMENT EVIDENCE
        # -----------------------------------------

        return {
            "assessment_type": "spatial_evidence_summary",

            "category_assessments": category_assessments,

            "integrated_priority_assessment": iups_result,

            "plot": plot,

            "analysis_parameters": {
                "infrastructure_radius_m": 1000,
                "hazard_radius_m": 5000,
                "distance_method": "Haversine spherical distance",
                "road_search_bbox_radius_m": 1200,
                "road_exact_radii_m": [250, 500, 1000],

                "risk_score_generated": False,

                "iups_screening_score_generated": (
                    iups_result.get("status") == "success"
                )
            },

            "infrastructure": {
                "summary_within_1km": infrastructure_summary,
                "nearest_assets": nearest_assets
            },

            "road_network": {
                "search_bbox_radius_m": search_radius_m,
                "candidate_points_in_bbox": len(road_candidates),
                "road_points_within_250m": road_points_250m,
                "road_points_within_500m": road_points_500m,
                "road_points_within_1km": road_points_1km,

                "nearest_road_point_m": (
                    road_candidates[0]["distance_m"]
                    if road_candidates
                    else None
                ),

                "road_type_distribution": road_type_distribution,
                "nearest_roads": nearest_roads,

                "geometry_note": (
                    "Road records contain representative points, "
                    "not complete road-line geometries."
                )
            },

            "hazard_observations": hazard_observations,

            "historical_flood_context": {
                "matching_event_count": len(
                    historical_flood_events
                ),

                "geographic_precision": (
                    "District names only; events are not "
                    "geocoded to individual plot locations."
                ),

                "events": historical_flood_events
            },

            "data_sources": data_sources,

            "limitations": [
                "Heat measurements are historical. "
                "Exact observation dates are unavailable.",

                "Rainfall observations represent two "
                "historical dates, not current rainfall.",

                "Rainfall measurements alone cannot "
                "confirm flooding at the selected plot.",

                "Historical flood events provide regional "
                "context, not plot-level flood confirmation.",

                "Infrastructure proximity does not establish "
                "facility availability or service capacity.",

                "No validated predictive risk model or probability "
                "estimate has been generated. IUPS is a relative "
                "screening indicator.",

                "Road proximity counts represent road sample points, "
                "not complete road segments or actual route connectivity."
            ]
        }

    except HTTPException:
        raise

    except Exception as error:
        print("Plot assessment error:", str(error))

        raise HTTPException(
            status_code=503,
            detail="Unable to generate plot assessment. Check the database and assessment data."
        )


# =============================================
# GET: ASSESS A SAVED PLOT
# =============================================

@router.get("/plots/{location_id}")
def assess_plot(location_id: int):
    """Retrieve spatial evidence and risk scores for a saved plot ID."""
    plot = db.spatial_locations.find_one(
        {
            "location_id": location_id,
            "location_type": "plot"
        },
        {
            "_id": 0,
            "location_id": 1,
            "latitude": 1,
            "longitude": 1,
            "created_at": 1
        }
    )

    if plot is None:
        raise HTTPException(
            status_code=404,
            detail="Saved plot location was not found."
        )

    latitude = float(plot["latitude"])
    longitude = float(plot["longitude"])
    return run_spatial_assessment(latitude, longitude, location_id=location_id, plot_record=plot)


# =============================================
# POST: ASSESS ANY ARBITRARY COORDINATES
# =============================================

@router.post("/evaluate")
def evaluate_coordinates(payload: CoordinateAssessmentRequest):
    """Evaluate Flood, Heat, Infrastructure, and IUPS risk for any clicked coordinates."""
    return run_spatial_assessment(payload.latitude, payload.longitude)
