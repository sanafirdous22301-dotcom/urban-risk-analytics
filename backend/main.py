
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from database.mongodb import db, check_mongodb_connection
from database.counters import initialize_counter

from backend.routers.map_layers import router as map_layers_router
from backend.routers.assessments import router as assessments_router
from backend.routers.datasets import router as datasets_router
from backend.routers.locations import router as locations_router
from backend.routers.ml import router as ml_router
from backend.routers.flood import router as flood_router
from backend.routers.heat import router as heat_router
from backend.routers.infrastructure import router as infrastructure_router


# 1. LIFESPAN MANAGEMENT (MONGODB COUNTER INITIALIZATION)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure MongoDB sequence counters and model registry are primed without overwriting existing IDs."""
    try:
        initialize_counter("location_id", "spatial_locations", "location_id")
        initialize_counter("dataset_id", "dataset_versions", "dataset_id")

        # Prime deployed model entry in model_runs collection
        db.model_runs.update_one(
            {"module_name": "Urban Heat Intelligence", "model_version": "candidate-v1"},
            {
                "$set": {
                    "module_name": "Urban Heat Intelligence",
                    "algorithm_name": "RandomForestRegressor(n_estimators=100, max_depth=12)",
                    "model_version": "candidate-v1",
                    "status": "deployed",
                    "run_timestamp": datetime.now(timezone.utc),
                    "parameters": {
                        "features": ["latitude", "longitude", "nighttime_temp_c"],
                        "target": "daytime_temp_c",
                        "heldout_test_mae_c": 0.506,
                        "heldout_test_r2": 0.357,
                        "spatial_cv_mae_c": 0.506
                    }
                }
            },
            upsert=True
        )
        print("MongoDB sequence counters and model registry initialized successfully.")
    except Exception as error:
        print(f"Notice: MongoDB counter initialization skipped or deferred: {error}")
    yield


# 2. CREATE FASTAPI APPLICATION

app = FastAPI(
    title="Urban Risk Analytics API",
    description="Backend API for the Integrated Urban Risk Analytics and Resource Prioritization System",
    version="1.0.0",
    lifespan=lifespan
)


# 3. REGISTER API ROUTERS

app.include_router(datasets_router)
app.include_router(locations_router)
app.include_router(map_layers_router)
app.include_router(assessments_router)
app.include_router(ml_router)
app.include_router(flood_router)
app.include_router(heat_router)
app.include_router(infrastructure_router)


# 3. HOME ENDPOINT

@app.get("/")
def home():
    return {
        "message": "Urban Risk Analytics API is running",
        "status": "success",
        "database": "MongoDB",
        "ml_model_deployed": True,
        "prediction_endpoint": "/api/ml/predict",
        "model_info_endpoint": "/api/ml/info",
        "docs_url": "/docs"
    }


# 4. MONGODB HEALTH CHECK

@app.get("/health/db")
def database_health():
    try:
        result = check_mongodb_connection()
        server_info = db.client.server_info()

        return {
            "status": "connected",
            "database": db.name,
            "mongodb_version": server_info["version"],
            "ping": result["ok"]
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="MongoDB connection failed"
        )


# 5. SYSTEM STATUS

@app.get("/api/system-status")
def system_status():
    collection_names = [
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

    try:
        table_counts = {}

        for collection_name in collection_names:
            table_counts[collection_name] = (
                db[collection_name].count_documents({})
            )

        return {
            "database": db.name,
            "status": "connected",
            "table_counts": table_counts
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve MongoDB system status"
        )


# 6. SERVE FRONTEND

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app.mount(
    "/app",
    StaticFiles(directory=str(FRONTEND_DIR / "html"), html=True),
    name="frontend"
)

app.mount(
    "/css",
    StaticFiles(directory=str(FRONTEND_DIR / "css")),
    name="frontend-css"
)

app.mount(
    "/js",
    StaticFiles(directory=str(FRONTEND_DIR / "js")),
    name="frontend-js"
)
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR / "static")),
    name="frontend-static"
)
