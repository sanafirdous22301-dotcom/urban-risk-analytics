
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.session import get_db
from backend.location_schemas import PlotLocationCreate


router = APIRouter(
    prefix="/api/locations",
    tags=["Spatial Locations"]
)

@router.post("/plots", status_code=201)
def create_plot_location(
    location: PlotLocationCreate,
    db: Session = Depends(get_db)
):
    query = text("""
        INSERT INTO spatial_locations (
            location_type,
            latitude,
            longitude,
            geom
        )
        VALUES (
            'plot',
            :latitude,
            :longitude,
            ST_GeomFromText(
                :point_wkt,
                4326,
                'axis-order=long-lat'
            )
        )
    """)

    result = db.execute(
        query,
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "point_wkt": f"POINT({location.longitude} {location.latitude})"
        }
    )

    db.commit()

    return {
        "message": "Plot location saved successfully",
        "location_id": result.lastrowid,
        "location_type": "plot",
        "latitude": location.latitude,
        "longitude": location.longitude
    }

# GET: Retrieve all saved plot locations
@router.get("/plots")
def get_plot_locations(db: Session = Depends(get_db)):

    query = text("""
        SELECT
            location_id,
            location_type,
            latitude,
            longitude,
            created_at
        FROM spatial_locations
        WHERE location_type = 'plot'
        ORDER BY location_id DESC
    """)

    result = db.execute(query)

    locations = [
        dict(row)
        for row in result.mappings().all()
    ]

    return {
        "total": len(locations),
        "locations": locations
    }
