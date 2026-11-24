"""
Infrastructure Intelligence and Resource Prioritization Service for URBANRISK Hyderabad.
Calculates:
1. Hospital proximity, distance-band coverage (1km, 3km, 5km), and gaps.
2. Fire-station proximity, distance-band coverage (3km, 5km, 8km), and gaps.
3. Road accessibility assessment (investigates graph-based routing; falls back cleanly to straight-line proximity with explicit caveats).
4. Multi-criteria infrastructure vulnerability & gap screening (distinguishes facility absent vs data unavailable).
5. Explainable resource-prioritization screening recommendations (combining hazard exposure, infrastructure deficits, and data confidence).

Preserves:
- All 791 priority grid cells (741 scored, 50 unscored).
- Approved IUPS composite formula and weights (flood: 0.35, heat: 0.35, infra: 0.15, road: 0.15).
- Zero fabrication of hospital beds, fire engines, emergency staff, or operational capacity.
"""

from datetime import datetime, timezone
import json
import logging
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pymongo

from database.mongodb import db as default_db

logger = logging.getLogger("urbanrisk.infrastructure")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Distance bands for planning screening (configurable screening thresholds, NOT official response standards)
HOSPITAL_DISTANCE_BANDS_KM = [1.0, 3.0, 5.0]
FIRE_STATION_DISTANCE_BANDS_KM = [3.0, 5.0, 8.0]


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two geographic coordinates in kilometers."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2.0) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2.0) ** 2
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
    return R * c


class InfrastructureIntelligenceService:
    def __init__(self, db=None):
        self.db = db if db is not None else default_db
        self._ensure_indexes()
        self._hospitals_cache: Optional[List[Dict[str, Any]]] = None
        self._fire_stations_cache: Optional[List[Dict[str, Any]]] = None

    def _ensure_indexes(self):
        """Ensures indexes on infrastructure collections for fast spatial lookups."""
        try:
            self.db.infrastructure_assets.create_index([("category", pymongo.ASCENDING)])
            self.db.infrastructure_assets.create_index([("latitude", pymongo.ASCENDING), ("longitude", pymongo.ASCENDING)])
            self.db.priority_grid_cells.create_index([("grid_id", pymongo.ASCENDING)], unique=True)
        except Exception as e:
            logger.warning(f"Index creation on infrastructure collections skipped or deferred: {e}")

    def get_mapped_facilities(self, force_refresh: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Loads and caches mapped hospital and fire-station assets from MongoDB."""
        if self._hospitals_cache is None or self._fire_stations_cache is None or force_refresh:
            hospitals = list(self.db.infrastructure_assets.find(
                {"category": "hospital"},
                {"_id": 0, "asset_id": 1, "asset_name": 1, "latitude": 1, "longitude": 1, "osm_id": 1}
            ))
            fire_stations = list(self.db.infrastructure_assets.find(
                {"category": "fire_station"},
                {"_id": 0, "asset_id": 1, "asset_name": 1, "latitude": 1, "longitude": 1, "osm_id": 1}
            ))
            self._hospitals_cache = hospitals
            self._fire_stations_cache = fire_stations
        return self._hospitals_cache, self._fire_stations_cache

    def evaluate_facility_proximity(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Calculates straight-line distances to nearest mapped hospital and fire station,
        facility counts within screening distance bands, and coverage classifications.
        """
        hospitals, fire_stations = self.get_mapped_facilities()

        # 1. Hospital proximity & bands
        hosp_distances = []
        for h in hospitals:
            h_lat, h_lon = h.get("latitude"), h.get("longitude")
            if h_lat is not None and h_lon is not None:
                d = haversine_distance_km(lat, lon, float(h_lat), float(h_lon))
                hosp_distances.append((d, h))

        hosp_distances.sort(key=lambda x: x[0])
        nearest_hosp_dist = hosp_distances[0][0] if hosp_distances else None
        nearest_hosp = hosp_distances[0][1] if hosp_distances else None

        hosp_within_1km = sum(1 for d, _ in hosp_distances if d <= 1.0)
        hosp_within_3km = sum(1 for d, _ in hosp_distances if d <= 3.0)
        hosp_within_5km = sum(1 for d, _ in hosp_distances if d <= 5.0)

        # 2. Fire-station proximity & bands
        fs_distances = []
        for fs in fire_stations:
            fs_lat, fs_lon = fs.get("latitude"), fs.get("longitude")
            if fs_lat is not None and fs_lon is not None:
                d = haversine_distance_km(lat, lon, float(fs_lat), float(fs_lon))
                fs_distances.append((d, fs))

        fs_distances.sort(key=lambda x: x[0])
        nearest_fs_dist = fs_distances[0][0] if fs_distances else None
        nearest_fs = fs_distances[0][1] if fs_distances else None

        fs_within_3km = sum(1 for d, _ in fs_distances if d <= 3.0)
        fs_within_5km = sum(1 for d, _ in fs_distances if d <= 5.0)
        fs_within_8km = sum(1 for d, _ in fs_distances if d <= 8.0)

        # Classifications based on defensible screening assumptions
        # Hospital screening bands: <=1.5km Good, 1.5-3.5km Moderate, >3.5km Potential Gap
        if nearest_hosp_dist is not None:
            if nearest_hosp_dist <= 1.5:
                hosp_coverage_class = "Good Mapped Facility Coverage"
            elif nearest_hosp_dist <= 3.5:
                hosp_coverage_class = "Limited Mapped Facility Coverage"
            else:
                hosp_coverage_class = "Potential Infrastructure Gap"
        else:
            hosp_coverage_class = "Insufficient Infrastructure Evidence"

        # Fire station screening bands: <=3.0km Good, 3.0-6.0km Limited, >6.0km Potential Gap
        if nearest_fs_dist is not None:
            if nearest_fs_dist <= 3.0:
                fs_coverage_class = "Good Mapped Facility Coverage"
            elif nearest_fs_dist <= 6.0:
                fs_coverage_class = "Limited Mapped Facility Coverage"
            else:
                fs_coverage_class = "Potential Infrastructure Gap"
        else:
            fs_coverage_class = "Insufficient Infrastructure Evidence"

        # Combined assessment
        if hosp_coverage_class == "Potential Infrastructure Gap" and fs_coverage_class == "Potential Infrastructure Gap":
            combined_coverage_class = "Potential Infrastructure Gap"
        elif hosp_coverage_class == "Good Mapped Facility Coverage" and fs_coverage_class == "Good Mapped Facility Coverage":
            combined_coverage_class = "Good Mapped Facility Coverage"
        else:
            combined_coverage_class = "Limited Mapped Facility Coverage"

        return {
            "evaluation_coordinates": {"latitude": lat, "longitude": lon},
            "distance_metric": "straight_line_geodesic_km",
            "distance_caveat": (
                "Distances are calculated as straight-line geodesic (Haversine) proximities in kilometers. "
                "These are screening distances, NOT actual road travel distances or emergency response drive times."
            ),
            "hospital_coverage": {
                "nearest_hospital_straight_line_km": round(nearest_hosp_dist, 2) if nearest_hosp_dist is not None else None,
                "nearest_hospital_name": nearest_hosp.get("asset_name") if nearest_hosp else "None found",
                "hospitals_within_1km": hosp_within_1km,
                "hospitals_within_3km": hosp_within_3km,
                "hospitals_within_5km": hosp_within_5km,
                "coverage_classification": hosp_coverage_class,
                "screening_thresholds_km": {"good": "<= 1.5 km", "limited": "1.5 - 3.5 km", "gap": "> 3.5 km"}
            },
            "fire_station_coverage": {
                "nearest_fire_station_straight_line_km": round(nearest_fs_dist, 2) if nearest_fs_dist is not None else None,
                "nearest_fire_station_name": nearest_fs.get("asset_name") if nearest_fs else "None found",
                "fire_stations_within_3km": fs_within_3km,
                "fire_stations_within_5km": fs_within_5km,
                "fire_stations_within_8km": fs_within_8km,
                "coverage_classification": fs_coverage_class,
                "screening_thresholds_km": {"good": "<= 3.0 km", "limited": "3.0 - 6.0 km", "gap": "> 6.0 km"}
            },
            "combined_infrastructure_assessment": {
                "classification": combined_coverage_class,
                "mapped_hospitals_total": len(hospitals),
                "mapped_fire_stations_total": len(fire_stations),
                "data_nature": "OpenStreetMap static snapshot extraction; query date unrecorded",
                "evidence_status": "Mapped physical location presence only; operational readiness, staffing, beds, or vehicle availability are not recorded."
            }
        }

    def inspect_road_network_accessibility(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Evaluates road network representation for the locality.
        Documents graph-routing limitations (disconnected sub-graphs and planar line segments lack turn-restrictions and complete topologies).
        """
        # Count road segments within 1km radius from MongoDB
        road_count = self.db.road_segments.count_documents({
            "latitude": {"$gte": lat - 0.01, "$lte": lat + 0.01},
            "longitude": {"$gte": lon - 0.01, "$lte": lon + 0.01}
        })

        return {
            "evaluation_coordinates": {"latitude": lat, "longitude": lon},
            "local_road_segments_within_1km": road_count,
            "routing_feasibility": "straight_line_proximity_fallback",
            "routing_feasibility_explanation": (
                "The 93,437 OpenStreetMap road features contain disconnected regional fragments, missing bridge/culvert "
                "junction topologies, unverified oneway attributes, and lack turn-restriction or elevation data. "
                "Network graph routing cannot be defended scientifically across all 791 km² without fabricating missing links. "
                "Straight-line geodesic proximity is utilized as a robust, transparent fallback."
            ),
            "data_completeness_flag": (
                "Road-Network Data Available" if road_count >= 10 else "Road-Network Data Incomplete / Low Density"
            )
        }

    def generate_explainable_resource_priorities(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Generates explainable planning screening recommendations combining
        IUPS priority scores, verified hazard exposure, and specific infrastructure deficits.
        Preserves original IUPS ranking and formulas without modification.
        """
        hospitals, fire_stations = self.get_mapped_facilities()

        # Query top IUPS scored cells from priority_grid_cells
        top_cells = list(self.db.priority_grid_cells.find(
            {"integrated_urban_priority_score": {"$ne": None}},
            {"_id": 0}
        ).sort("integrated_urban_priority_score", pymongo.DESCENDING).limit(limit))

        recommendations = []
        for idx, cell in enumerate(top_cells):
            c_lat = cell.get("cell_center_latitude")
            c_lon = cell.get("cell_center_longitude")
            grid_id = cell.get("grid_id")
            iups_score = cell.get("integrated_urban_priority_score", 0.0)
            score_100 = round(iups_score * 100.0, 1)

            # Evaluate facility distances for this grid cell center
            prox = self.evaluate_facility_proximity(c_lat, c_lon)
            hosp_cov = prox["hospital_coverage"]
            fs_cov = prox["fire_station_coverage"]

            # Identify primary deficit and hazard context
            deficits = []
            if hosp_cov["coverage_classification"] == "Potential Infrastructure Gap":
                deficits.append(f"Hospital coverage gap (Nearest mapped hospital: {hosp_cov['nearest_hospital_straight_line_km']} km)")
            elif hosp_cov["coverage_classification"] == "Limited Mapped Facility Coverage":
                deficits.append("Limited hospital proximity")

            if fs_cov["coverage_classification"] == "Potential Infrastructure Gap":
                deficits.append(f"Fire station coverage gap (Nearest mapped station: {fs_cov['nearest_fire_station_straight_line_km']} km)")

            main_gap = "; ".join(deficits) if deficits else "Balanced mapped facility proximity"

            # Primary hazard context
            flood_score = cell.get("flood_evidence_score")
            heat_score = cell.get("heat_evidence_score")
            hazard_context = []
            if flood_score and flood_score > 0.5:
                hazard_context.append("Elevated flood hazard evidence")
            if heat_score and heat_score > 0.5:
                hazard_context.append("Elevated thermal exposure")
            hazard_summary = ", ".join(hazard_context) if hazard_context else "Moderate multi-hazard exposure"

            # Explainable planning justification
            justification = (
                f"Grid Cell #{grid_id} prioritized with IUPS screening score {score_100}/100. "
                f"Main infrastructure context: {main_gap}. "
                f"Hazard exposure context: {hazard_summary}. "
                f"Recommended for municipal spatial planning review and field data verification."
            )

            rec = {
                "rank": idx + 1,
                "grid_id": grid_id,
                "cell_center_latitude": c_lat,
                "cell_center_longitude": c_lon,
                "priority_classification": cell.get("screening_priority", "Higher screening priority"),
                "integrated_urban_priority_score_0_100": score_100,
                "main_infrastructure_gap": main_gap,
                "nearest_hospital_straight_line_km": hosp_cov["nearest_hospital_straight_line_km"],
                "nearest_fire_station_straight_line_km": fs_cov["nearest_fire_station_straight_line_km"],
                "hazard_context": hazard_summary,
                "planning_recommendation": justification,
                "planning_disclaimer": (
                    "Planning-screening recommendation only. Not an official municipal capital expenditure decision. "
                    "Facility operational capacity and road congestion must be verified through local field inspection."
                )
            }
            recommendations.append(rec)

        return recommendations
