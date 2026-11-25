from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from database.mongodb import db
from backend.services.phase6_analytics_service import AdvancedHazardAnalyticsService

router = APIRouter(
    prefix="/api/flood",
    tags=["Flood Intelligence"]
)


def load_historical_flood_records():
    """Returns 40 historical flood records from DB, falling back to source CSV if DB collection is empty."""
    records = []
    try:
        records = list(
            db.flood_events.find(
                {},
                {
                    "_id": 0,
                    "event_id": 1,
                    "source_event_id": 1,
                    "start_date": 1,
                    "end_date": 1,
                    "main_cause": 1,
                    "duration_days": 1,
                    "human_fatality": 1,
                    "human_injured": 1,
                    "district": 1
                }
            ).sort("start_date", -1)
        )
    except Exception:
        pass

    if not records:
        csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "flood" / "hyderabad_historical_flood_events.csv"
        if csv_path.exists():
            import pandas as pd
            df = pd.read_csv(csv_path)
            for idx, row in df.iterrows():
                fatalities = None
                if pd.notna(row.get("Human fatality")):
                    try:
                        fatalities = int(float(row["Human fatality"]))
                    except (ValueError, TypeError):
                        pass
                
                injured = None
                if pd.notna(row.get("Human injured")):
                    try:
                        injured = int(float(row["Human injured"]))
                    except (ValueError, TypeError):
                        pass
                        
                dur = None
                if pd.notna(row.get("Duration(Days)")):
                    try:
                        dur = float(row["Duration(Days)"])
                    except (ValueError, TypeError):
                        pass

                records.append({
                    "event_id": idx + 1,
                    "source_event_id": str(row.get("UEI", f"EVT-{idx+1}")),
                    "start_date": str(row.get("Start_Date_Parsed", row.get("Start Date", ""))),
                    "end_date": str(row.get("End_Date_Parsed", row.get("End Date", ""))),
                    "main_cause": str(row.get("Main Cause", "Heavy Rains & Floods")),
                    "duration_days": dur,
                    "human_fatality": fatalities,
                    "human_injured": injured,
                    "district": str(row.get("Districts", "Hyderabad District"))
                })
    return records


@router.get("/climatology")
def get_flood_rainfall_climatology():
    """Returns 42-year daily rainfall climatological recurrence percentiles and statistics (NASA POWER)."""
    service = AdvancedHazardAnalyticsService()
    return service.get_climatological_rainfall_stats()


@router.get("/evidence-profile")
def get_flood_evidence_profile(
    latitude: float = Query(17.3850, ge=-90.0, le=90.0),
    longitude: float = Query(78.4867, ge=-180.0, le=180.0)
):
    """
    Evaluates locality flood context: direct cell flood evidence vs regional context,
    historical events proximity, and environmental runoff imperviousness context.
    """
    service = AdvancedHazardAnalyticsService()
    return service.evaluate_flood_evidence_profile(latitude, longitude)


@router.get("/historical-events")
def get_historical_flood_events():
    """Returns all 40 documented historical flood disaster events (1969-2022) with impact records."""
    records = load_historical_flood_records()
    return {
        "total": len(records),
        "source": "India Flood Inventory v3 (IMD Disasters Archive 1969-2022)",
        "coverage_period": "1969 to 2022",
        "fatalities_total": 727,
        "events": records
    }


@router.get("/summary")
def get_flood_summary():
    """Return summary statistics and records for flood events and rainfall observations."""
    try:
        flood_records = load_historical_flood_records()

        rainfall_records = list(
            db.hazard_observations.find(
                {"hazard_type": "flood", "metric_name": "rainfall_mm"},
                {"_id": 0, "metric_value": 1, "observed_at": 1}
            )
        )

        cause_counts = {}
        fatalities_total = 0
        events_with_fatalities = 0
        valid_durations = []
        years = []

        for event in flood_records:
            cause = event.get("main_cause") or "Unspecified"
            cause_counts[cause] = cause_counts.get(cause, 0) + 1

            fatality = event.get("human_fatality")
            if fatality is not None and isinstance(fatality, (int, float)):
                fatalities_total += int(fatality)
                events_with_fatalities += 1

            dur = event.get("duration_days")
            if dur is not None and isinstance(dur, (int, float)):
                valid_durations.append(float(dur))

            sdate = event.get("start_date")
            if sdate and len(str(sdate)) >= 4:
                try:
                    years.append(int(str(sdate)[:4]))
                except ValueError:
                    pass

        rainfall_values = [
            float(r["metric_value"])
            for r in rainfall_records
            if r.get("metric_value") is not None
        ]

        rainfall_dates = sorted(
            list(set(str(r["observed_at"]) for r in rainfall_records if r.get("observed_at")))
        )

        return {
            "status": "operational",
            "module": "Flood Intelligence",
            "total_flood_events": len(flood_records),
            "hyderabad_events_count": len(flood_records),
            "fatalities_total": fatalities_total,
            "events_with_fatalities": events_with_fatalities,
            "year_range": {
                "start": min(years) if years else None,
                "end": max(years) if years else None
            },
            "duration_days": {
                "max": max(valid_durations) if valid_durations else 0,
                "avg": round(sum(valid_durations) / len(valid_durations), 1) if valid_durations else 0
            },
            "top_causes": [
                {"cause": k, "count": v}
                for k, v in sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)
            ],
            "rainfall_observations": {
                "total_records": len(rainfall_records),
                "raster_samples_count": len(rainfall_records),
                "distinct_storm_dates_count": len(rainfall_dates),
                "dates_recorded": rainfall_dates,
                "storm_events": ["2020-09-25", "2021-10-08"],
                "rainfall_data_nature": "Historical extreme storm raster extraction (CHIRPS v3.0)",
                "is_real_time": False,
                "is_forecast": False,
                "mean_rainfall_mm": round(sum(rainfall_values) / len(rainfall_values), 1) if rainfall_values else 0,
                "max_rainfall_mm": max(rainfall_values) if rainfall_values else 0,
                "min_rainfall_mm": min(rainfall_values) if rainfall_values else 0
            },
            "storm_events": ["2020-09-25", "2021-10-08"],
            "raster_samples_count": len(rainfall_records),
            "rainfall_data_nature": "Historical extreme storm raster extraction (CHIRPS v3.0)",
            "is_real_time": False,
            "is_forecast": False,
            "recent_events": flood_records[:15],
            "all_events": flood_records
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve flood summary: {error}"
        )
