
import csv
import math
from functools import lru_cache
from pathlib import Path


# Project directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

GRID_CSV = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "integrated_urban_risk"
    / "integrated_urban_risk_priority_grid_1km.csv"
)

# Match the notebook's maximum grid-assignment distance.
MAX_GRID_DISTANCE_KM = 0.75


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two geographic coordinates in km."""

    earth_radius_km = 6371.0

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def to_number(value):
    """Convert CSV values to numbers, keeping missing values as None."""

    try:
        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def to_boolean(value):
    return str(value).strip().lower() in {
        "1", "1.0", "true", "yes"
    }
def load_integrated_grid():
    """Load the integrated priority grid from MongoDB if available, falling back to CSV baseline."""
    try:
        from database.mongodb import db
        if db is not None and "priority_grid_cells" in db.list_collection_names():
            cnt = db.priority_grid_cells.count_documents({})
            if cnt == 791:
                return list(db.priority_grid_cells.find({}, {"_id": 0}))
    except Exception:
        pass

    if not GRID_CSV.exists():
        raise FileNotFoundError(
            f"Integrated grid CSV not found: {GRID_CSV}"
        )

    with open(GRID_CSV, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def assess_plot_iups(latitude, longitude):
    """
    Find the nearest 1 km grid cell and return its
    precomputed Integrated Urban Priority Score.
    """

    grid_cells = load_integrated_grid()

    nearest_cell = None
    nearest_distance = float("inf")

    for cell in grid_cells:

        cell_lat = to_number(cell.get("cell_center_latitude"))
        cell_lon = to_number(cell.get("cell_center_longitude"))

        if cell_lat is None or cell_lon is None:
            continue

        distance = haversine_distance(
            latitude,
            longitude,
            cell_lat,
            cell_lon
        )

        if distance < nearest_distance:
            nearest_distance = distance
            nearest_cell = cell

    if nearest_cell is None:
        return {
            "status": "unavailable",
            "reason": "No valid grid cells were found."
        }

    if nearest_distance > MAX_GRID_DISTANCE_KM:
        return {
            "status": "unavailable",
            "reason": "Plot is outside the grid assignment distance.",
            "nearest_grid_distance_km": round(nearest_distance, 3),
            "maximum_grid_distance_km": MAX_GRID_DISTANCE_KM
        }

    score = to_number(nearest_cell.get("priority_score_0_100"))

    if score is None:
        return {
            "status": "not_scored",
            "reason": "No flood or heat hazard evidence is available for the nearest grid cell.",
            "grid_id": nearest_cell.get("grid_id"),
            "nearest_grid_distance_km": round(nearest_distance, 3)
        }

    return {
        "status": "success",
        "assessment_type": "Integrated Urban Priority Screening",

        "grid": {
            "grid_id": nearest_cell.get("grid_id"),
            "latitude": to_number(nearest_cell.get("cell_center_latitude")),
            "longitude": to_number(nearest_cell.get("cell_center_longitude")),
            "distance_from_plot_km": round(nearest_distance, 3)
        },

        "priority_score": round(score, 3),
        "priority_score_scale": "0-100",
        "priority_band": nearest_cell.get("screening_priority"),

        "components": {
            "flood_evidence_score": to_number(
                nearest_cell.get("flood_evidence_score")
            ),
            "heat_evidence_score": to_number(
                nearest_cell.get("heat_evidence_score")
            ),
            "infrastructure_gap_score": to_number(
                nearest_cell.get("infrastructure_gap_score")
            ),
            "road_representation_gap_score": to_number(
                nearest_cell.get("road_representation_gap_score")
            )
        },

        "component_coverage": {
            "count": to_number(
                nearest_cell.get("priority_score_component_count")
            ),
            "ratio": to_number(
                nearest_cell.get("priority_score_component_coverage")
            ),
            "hazard_component_count": to_number(
                nearest_cell.get("hazard_component_count")
            )
        },

        "source_availability": {
            "flood": to_boolean(nearest_cell.get("flood_data_available")),
            "modis": to_boolean(nearest_cell.get("modis_data_available")),
            "yale": to_boolean(nearest_cell.get("yale_data_available")),
            "infrastructure": to_boolean(
                nearest_cell.get("infrastructure_data_available")
            ),
            "roads": to_boolean(nearest_cell.get("road_data_available"))
        },

        "investigation_flags": {
            "no_mapped_infrastructure": to_boolean(
                nearest_cell.get("investigation_no_mapped_infrastructure")
            ),
            "low_infrastructure": to_boolean(
                nearest_cell.get("investigation_low_infrastructure")
            ),
            "low_road_representation": to_boolean(
                nearest_cell.get("investigation_low_road_representation")
            ),
            "limited_data": to_boolean(
                nearest_cell.get("investigation_limited_data")
            )
        },

        "limitations": [
            "The score represents relative screening priority, not predicted risk or probability.",
            "The nearest 1 km grid cell is used as a proxy for the selected plot.",
            "Infrastructure and road gaps represent mapped-data proxies, not verified service adequacy.",
            "Historical flood context is not independently geocoded to the plot."
        ]
    }
