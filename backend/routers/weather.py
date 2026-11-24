"""
Weather API Router for URBANRISK Hyderabad.
Exposes read-only endpoints for current citywide weather, historical observations, and summary.
"""

from fastapi import APIRouter, HTTPException, Query
from database.mongodb import db
from backend.services.weather_service import WeatherService

router = APIRouter(
    prefix="/api/weather",
    tags=["Weather"]
)

service = WeatherService()


@router.get("/current")
@router.get("/latest")
def get_current_weather():
    """
    Returns the latest verified city-level ambient weather observation for Hyderabad.
    Evaluates observation freshness against current time and includes explicit attribution.
    """
    try:
        res = service.get_latest_observation(db=db)
        if res["status"] == "unavailable" and res.get("data") is None:
            # If DB is empty, try an on-demand initial fetch
            try:
                fetch_res = service.fetch_and_store_weather(db=db)
                if fetch_res.get("status") == "success":
                    res = service.get_latest_observation(db=db)
            except Exception:
                pass

        return res
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve current weather: {str(e)}"
        )


@router.get("/history")
def get_weather_history(
    limit: int = Query(default=24, ge=1, le=100, description="Max observations to return")
):
    """
    Returns chronological history of stored weather observations, sorted newest first.
    """
    try:
        return service.get_weather_history(limit=limit, db=db)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve weather history: {str(e)}"
        )


@router.get("/summary")
def get_weather_summary():
    """
    Returns aggregate citywide meteorological statistics and spatial grid integration boundaries.
    """
    try:
        return service.get_weather_summary(db=db)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve weather summary: {str(e)}"
        )
