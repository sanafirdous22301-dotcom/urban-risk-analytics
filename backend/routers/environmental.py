"""
Environmental Intelligence API Router for URBANRISK Hyderabad.
Exposes updated satellite indicators: 2023 MODIS LST, 2024 Sentinel-2 NDVI, and 2021 ESA WorldCover.
"""

from fastapi import APIRouter, HTTPException, Query
from database.mongodb import db
from backend.services.environmental_service import EnvironmentalService

router = APIRouter(
    prefix="/api/environmental",
    tags=["Environmental"]
)

service = EnvironmentalService()


@router.get("/summary")
def get_environmental_summary():
    """
    Returns metadata catalog, observation dates, resolution, quality control,
    and citywide coverage statistics for updated satellite environmental intelligence.
    """
    try:
        return service.get_environmental_summary(db=db)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve environmental summary: {str(e)}"
        )


@router.get("/grid/sample")
def get_environmental_grid_sample(
    limit: int = Query(default=25, ge=1, le=100, description="Max cells to return")
):
    """
    Returns a sample of 1-km grid cells with updated satellite environmental indicators.
    """
    try:
        if db is None or "environmental_indicators" not in db.list_collection_names():
            return {"status": "unavailable", "cells": [], "total_cells": 0}

        col = db["environmental_indicators"]
        cursor = col.find({}, {"_id": 0}).limit(limit)
        cells = list(cursor)

        return {
            "status": "success",
            "total_cells": col.count_documents({}),
            "returned_cells": len(cells),
            "cells": cells
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve environmental grid cells: {str(e)}"
        )


@router.get("/catalog")
def get_environmental_catalog():
    """
    Returns authoritative metadata definitions for all satellite environmental products.
    """
    try:
        if db is not None and "environmental_catalog" in db.list_collection_names():
            docs = list(db.environmental_catalog.find({}, {"_id": 0}))
            if docs:
                return {"status": "success", "catalog": docs}
        return {"status": "success", "catalog": service.get_environmental_summary(db=None)["catalog"]}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve environmental catalog: {str(e)}"
        )
