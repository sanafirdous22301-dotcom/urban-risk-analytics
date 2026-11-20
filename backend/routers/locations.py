
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from database.mongodb import db
from database.counters import get_next_sequence
from backend.location_schemas import PlotLocationCreate


router = APIRouter(
    prefix="/api/locations",
    tags=["Spatial Locations"]
)


# POST: Save a new plot location

@router.post("/plots", status_code=201)
def create_plot_location(location: PlotLocationCreate):

    try:
        location_id = get_next_sequence("location_id")

        location_document = {
            "_id": location_id,
            "location_id": location_id,
            "location_type": "plot",
            "latitude": location.latitude,
            "longitude": location.longitude,
            "geom": {
                "type": "Point",
                "coordinates": [
                    location.longitude,
                    location.latitude
                ]
            },
            "created_at": datetime.now(timezone.utc)
        }

        db.spatial_locations.insert_one(location_document)

        return {
            "message": "Plot location saved successfully",
            "location_id": location_id,
            "location_type": "plot",
            "latitude": location.latitude,
            "longitude": location.longitude
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to save plot location"
        )


# GET: Retrieve all saved plot locations

@router.get("/plots")
def get_plot_locations():

    try:
        locations = list(
            db.spatial_locations.find(
                {"location_type": "plot"},
                {
                    "_id": 0,
                    "location_id": 1,
                    "location_type": 1,
                    "latitude": 1,
                    "longitude": 1,
                    "created_at": 1
                }
            ).sort("location_id", -1)
        )

        return {
            "total": len(locations),
            "locations": locations
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve plot locations"
        )
