"""
Admin Ingestion Router for URBANRISK Hyderabad.
Provides authenticated endpoints for inspecting ingestion status, reviewing historical runs,
and triggering dataset ingestions.
"""

import os
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Header, Depends, Query
from pydantic import BaseModel, Field

from backend.services.ingestion_service import DatasetIngestionService, DATASET_CADENCE_CONFIG

router = APIRouter(prefix="/api/admin/ingestion", tags=["Admin Dataset Ingestion"])

# Admin secret retrieved strictly from environment. Never provide a fallback or default secret.
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")

def verify_admin_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    Enforces strict header-only authentication via 'X-Admin-Key'.
    - If ADMIN_API_KEY is not configured or is empty in the environment, fails closed with HTTP 503 Service Unavailable.
    - If configured, validates X-Admin-Key in constant time. Missing or invalid keys return HTTP 401.
    - Query-parameter authentication is strictly prohibited.
    """
    admin_secret = os.environ.get("ADMIN_API_KEY")
    if not admin_secret or not admin_secret.strip():
        raise HTTPException(
            status_code=503,
            detail="Administrative ingestion triggers are temporarily unavailable: ADMIN_API_KEY is not configured."
        )

    if not x_admin_key or x_admin_key != admin_secret:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid 'X-Admin-Key' request header."
        )
    return True


class TriggerIngestionRequest(BaseModel):
    dataset_key: str = Field(..., description="Key of dataset to ingest ('weather_open_meteo', 'modis_lst', 'sentinel2_ndvi', 'esa_worldcover', 'historical_floods', or 'all')")
    force: bool = Field(False, description="Whether to bypass provider publishing cadence interval checks")
    dry_run: bool = Field(False, description="Validate data and preview changes without modifying MongoDB")


@router.get("/status")
def get_datasets_status():
    """
    Returns the latest ingestion status, cadence, and last run timestamp for all supported datasets.
    Publicly viewable for transparency and operational monitoring.
    """
    service = DatasetIngestionService()
    statuses = service.get_datasets_status()
    return {
        "status": "success",
        "datasets": statuses,
        "cadence_rules": {
            "weather": "1-3 hours (Open-Meteo model cycles)",
            "modis": "8 days (NASA LST composite)",
            "sentinel2": "5 days (Copernicus constellation revisit)",
            "worldcover": "Annual (static baseline)",
            "historical_floods": "Monthly/Periodic archive"
        }
    }


@router.get("/history")
def get_ingestion_history(
    limit: int = Query(50, ge=1, le=200),
    dataset_key: Optional[str] = Query(None)
):
    """
    Retrieves ingestion run logs from MongoDB `dataset_ingestion_runs`.
    """
    service = DatasetIngestionService()
    runs = service.get_ingestion_history(limit=limit, dataset_key=dataset_key)
    return {
        "status": "success",
        "count": len(runs),
        "history": runs
    }


@router.post("/trigger")
def trigger_dataset_ingestion(
    request: TriggerIngestionRequest,
    is_admin: bool = Depends(verify_admin_key)
):
    """
    Triggers ingestion for a specific dataset or all datasets.
    Protected endpoint: requires 'X-Admin-Key' request header.
    Never logs or exposes the admin key.
    """
    service = DatasetIngestionService()
    try:
        result = service.trigger_ingestion(
            dataset_key=request.dataset_key,
            trigger_type="manual_admin_api",
            force=request.force,
            dry_run=request.dry_run
        )
        return {
            "status": "success",
            "message": f"Ingestion processed for '{request.dataset_key}'",
            "result": result
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
