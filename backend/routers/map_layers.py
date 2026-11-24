
from fastapi import APIRouter, HTTPException, Query

from database.mongodb import db


router = APIRouter(
    prefix="/api/map-layers",
    tags=["Map Layers"]
)


def make_bbox(west, south, east, north):
    """
    Create a GeoJSON bounding polygon.
    Coordinates are longitude first, latitude second.
    """

    if west >= east or south >= north:
        raise HTTPException(
            status_code=422,
            detail="Invalid map boundaries. West must be less than east and south less than north."
        )

    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south]
        ]]
    }


@router.get("/infrastructure")
def get_infrastructure(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    category: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=3000, ge=1, le=10000)
):

    if not isinstance(limit, int):
        limit = 3000
    if not isinstance(category, str):
        category = None

    bbox_geometry = make_bbox(west, south, east, north)

    query_filter = {
        "geom": {
            "$geoWithin": {
                "$geometry": bbox_geometry
            }
        }
    }

    if category is not None:
        query_filter["category"] = category

    try:
        records = list(
            db.infrastructure_assets.find(
                query_filter,
                {
                    "_id": 0,
                    "asset_id": 1,
                    "category": 1,
                    "asset_name": 1,
                    "subtype": 1,
                    "latitude": 1,
                    "longitude": 1
                }
            ).sort("asset_id", 1).limit(limit)
        )

        features = []

        for record in records:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(record["longitude"]),
                        float(record["latitude"])
                    ]
                },
                "properties": {
                    "asset_id": record["asset_id"],
                    "category": record["category"],
                    "name": record["asset_name"],
                    "subtype": record["subtype"]
                }
            })

        return {
            "type": "FeatureCollection",
            "total": len(features),
            "limit": limit,
            "truncated": len(features) == limit,
            "features": features
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve infrastructure map data"
        )


@router.get("/roads")
def get_roads(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    limit: int = Query(default=3000, ge=1, le=10000)
):

    if not isinstance(limit, int):
        limit = 3000

    bbox_geometry = make_bbox(west, south, east, north)

    query_filter = {
        "representative_point": {
            "$geoWithin": {
                "$geometry": bbox_geometry
            }
        }
    }

    try:
        records = list(
            db.road_segments.find(
                query_filter,
                {
                    "_id": 0,
                    "road_id": 1,
                    "road_name": 1,
                    "road_type": 1,
                    "maxspeed": 1,
                    "oneway": 1,
                    "length_km": 1,
                    "latitude": 1,
                    "longitude": 1
                }
            ).sort("road_id", 1).limit(limit)
        )

        features = []

        for record in records:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        float(record["longitude"]),
                        float(record["latitude"])
                    ]
                },
                "properties": {
                    "road_id": record["road_id"],
                    "road_name": record["road_name"],
                    "road_type": record["road_type"],
                    "maxspeed": record["maxspeed"],
                    "oneway": record["oneway"],
                    "length_km": (
                        float(record["length_km"])
                        if record["length_km"] is not None
                        else None
                    )
                }
            })

        return {
            "type": "FeatureCollection",
            "total": len(features),
            "limit": limit,
            "truncated": len(features) == limit,
            "features": features
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve road map data"
        )


@router.get("/risk-grid")
def get_risk_grid():
    """
    Return all 791 1-km grid cells in Greater Hyderabad as a GeoJSON FeatureCollection
    for live map rendering (overall IUPS, flood, heat, and infrastructure layers).
    """
    try:
        cells = list(db.priority_grid_cells.find())
        features = []
        for c in cells:
            clat = c.get("cell_center_latitude")
            clon = c.get("cell_center_longitude")
            if clat is None or clon is None:
                continue

            pri_score = c.get("priority_score_0_100")
            if pri_score is not None:
                pri_score = round(float(pri_score), 1)

            flood_score = c.get("flood_evidence_score")
            if flood_score is not None:
                flood_score = round(float(flood_score), 3)

            heat_score = c.get("heat_evidence_score")
            if heat_score is not None:
                heat_score = round(float(heat_score), 3)

            infra_score = c.get("infrastructure_gap_score")
            if infra_score is not None:
                infra_score = round(float(infra_score), 3)

            road_score = c.get("road_representation_gap_score")
            if road_score is not None:
                road_score = round(float(road_score), 3)

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(clon), float(clat)]
                },
                "properties": {
                    "grid_id": c.get("grid_id"),
                    "priority_score": pri_score,
                    "screening_priority": c.get("screening_priority") or "Not scored",
                    "flood_evidence_score": flood_score,
                    "heat_evidence_score": heat_score,
                    "infrastructure_gap_score": infra_score,
                    "road_representation_gap_score": road_score,
                    "is_scored": c.get("screening_priority") != "Not scored"
                }
            })

        return {
            "type": "FeatureCollection",
            "total": len(features),
            "features": features
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve risk grid GeoJSON: {str(e)}"
        )

