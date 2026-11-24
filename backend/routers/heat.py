from fastapi import APIRouter, HTTPException, Query
from database.mongodb import db
from backend.services.phase6_analytics_service import AdvancedHazardAnalyticsService

router = APIRouter(
    prefix="/api/heat",
    tags=["Urban Heat Intelligence"]
)


@router.get("/vulnerability-profile")
def get_heat_vulnerability_profile(
    latitude: float = Query(17.3850, ge=-90.0, le=90.0),
    longitude: float = Query(78.4867, ge=-180.0, le=180.0)
):
    """
    Returns locality thermal anomaly relative to citywide baseline, hotspot classification,
    canopy vegetation density (NDVI), and environmental cooling vulnerability.
    """
    service = AdvancedHazardAnalyticsService()
    return service.get_heat_vulnerability_profile(latitude, longitude)


@router.get("/model-metadata")
def get_heat_model_metadata():
    """Returns validation metrics, spatial cross-validation, and baseline comparisons for thermal vulnerability model."""
    service = AdvancedHazardAnalyticsService()
    return service.train_or_load_heat_vulnerability_model()


@router.get("/summary")
def get_heat_summary():
    """Return summary statistics for MODIS land surface temperatures, Yale UHI, and ML model status."""
    try:
        modis_day_records = list(
            db.hazard_observations.find(
                {"hazard_type": "heat", "metric_name": "daytime_temp_c"},
                {"_id": 0, "metric_value": 1}
            )
        )
        modis_night_records = list(
            db.hazard_observations.find(
                {"hazard_type": "heat", "metric_name": "nighttime_temp_c"},
                {"_id": 0, "metric_value": 1}
            )
        )
        yale_day_records = list(
            db.hazard_observations.find(
                {"hazard_type": "heat", "metric_name": "daytime_uhi"},
                {"_id": 0, "metric_value": 1}
            )
        )
        yale_night_records = list(
            db.hazard_observations.find(
                {"hazard_type": "heat", "metric_name": "nighttime_uhi"},
                {"_id": 0, "metric_value": 1}
            )
        )

        def calc_stats(records):
            vals = [float(r["metric_value"]) for r in records if r.get("metric_value") is not None]
            if not vals:
                return {"count": 0, "min": None, "max": None, "mean": None}
            return {
                "count": len(vals),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
                "mean": round(sum(vals) / len(vals), 2)
            }

        modis_day_stats = calc_stats(modis_day_records)
        modis_night_stats = calc_stats(modis_night_records)
        yale_day_stats = calc_stats(yale_day_records)
        yale_night_stats = calc_stats(yale_night_records)

        return {
            "status": "operational",
            "module": "Urban Heat Intelligence",
            "modis_observation_year": 2018,
            "yale_observation_period": "2003–2018",
            "data_nature": "Historical satellite observations; not current ambient temperatures",
            "is_real_time": False,
            "is_forecast": False,
            "total_heat_observations": (
                len(modis_day_records)
                + len(modis_night_records)
                + len(yale_day_records)
                + len(yale_night_records)
            ),
            "datasets": {
                "modis": {
                    "dataset_name": "Hyderabad MODIS Heat",
                    "daytime_temp_c": modis_day_stats,
                    "nighttime_temp_c": modis_night_stats
                },
                "yale": {
                    "dataset_name": "Hyderabad Yale Urban Heat",
                    "daytime_uhi": yale_day_stats,
                    "nighttime_uhi": yale_night_stats
                }
            },
            "ml_deployment": {
                "status": "deployed",
                "model_name": "Random Forest Daytime Surface Temperature Regressor",
                "algorithm": "RandomForestRegressor(n_estimators=100, max_depth=12)",
                "endpoints": [
                    "POST /api/ml/predict",
                    "POST /predict",
                    "POST /api/ml/predict/uhi",
                    "GET /api/ml/info"
                ],
                "features": ["latitude", "longitude", "nighttime_temp_c"],
                "target": "daytime_temp_c",
                "evaluation_metrics": {
                    "spatial_cv_mae_c": 0.506,
                    "spatial_cv_rmse_c": 0.697,
                    "spatial_cv_r2": 0.357,
                    "heldout_test_mae_c": 0.506,
                    "heldout_test_r2": 0.357
                }
            }
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve heat summary: {error}"
        )
