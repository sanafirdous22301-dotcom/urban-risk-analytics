
import csv
import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from database.connection import engine


ROOT = Path(__file__).resolve().parent.parent


def read_csv(relative_path):
    path = ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Source file is empty: {path}")

    return rows


def clean(value):
    if value is None:
        return None

    value = str(value).strip()

    if value == "" or value.lower() in ("nan", "none", "null"):
        return None

    return value


def number(value):
    value = clean(value)

    if value is None:
        return None

    return float(value)


def integer(value):
    value = number(value)

    if value is None:
        return None

    return int(value)


def parse_date(value):
    value = clean(value)

    if value is None:
        return None

    formats = (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    raise ValueError(f"Unrecognized date: {value}")


def register_dataset(connection, metadata):
    existing = connection.execute(
        text("""
            SELECT dataset_id
            FROM dataset_versions
            WHERE dataset_name = :name
              AND version_label <=> :version
        """),
        {
            "name": metadata["dataset_name"],
            "version": metadata["version_label"],
        },
    ).scalar_one_or_none()

    if existing is not None:
        connection.execute(
            text("""
                UPDATE dataset_versions
                SET source_name = :source,
                    file_path = :path,
                    record_count = :count,
                    date_range_start = :start_date,
                    date_range_end = :end_date
                WHERE dataset_id = :dataset_id
            """),
            {
                "source": metadata["source_name"],
                "path": metadata["file_path"],
                "count": metadata["record_count"],
                "start_date": metadata["date_range_start"],
                "end_date": metadata["date_range_end"],
                "dataset_id": existing,
            },
        )

        return existing

    result = connection.execute(
        text("""
            INSERT INTO dataset_versions
            (
                dataset_name, source_name, file_path,
                version_label, date_range_start,
                date_range_end, record_count
            )
            VALUES
            (
                :dataset_name, :source_name, :file_path,
                :version_label, :date_range_start,
                :date_range_end, :record_count
            )
        """),
        metadata,
    )

    return result.lastrowid


def get_location_id(connection, external_key, latitude, longitude):
    connection.execute(
        text("""
            INSERT INTO spatial_locations
            (
                location_type, external_key,
                latitude, longitude, geom
            )
            VALUES
            (
                'grid_point', :external_key,
                :latitude, :longitude,
                ST_GeomFromText(
                    :point_wkt, 4326, 'axis-order=long-lat'
                )
            )
            ON DUPLICATE KEY UPDATE
                location_id = LAST_INSERT_ID(location_id)
        """),
        {
            "external_key": external_key,
            "latitude": latitude,
            "longitude": longitude,
            "point_wkt": f"POINT({longitude} {latitude})",
        },
    )

    return connection.execute(
        text("""
            SELECT location_id
            FROM spatial_locations
            WHERE location_type = 'grid_point'
              AND external_key = :external_key
        """),
        {"external_key": external_key},
    ).scalar_one()


def import_hazard_dataset(
    connection, dataset_id, rows, source_type
):
    # Replace this source dataset's previous observations.
    # Other datasets and user-created plot records remain untouched.
    connection.execute(
        text("""
            DELETE FROM hazard_observations
            WHERE dataset_id = :dataset_id
        """),
        {"dataset_id": dataset_id},
    )

    observations = []

    for index, row in enumerate(rows, start=1):
        latitude = number(row["latitude"])
        longitude = number(row["longitude"])

        if latitude is None or longitude is None:
            raise ValueError(
                f"{source_type} row {index} has missing coordinates"
            )

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError(
                f"{source_type} row {index} has invalid coordinates"
            )

        if source_type == "MODIS":
            external_key = f"MODIS:{clean(row['pixel_id']) or index}"
            hazard_type = "heat"
            observed_at = None
            metrics = [
                ("daytime_temp_c", "°C", row["daytime_temp_c"]),
                ("nighttime_temp_c", "°C", row["nighttime_temp_c"]),
            ]

        elif source_type == "YALE":
            external_key = f"YALE:{clean(row['pixel_id']) or index}"
            hazard_type = "heat"
            observed_at = None
            metrics = [
                ("daytime_uhi", "°C", row["daytime_uhi"]),
                ("nighttime_uhi", "°C", row["nighttime_uhi"]),
            ]

        else:
            external_key = (
                f"RAIN:{latitude:.6f}:{longitude:.6f}"
            )
            hazard_type = "flood"
            observed_at = parse_date(row["date"])
            metrics = [
                ("rainfall_mm", "mm", row["rainfall_mm"]),
            ]

        location_id = get_location_id(
            connection,
            external_key,
            latitude,
            longitude,
        )

        for metric_name, unit, raw_value in metrics:
            observations.append({
                "dataset_id": dataset_id,
                "location_id": location_id,
                "hazard_type": hazard_type,
                "metric_name": metric_name,
                "metric_value": number(raw_value),
                "unit": unit,
                "observed_at": observed_at,
            })

    if observations:
        connection.execute(
            text("""
                INSERT INTO hazard_observations
                (
                    dataset_id, location_id, hazard_type,
                    metric_name, metric_value, unit, observed_at
                )
                VALUES
                (
                    :dataset_id, :location_id, :hazard_type,
                    :metric_name, :metric_value, :unit, :observed_at
                )
            """),
            observations,
        )

    return len(observations)


def stable_fallback(prefix, row, index):
    content = "|".join(
        str(row.get(key, "")) for key in sorted(row)
    )

    digest = hashlib.sha256(
        f"{index}|{content}".encode("utf-8")
    ).hexdigest()[:24]

    return f"{prefix}:{digest}"


def import_infrastructure(connection, dataset_id, rows):
    for index, row in enumerate(rows, start=1):
        latitude = number(row["latitude"])
        longitude = number(row["longitude"])

        if latitude is None or longitude is None:
            raise ValueError(
                f"Infrastructure row {index} has missing coordinates"
            )

        osm_id = clean(row["osm_id"])

        if osm_id is None:
            osm_id = stable_fallback("LOCAL", row, index)

        connection.execute(
            text("""
                INSERT INTO infrastructure_assets
                (
                    dataset_id, osm_id, category, asset_name,
                    subtype, latitude, longitude, geom
                )
                VALUES
                (
                    :dataset_id, :osm_id, :category, :asset_name,
                    :subtype, :latitude, :longitude,
                    ST_GeomFromText(
                        :point_wkt, 4326, 'axis-order=long-lat'
                    )
                )
                ON DUPLICATE KEY UPDATE
                    category = VALUES(category),
                    asset_name = VALUES(asset_name),
                    subtype = VALUES(subtype),
                    latitude = VALUES(latitude),
                    longitude = VALUES(longitude),
                    geom = VALUES(geom)
            """),
            {
                "dataset_id": dataset_id,
                "osm_id": osm_id,
                "category": clean(row["category"]) or "unknown",
                "asset_name": clean(row["name"]),
                "subtype": clean(row["subtype"]),
                "latitude": latitude,
                "longitude": longitude,
                "point_wkt": f"POINT({longitude} {latitude})",
            },
        )


def import_roads(connection, dataset_id, rows):
    for index, row in enumerate(rows, start=1):
        latitude = number(row["latitude"])
        longitude = number(row["longitude"])

        if latitude is None or longitude is None:
            raise ValueError(
                f"Road row {index} has missing coordinates"
            )

        osm_id = clean(row["osm_id"])

        if osm_id is None:
            osm_id = stable_fallback("LOCAL", row, index)

        connection.execute(
            text("""
                INSERT INTO road_segments
                (
                    dataset_id, osm_id, road_name, road_type,
                    maxspeed, oneway, length_km,
                    latitude, longitude, representative_point
                )
                VALUES
                (
                    :dataset_id, :osm_id, :road_name, :road_type,
                    :maxspeed, :oneway, :length_km,
                    :latitude, :longitude,
                    ST_GeomFromText(
                        :point_wkt, 4326, 'axis-order=long-lat'
                    )
                )
                ON DUPLICATE KEY UPDATE
                    road_name = VALUES(road_name),
                    road_type = VALUES(road_type),
                    maxspeed = VALUES(maxspeed),
                    oneway = VALUES(oneway),
                    length_km = VALUES(length_km),
                    latitude = VALUES(latitude),
                    longitude = VALUES(longitude),
                    representative_point = VALUES(representative_point)
            """),
            {
                "dataset_id": dataset_id,
                "osm_id": osm_id,
                "road_name": clean(row["road_name"]),
                "road_type": clean(row["road_type"]),
                "maxspeed": clean(row["maxspeed"]),
                "oneway": clean(row["oneway"]),
                "length_km": number(row["length_km"]),
                "latitude": latitude,
                "longitude": longitude,
                "point_wkt": f"POINT({longitude} {latitude})",
            },
        )


def import_flood_events(connection, dataset_id, rows):
    for index, row in enumerate(rows, start=1):
        source_id = clean(row["UEI"])

        if source_id is None:
            source_id = f"ROW:{index}"
        else:
            source_id = f"UEI:{source_id}:ROW:{index}"

        start_date = (
            parse_date(row["Start_Date_Parsed"])
            if clean(row["Start_Date_Parsed"])
            else parse_date(row["Start Date"])
        )

        end_date = (
            parse_date(row["End_Date_Parsed"])
            if clean(row["End_Date_Parsed"])
            else parse_date(row["End Date"])
        )

        connection.execute(
            text("""
                INSERT INTO flood_events
                (
                    dataset_id, source_event_id, district,
                    start_date, end_date, main_cause,
                    duration_days, human_fatality, human_injured
                )
                VALUES
                (
                    :dataset_id, :source_event_id, :district,
                    :start_date, :end_date, :main_cause,
                    :duration_days, :human_fatality, :human_injured
                )
                ON DUPLICATE KEY UPDATE
                    district = VALUES(district),
                    start_date = VALUES(start_date),
                    end_date = VALUES(end_date),
                    main_cause = VALUES(main_cause),
                    duration_days = VALUES(duration_days),
                    human_fatality = VALUES(human_fatality),
                    human_injured = VALUES(human_injured)
            """),
            {
                "dataset_id": dataset_id,
                "source_event_id": source_id,
                "district": clean(row["Districts"]),
                "start_date": start_date,
                "end_date": end_date,
                "main_cause": clean(row["Main Cause"]),
                "duration_days": integer(row["Duration(Days)"]),
                "human_fatality": integer(row["Human fatality"]),
                "human_injured": integer(row["Human injured"]),
            },
        )


def main():
    print("========== URBAN RISK DATA IMPORT ==========")

    modis = read_csv(
        "data/processed/heat/hyderabad_modis_heat.csv"
    )
    yale = read_csv(
        "data/processed/heat/hyderabad_yale_heat.csv"
    )
    rainfall = read_csv(
        "data/processed/flood/hyderabad_rainfall.csv"
    )
    infrastructure = read_csv(
        "data/processed/infrastructure/infrastructure_points.csv"
    )
    roads = read_csv(
        "data/processed/infrastructure/roads_processed.csv"
    )
    floods = read_csv(
        "data/processed/flood/hyderabad_historical_flood_events.csv"
    )

    rainfall_dates = [
        parse_date(row["date"]) for row in rainfall
    ]

    metadata = [
        {
            "dataset_name": "Hyderabad MODIS Heat",
            "source_name": "MODIS 2018",
            "file_path": "data/processed/heat/hyderabad_modis_heat.csv",
            "version_label": "2018-v1",
            "date_range_start": None,
            "date_range_end": None,
            "record_count": len(modis),
        },
        {
            "dataset_name": "Hyderabad Yale Urban Heat",
            "source_name": "Yale Urban Heat Dataset",
            "file_path": "data/processed/heat/hyderabad_yale_heat.csv",
            "version_label": "2003-2018-v1",
            "date_range_start": None,
            "date_range_end": None,
            "record_count": len(yale),
        },
        {
            "dataset_name": "Hyderabad Rainfall",
            "source_name": "Rainfall processed source",
            "file_path": "data/processed/flood/hyderabad_rainfall.csv",
            "version_label": "2020-2021-v1",
            "date_range_start": min(rainfall_dates),
            "date_range_end": max(rainfall_dates),
            "record_count": len(rainfall),
        },
        {
            "dataset_name": "Hyderabad Infrastructure Points",
            "source_name": "OpenStreetMap",
            "file_path": "data/processed/infrastructure/infrastructure_points.csv",
            "version_label": "processed-v1",
            "date_range_start": None,
            "date_range_end": None,
            "record_count": len(infrastructure),
        },
        {
            "dataset_name": "Hyderabad Road Network",
            "source_name": "OpenStreetMap",
            "file_path": "data/processed/infrastructure/roads_processed.csv",
            "version_label": "processed-v1",
            "date_range_start": None,
            "date_range_end": None,
            "record_count": len(roads),
        },
        {
            "dataset_name": "Hyderabad Historical Flood Events",
            "source_name": "Historical flood event inventory",
            "file_path": "data/processed/flood/hyderabad_historical_flood_events.csv",
            "version_label": "processed-v1",
            "date_range_start": None,
            "date_range_end": None,
            "record_count": len(floods),
        },
    ]

    with engine.begin() as connection:
        dataset_ids = {}

        for item in metadata:
            dataset_ids[item["dataset_name"]] = register_dataset(
                connection, item
            )

        print("\nDataset registry updated.")

        modis_count = import_hazard_dataset(
            connection,
            dataset_ids["Hyderabad MODIS Heat"],
            modis,
            "MODIS",
        )

        yale_count = import_hazard_dataset(
            connection,
            dataset_ids["Hyderabad Yale Urban Heat"],
            yale,
            "YALE",
        )

        rainfall_count = import_hazard_dataset(
            connection,
            dataset_ids["Hyderabad Rainfall"],
            rainfall,
            "RAIN",
        )

        import_infrastructure(
            connection,
            dataset_ids["Hyderabad Infrastructure Points"],
            infrastructure,
        )

        import_roads(
            connection,
            dataset_ids["Hyderabad Road Network"],
            roads,
        )

        import_flood_events(
            connection,
            dataset_ids["Hyderabad Historical Flood Events"],
            floods,
        )

    print("\n========== IMPORT COMPLETED ==========")
    print("MODIS observations:", modis_count)
    print("Yale observations:", yale_count)
    print("Rainfall observations:", rainfall_count)
    print("Infrastructure records:", len(infrastructure))
    print("Road records:", len(roads))
    print("Historical flood events:", len(floods))
    print("\nAll changes committed successfully.")


if __name__ == "__main__":
    main()
