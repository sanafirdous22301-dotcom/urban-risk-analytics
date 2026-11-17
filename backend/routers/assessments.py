from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import math
from database.session import get_db


router = APIRouter(
    prefix="/api/assessments",
    tags=["Plot Assessments"]
)


# =============================================
# GET: ASSESS A SAVED PLOT
# =============================================

@router.get("/plots/{location_id}")
def assess_plot(
    location_id: int,
    db: Session = Depends(get_db)
):

    # -----------------------------------------
    # 1. RETRIEVE THE SELECTED PLOT
    # -----------------------------------------

    plot_query = text("""
        SELECT
            location_id,
            latitude,
            longitude,
            created_at
        FROM spatial_locations
        WHERE location_id = :location_id
          AND location_type = 'plot'
    """)

    plot = db.execute(
        plot_query,
        {"location_id": location_id}
    ).mappings().first()

    if plot is None:
        raise HTTPException(
            status_code=404,
            detail="Saved plot location was not found."
        )


    # -----------------------------------------
    # 2. INFRASTRUCTURE WITHIN 1 KM
    # -----------------------------------------

    infrastructure_summary_query = text("""
        SELECT
            category,
            COUNT(*) AS assets_within_1km,
            ROUND(MIN(distance_m), 1) AS nearest_distance_m
        FROM (
            SELECT
                a.category,
                ST_Distance_Sphere(
                    a.geom,
                    p.geom
                ) AS distance_m

            FROM infrastructure_assets a

            CROSS JOIN (
                SELECT geom
                FROM spatial_locations
                WHERE location_id = :location_id
                  AND location_type = 'plot'
            ) p

        ) AS asset_distances

        WHERE distance_m <= 1000

        GROUP BY category
        ORDER BY assets_within_1km DESC
    """)

    infrastructure_summary = db.execute(
        infrastructure_summary_query,
        {"location_id": location_id}
    ).mappings().all()


    # -----------------------------------------
    # 3. TEN NEAREST INFRASTRUCTURE ASSETS
    # -----------------------------------------

    nearest_assets_query = text("""
        SELECT
            a.asset_id,
            a.category,
            a.asset_name,
            a.subtype,
            ROUND(
                ST_Distance_Sphere(
                    a.geom,
                    p.geom
                ),
                1
            ) AS distance_m

        FROM infrastructure_assets a

        CROSS JOIN (
            SELECT geom
            FROM spatial_locations
            WHERE location_id = :location_id
              AND location_type = 'plot'
        ) p

        ORDER BY distance_m
        LIMIT 10
    """)

    nearest_assets = db.execute(
        nearest_assets_query,
        {"location_id": location_id}
    ).mappings().all()
    # -----------------------------------------
    # 4. NEARBY ROAD-NETWORK ANALYSIS
    # -----------------------------------------

    # Create a 1.2 km bounding box around the plot.
    # This box is used to filter road points through
    # the MySQL spatial index before exact distances.

    latitude = float(plot["latitude"])
    longitude = float(plot["longitude"])

    search_radius_m = 1200

    latitude_delta = search_radius_m / 111320

    longitude_delta = search_radius_m / (
        111320 * max(
            abs(math.cos(math.radians(latitude))),
            0.01
        )
    )

    south = max(-90, latitude - latitude_delta)
    north = min(90, latitude + latitude_delta)

    west = max(-180, longitude - longitude_delta)
    east = min(180, longitude + longitude_delta)

    bbox_wkt = (
        f"POLYGON(("
        f"{west:.8f} {south:.8f},"
        f"{east:.8f} {south:.8f},"
        f"{east:.8f} {north:.8f},"
        f"{west:.8f} {north:.8f},"
        f"{west:.8f} {south:.8f}"
        f"))"
    )

    road_query = text("""
        SELECT
            r.road_id,
            r.road_name,
            r.road_type,
            r.length_km,
            r.maxspeed,
            r.oneway,

            ROUND(
                ST_Distance_Sphere(
                    r.representative_point,
                    p.geom
                ),
                1
            ) AS distance_m

        FROM road_segments r

        CROSS JOIN (
            SELECT geom
            FROM spatial_locations
            WHERE location_id = :location_id
              AND location_type = 'plot'
        ) p

        WHERE MBRIntersects(
            ST_GeomFromText(
                :bbox_wkt,
                4326,
                'axis-order=long-lat'
            ),
            r.representative_point
        )

        ORDER BY distance_m
    """)

    road_candidates = db.execute(
        road_query,
        {
            "location_id": location_id,
            "bbox_wkt": bbox_wkt
        }
    ).mappings().all()


    # Count road representative points within each radius.

    road_points_250m = 0
    road_points_500m = 0
    road_points_1km = 0

    road_type_counts = {}

    for road in road_candidates:

        distance = float(road["distance_m"])

        if distance <= 250:
            road_points_250m += 1

        if distance <= 500:
            road_points_500m += 1

        if distance <= 1000:

            road_points_1km += 1

            road_type = road["road_type"] or "unknown"

            road_type_counts[road_type] = (
                road_type_counts.get(road_type, 0) + 1
            )


    road_type_distribution = [
        {
            "road_type": road_type,
            "road_points_within_1km": count
        }
        for road_type, count in sorted(
            road_type_counts.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ]


    # Keep the five closest road records.

    nearest_roads = [
        dict(road)
        for road in road_candidates[:5]
    ]

    # -----------------------------------------
    # 4. NEARBY HEAT AND RAINFALL OBSERVATIONS
    # -----------------------------------------

    hazard_query = text("""
        SELECT
            dataset_id,
            dataset_name,
            source_name,
            version_label,
            date_range_start,
            date_range_end,

            hazard_type,
            metric_name,
            unit,
            observed_at,

            COUNT(*) AS total_measurements,

            COUNT(DISTINCT location_id)
                AS total_sample_locations,

            COUNT(
                DISTINCT CASE
                    WHEN distance_m <= 5000
                    THEN location_id
                END
            ) AS sample_locations_within_5km,

            ROUND(
                MIN(distance_m),
                1
            ) AS nearest_observation_m,

            ROUND(
                AVG(
                    CASE
                        WHEN distance_m <= 5000
                        THEN metric_value
                    END
                ),
                2
            ) AS average_value_within_5km

        FROM (

            SELECT
                h.dataset_id,
                d.dataset_name,
                d.source_name,
                d.version_label,
                d.date_range_start,
                d.date_range_end,

                h.hazard_type,
                h.metric_name,
                h.metric_value,
                h.unit,
                h.observed_at,

                s.location_id,

                ST_Distance_Sphere(
                    s.geom,
                    p.geom
                ) AS distance_m

            FROM hazard_observations h

            JOIN spatial_locations s
                ON h.location_id = s.location_id

            JOIN dataset_versions d
                ON h.dataset_id = d.dataset_id

            CROSS JOIN (
                SELECT geom
                FROM spatial_locations
                WHERE location_id = :location_id
                  AND location_type = 'plot'
            ) p

            WHERE h.dataset_id IN (1, 9, 10)

        ) AS hazard_distances

        GROUP BY
            dataset_id,
            dataset_name,
            source_name,
            version_label,
            date_range_start,
            date_range_end,
            hazard_type,
            metric_name,
            unit,
            observed_at

        ORDER BY
            dataset_id,
            metric_name,
            observed_at
    """)

    hazard_observations = db.execute(
        hazard_query,
        {"location_id": location_id}
    ).mappings().all()


    # -----------------------------------------
    # 5. HISTORICAL FLOOD EVENTS
    # -----------------------------------------

    flood_query = text("""
        SELECT
            event_id,
            source_event_id,
            start_date,
            end_date,
            main_cause,
            duration_days,
            human_fatality,
            human_injured

        FROM flood_events

        WHERE dataset_id = 13
          AND LOWER(
              COALESCE(district, '')
          ) LIKE '%hyderabad%'

        ORDER BY start_date DESC
    """)

    historical_flood_events = db.execute(
        flood_query
    ).mappings().all()


    # -----------------------------------------
    # 6. DATASET PROVENANCE
    # -----------------------------------------

    source_query = text("""
        SELECT
            dataset_id,
            dataset_name,
            source_name,
            version_label,
            date_range_start,
            date_range_end,
            record_count

        FROM dataset_versions

WHERE dataset_id IN (1, 9, 10, 11, 12, 13)
        ORDER BY dataset_id
    """)

    data_sources = db.execute(
        source_query
    ).mappings().all()


    # -----------------------------------------
    # 7. RETURN THE ASSESSMENT EVIDENCE
    # -----------------------------------------

    return {

        "assessment_type": "spatial_evidence_summary",

        "plot": dict(plot),

        "analysis_parameters": {
            "infrastructure_radius_m": 1000,
            "hazard_radius_m": 5000,
            "distance_method": "ST_Distance_Sphere",
"road_search_bbox_radius_m": 1200,
"road_exact_radii_m": [250, 500, 1000],
            "risk_score_generated": False
            
        },

        "infrastructure": {

            "summary_within_1km": [
                dict(row)
                for row in infrastructure_summary
            ],

            "nearest_assets": [
                dict(row)
                for row in nearest_assets
            ]

        },
"road_network": {

    "search_bbox_radius_m": search_radius_m,

    "candidate_points_in_bbox": len(road_candidates),

    "road_points_within_250m": road_points_250m,

    "road_points_within_500m": road_points_500m,

    "road_points_within_1km": road_points_1km,

    "nearest_road_point_m": (
        road_candidates[0]["distance_m"]
        if road_candidates
        else None
    ),

    "road_type_distribution": road_type_distribution,

    "nearest_roads": nearest_roads,

    "geometry_note": (
        "Road records contain representative points, "
        "not complete road-line geometries."
    )

},
        "hazard_observations": [
            dict(row)
            for row in hazard_observations
        ],

        "historical_flood_context": {

            "matching_event_count": len(
                historical_flood_events
            ),

            "geographic_precision": (
                "District names only; events are not "
                "geocoded to individual plot locations."
            ),

            "events": [
                dict(row)
                for row in historical_flood_events
            ]

        },

        "data_sources": [
            dict(row)
            for row in data_sources
        ],

        "limitations": [

            "Heat measurements are historical. "
            "Exact observation dates are unavailable.",

            "Rainfall observations represent two "
            "historical dates, not current rainfall.",

            "Rainfall measurements alone cannot "
            "confirm flooding at the selected plot.",

            "Historical flood events provide regional "
            "context, not plot-level flood confirmation.",

            "Infrastructure proximity does not establish "
            "facility availability or service capacity.",

            "No validated risk score or predictive model "
            "has been generated.",
"Road proximity counts represent road sample points, "
"not complete road segments or actual route connectivity."        ]

    }