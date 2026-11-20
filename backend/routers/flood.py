from fastapi import APIRouter, HTTPException
from database.mongodb import db

router = APIRouter(
    prefix="/api/flood",
    tags=["Flood Intelligence"]
)


@router.get("/summary")
def get_flood_summary():
    """Return summary statistics and records for flood events and rainfall observations."""
    try:
        flood_records = list(
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
                "dates_recorded": rainfall_dates,
                "mean_rainfall_mm": round(sum(rainfall_values) / len(rainfall_values), 1) if rainfall_values else 0,
                "max_rainfall_mm": max(rainfall_values) if rainfall_values else 0,
                "min_rainfall_mm": min(rainfall_values) if rainfall_values else 0
            },
            "recent_events": flood_records[:15],
            "all_events": flood_records
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to retrieve flood summary: {error}"
        )
