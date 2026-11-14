
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.session import get_db
from backend.routers.datasets import router as datasets_router
from backend.routers.locations import router as locations_router


# =====================================
# 1. CREATE FASTAPI APPLICATION
# =====================================

app = FastAPI(
    title="Urban Risk Analytics API",
    description="Backend API for the Integrated Urban Risk Analytics and Resource Prioritization System",
    version="1.0.0"
)


# =====================================
# 2. REGISTER API ROUTERS
# =====================================

app.include_router(datasets_router)
app.include_router(locations_router)


# =====================================
# 3. HOME ENDPOINT
# =====================================

@app.get("/")
def home():
    return {
        "message": "Urban Risk Analytics API is running",
        "status": "success"
    }


# =====================================
# 4. DATABASE HEALTH CHECK
# =====================================

@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):

    result = db.execute(
        text("SELECT DATABASE(), VERSION()")
    )

    database_name, mysql_version = result.fetchone()

    return {
        "status": "connected",
        "database": database_name,
        "mysql_version": mysql_version
    }


# =====================================
# 5. SYSTEM STATUS
# =====================================

@app.get("/api/system-status")
def system_status(db: Session = Depends(get_db)):

    table_names = [
        "dataset_versions",
        "spatial_locations",
        "model_runs",
        "hazard_observations",
        "flood_events",
        "infrastructure_assets",
        "road_segments",
        "risk_assessments",
        "resource_priorities"
    ]

    table_counts = {}

    for table in table_names:

        result = db.execute(
            text(f"SELECT COUNT(*) FROM `{table}`")
        )

        table_counts[table] = result.scalar_one()

    return {
        "database": "urban_risk_db",
        "status": "connected",
        "table_counts": table_counts
    }


# =====================================
# 6. SERVE FRONTEND
# =====================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FRONTEND_DIR = PROJECT_ROOT / "frontend"

app.mount(
    "/app",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend"
)
