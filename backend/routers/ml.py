import json
import warnings
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# Suppress minor scikit-learn patch version difference warnings (1.9.0 vs 1.9.1)
warnings.filterwarnings("ignore", message=".*InconsistentVersionWarning.*")
warnings.filterwarnings("ignore", message=".*Trying to unpickle estimator.*")

router = APIRouter(tags=["Machine Learning"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Model Paths
MODIS_MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "heat"
    / "modis"
    / "modis_daytime_temperature_regression_candidate.joblib"
)

MODIS_METADATA_PATH = (
    PROJECT_ROOT
    / "models"
    / "heat"
    / "modis"
    / "modis_daytime_temperature_regression_metadata.json"
)

YALE_MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "heat"
    / "yale"
    / "yale_daytime_uhi_regression_candidate.joblib"
)

YALE_METADATA_PATH = (
    PROJECT_ROOT
    / "models"
    / "heat"
    / "yale"
    / "yale_daytime_uhi_regression_metadata.json"
)

# Load Models and Metadata Safely
modis_pipeline = None
modis_metadata = {}
yale_pipeline = None
yale_metadata = {}

try:
    if MODIS_MODEL_PATH.exists():
        modis_pipeline = joblib.load(MODIS_MODEL_PATH)
    if MODIS_METADATA_PATH.exists():
        with open(MODIS_METADATA_PATH, "r", encoding="utf-8") as f:
            modis_metadata = json.load(f)
except Exception as err:
    print(f"Warning: Failed to load MODIS heat model: {err}")

try:
    if YALE_MODEL_PATH.exists():
        yale_pipeline = joblib.load(YALE_MODEL_PATH)
    if YALE_METADATA_PATH.exists():
        with open(YALE_METADATA_PATH, "r", encoding="utf-8") as f:
            yale_metadata = json.load(f)
except Exception as err:
    print(f"Warning: Failed to load Yale UHI model: {err}")


# Request and Response Schemas
class HeatPredictRequest(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees",
        examples=[17.3850]
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees",
        examples=[78.4867]
    )
    nighttime_temp_c: float = Field(
        ...,
        ge=-10.0,
        le=60.0,
        description="Measured nighttime land surface temperature in °C",
        examples=[24.5]
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "latitude": 17.3850,
                "longitude": 78.4867,
                "nighttime_temp_c": 24.5
            }
        }
    }


class UHIPredictRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, examples=[17.3850])
    longitude: float = Field(..., ge=-180.0, le=180.0, examples=[78.4867])
    nighttime_uhi: float = Field(
        ...,
        ge=-10.0,
        le=30.0,
        description="Measured nighttime Urban Heat Island anomaly in °C",
        examples=[1.5]
    )


def determine_heat_risk(predicted_daytime_c: float) -> str:
    """Classify heat risk level based on predicted daytime surface temperature."""
    if predicted_daytime_c >= 38.0:
        return "Severe"
    elif predicted_daytime_c >= 34.0:
        return "High"
    elif predicted_daytime_c >= 28.0:
        return "Moderate"
    else:
        return "Low"


def run_modis_prediction(data: HeatPredictRequest) -> dict:
    if modis_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trained MODIS Heat ML model is not loaded."
        )

    input_df = pd.DataFrame([{
        "latitude": data.latitude,
        "longitude": data.longitude,
        "nighttime_temp_c": data.nighttime_temp_c
    }])

    raw_prediction = float(modis_pipeline.predict(input_df)[0])
    predicted_daytime = round(raw_prediction, 2)
    temp_diff = round(predicted_daytime - data.nighttime_temp_c, 2)
    risk_level = determine_heat_risk(predicted_daytime)

    return {
        "status": "success",
        "task": modis_metadata.get(
            "task",
            "Daytime land surface temperature estimation"
        ),
        "model_name": modis_metadata.get(
            "selected_algorithm",
            "Random Forest Regressor"
        ),
        "input": {
            "latitude": data.latitude,
            "longitude": data.longitude,
            "nighttime_temp_c": data.nighttime_temp_c
        },
        "prediction": {
            "predicted_daytime_temp_c": predicted_daytime,
            "diurnal_temperature_difference_c": temp_diff,
            "heat_risk_level": risk_level,
            "unit": "Celsius (°C)"
        },
        "evaluation_metrics": {
            "spatial_cv_mae_c": round(
                modis_metadata.get("spatial_cv_mae_c", 0.506), 3
            ),
            "heldout_test_mae_c": round(
                modis_metadata.get("heldout_spatial_test_mae_c", 0.949), 3
            ),
            "heldout_test_rmse_c": round(
                modis_metadata.get("heldout_spatial_test_rmse_c", 1.360), 3
            ),
            "heldout_test_r2": round(
                modis_metadata.get("heldout_spatial_test_r2", 0.357), 3
            )
        }
    }


# ML Endpoints
@router.post("/api/ml/predict")
def predict_temperature(data: HeatPredictRequest):
    """Predict daytime surface temperature and heat risk level from spatial coordinates and nighttime temperature."""
    return run_modis_prediction(data)


@router.post("/predict")
def predict_alias(data: HeatPredictRequest):
    """Compatibility endpoint matching root prediction path."""
    return run_modis_prediction(data)


@router.post("/api/ml/predict/uhi")
def predict_uhi(data: UHIPredictRequest):
    """Predict daytime Urban Heat Island (UHI) anomaly from spatial coordinates and nighttime UHI."""
    if yale_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trained Yale UHI ML model is not loaded."
        )

    input_df = pd.DataFrame([{
        "latitude": data.latitude,
        "longitude": data.longitude,
        "nighttime_uhi": data.nighttime_uhi
    }])

    raw_prediction = float(yale_pipeline.predict(input_df)[0])
    predicted_uhi = round(raw_prediction, 3)

    return {
        "status": "success",
        "task": yale_metadata.get(
            "task",
            "Daytime UHI anomaly estimation"
        ),
        "model_name": yale_metadata.get(
            "selected_algorithm",
            "Random Forest Regressor"
        ),
        "input": {
            "latitude": data.latitude,
            "longitude": data.longitude,
            "nighttime_uhi": data.nighttime_uhi
        },
        "prediction": {
            "predicted_daytime_uhi_anomaly_c": predicted_uhi,
            "unit": "Celsius anomaly (°C)"
        },
        "evaluation_metrics": {
            "spatial_cv_mae_c": round(
                yale_metadata.get("spatial_cv_mae_c", 0.393), 3
            ),
            "heldout_test_mae_c": round(
                yale_metadata.get("heldout_spatial_test_mae_c", 0.240), 3
            ),
            "heldout_test_rmse_c": round(
                yale_metadata.get("heldout_spatial_test_rmse_c", 0.323), 3
            ),
            "heldout_test_r2": round(
                yale_metadata.get("heldout_spatial_test_r2", 0.509), 3
            )
        }
    }


@router.get("/api/ml/info")
def ml_model_information():
    """Retrieve detailed information, algorithms, and evaluation metrics for deployed ML models."""
    return {
        "system": "Integrated Urban Risk Analytics and Resource Prioritization System",
        "module": "Machine Learning Model Deployment",
        "active_models": [
            {
                "id": "modis_heat_random_forest",
                "name": "Hyderabad MODIS Daytime Surface Temperature Regressor",
                "algorithm": modis_metadata.get(
                    "selected_algorithm",
                    "Random Forest Regressor"
                ),
                "target": "daytime_temp_c",
                "features": ["latitude", "longitude", "nighttime_temp_c"],
                "dataset": "Hyderabad MODIS Heat (hyderabad_modis_heat.csv)",
                "pipeline": "StandardScaler + RandomForestRegressor",
                "loaded": modis_pipeline is not None,
                "endpoint": "POST /api/ml/predict",
                "metrics": {
                    "spatial_cv_mae_c": modis_metadata.get(
                        "spatial_cv_mae_c"
                    ),
                    "heldout_spatial_test_mae_c": modis_metadata.get(
                        "heldout_spatial_test_mae_c"
                    ),
                    "heldout_spatial_test_rmse_c": modis_metadata.get(
                        "heldout_spatial_test_rmse_c"
                    ),
                    "heldout_spatial_test_r2": modis_metadata.get(
                        "heldout_spatial_test_r2"
                    )
                }
            },
            {
                "id": "yale_uhi_random_forest",
                "name": "Hyderabad Yale Daytime Urban Heat Island Regressor",
                "algorithm": yale_metadata.get(
                    "selected_algorithm",
                    "Random Forest Regressor"
                ),
                "target": "daytime_uhi",
                "features": ["latitude", "longitude", "nighttime_uhi"],
                "dataset": "Hyderabad Yale Heat (hyderabad_yale_heat.csv)",
                "pipeline": "StandardScaler + RandomForestRegressor",
                "loaded": yale_pipeline is not None,
                "endpoint": "POST /api/ml/predict/uhi",
                "metrics": {
                    "spatial_cv_mae_c": yale_metadata.get(
                        "spatial_cv_mae_c"
                    ),
                    "heldout_spatial_test_mae_c": yale_metadata.get(
                        "heldout_spatial_test_mae_c"
                    ),
                    "heldout_spatial_test_rmse_c": yale_metadata.get(
                        "heldout_spatial_test_rmse_c"
                    ),
                    "heldout_spatial_test_r2": yale_metadata.get(
                        "heldout_spatial_test_r2"
                    )
                }
            }
        ]
    }
