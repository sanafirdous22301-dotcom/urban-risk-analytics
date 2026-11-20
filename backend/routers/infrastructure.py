from fastapi import APIRouter, HTTPException
from database.mongodb import db

router = APIRouter(
    prefix="/api/infrastructure",
    tags=["Infrastructure Intelligence"]
)


@router.get("/summary")
def get_infrastructure_summary():
    """Return summary statistics for infrastructure assets, road network segments, and spatial indexes."""
    try:
        categories = db.infrastructure_assets.distinct("category")
        category_counts = {}
        for cat in categories:
            category_counts[cat or "unspecified"] = db.infrastructure_assets.count_documents({"category": cat})

        total_assets = sum(category_counts.values())

        road_types = db.road_segments.distinct("road_type")
        road_type_counts = {}
        for rtype in road_types:
            road_type_counts[rtype or "unspecified"] = db.road_segments.count_documents({"road_type": rtype})

        total_roads = sum(road_type_counts.values())

        return {
            "status": "operational",
            "module": "Infrastructure Intelligence",
            "infrastructure_assets": {
                "total_records": total_assets,
                "categories": category_counts,
                "hospitals": category_counts.get("hospital", 0),
                "fire_stations": category_counts.get("fire_station", 0),
                "buildings": category_counts.get("building", 0)
            },
            "road_network": {
                "total_records": total_roads,
                "road_types": road_type_counts,
                "residential": road_type_counts.get("residential", 0),
                "tertiary": road_type_counts.get("tertiary", 0),
                "secondary": road_type_counts.get("secondary", 0),
                "primary": road_type_counts.get("primary", 0),
                "trunk": road_type_counts.get("trunk", 0),
                "motorway": road_type_counts.get("motorway", 0),
                "unclassified": road_type_counts.get("unclassified", 0)
            },
            "spatial_indexing": {
                "collection_indexes": [
                    {"collection": "road_segments", "index": "2dsphere on representative_point"},
                    {"collection": "spatial_locations", "index": "unique index on location_id"},
                    {"collection": "infrastructure_assets", "index": "category and coordinate indexing"}
                ]
            }
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve infrastructure summary: {error}"
        )
