
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
