
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.session import get_db


router = APIRouter(
    prefix="/api/map-layers",
    tags=["Map Layers"]
)


def make_bbox(west, south, east, north):
    """
    Create a geographic bounding polygon.
    Coordinates are longitude first, latitude second.
    """

    if west >= east or south >= north:
        raise HTTPException(
            status_code=422,
            detail="Invalid map boundaries. West must be less than east and south less than north."
        )

    return (
        f"POLYGON(({west} {south}, "
        f"{east} {south}, "
        f"{east} {north}, "
        f"{west} {north}, "
        f"{west} {south}))"
    )


@router.get("/infrastructure")
def get_infrastructure(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    category: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=3000, ge=1, le=10000),
    db: Session = Depends(get_db)
):
    bbox_wkt = make_bbox(west, south, east, north)

    query = text("""
        SELECT
            asset_id,
            category,
            asset_name,
            subtype,
            latitude,
            longitude
        FROM infrastructure_assets
        WHERE MBRIntersects(
            ST_GeomFromText(
                :bbox_wkt,
                4326,
                'axis-order=long-lat'
            ),
            geom
        )
        AND (:category IS NULL OR category = :category)
        ORDER BY asset_id
        LIMIT :limit
    """)

    result = db.execute(
        query,
        {
            "bbox_wkt": bbox_wkt,
            "category": category,
            "limit": limit
        }
    )

    features = []

    for row in result.mappings().all():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(row["longitude"]),
                    float(row["latitude"])
                ]
            },
            "properties": {
                "asset_id": row["asset_id"],
                "category": row["category"],
                "name": row["asset_name"],
                "subtype": row["subtype"]
            }
        })

    return {
        "type": "FeatureCollection",
        "total": len(features),
        "limit": limit,
        "truncated": len(features) == limit,
        "features": features
    }


@router.get("/roads")
def get_roads(
    west: float = Query(..., ge=-180, le=180),
    south: float = Query(..., ge=-90, le=90),
    east: float = Query(..., ge=-180, le=180),
    north: float = Query(..., ge=-90, le=90),
    limit: int = Query(default=3000, ge=1, le=10000),
    db: Session = Depends(get_db)
):
    bbox_wkt = make_bbox(west, south, east, north)

    query = text("""
        SELECT
            road_id,
            road_name,
            road_type,
            maxspeed,
            oneway,
            length_km,
            latitude,
            longitude
        FROM road_segments
        WHERE MBRIntersects(
            ST_GeomFromText(
                :bbox_wkt,
                4326,
                'axis-order=long-lat'
            ),
            representative_point
        )
        ORDER BY road_id
        LIMIT :limit
    """)

    result = db.execute(
        query,
        {
            "bbox_wkt": bbox_wkt,
            "limit": limit
        }
    )

    features = []

    for row in result.mappings().all():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(row["longitude"]),
                    float(row["latitude"])
                ]
            },
            "properties": {
                "road_id": row["road_id"],
                "road_name": row["road_name"],
                "road_type": row["road_type"],
                "maxspeed": row["maxspeed"],
                "oneway": row["oneway"],
                "length_km": (
                    float(row["length_km"])
                    if row["length_km"] is not None
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
