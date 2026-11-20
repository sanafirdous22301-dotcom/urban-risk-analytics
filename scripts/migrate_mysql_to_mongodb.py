from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from pymongo import ReplaceOne, ASCENDING, GEOSPHERE

from database.connection import engine
from database.mongodb import db


BATCH_SIZE = 1000

# MySQL table: primary key, columns to migrate, optional spatial fields
TABLES = {
    "dataset_versions": {
        "pk": "dataset_id",
        "columns": [
            "dataset_id", "dataset_name", "source_name", "file_path",
            "version_label", "date_range_start", "date_range_end",
            "retrieved_at", "record_count"
        ]
    },
    "flood_events": {
        "pk": "event_id",
        "columns": [
            "event_id", "dataset_id", "source_event_id", "district",
            "start_date", "end_date", "main_cause", "duration_days",
            "human_fatality", "human_injured"
        ]
    },
    "hazard_observations": {
        "pk": "observation_id",
        "columns": [
            "observation_id", "dataset_id", "location_id", "hazard_type",
            "metric_name", "metric_value", "unit", "observed_at",
            "created_at"
        ]
    },
    "infrastructure_assets": {
        "pk": "asset_id",
        "columns": [
            "asset_id", "dataset_id", "osm_id", "category", "asset_name",
            "subtype", "latitude", "longitude"
        ],
        "geometry": ("geom", "longitude", "latitude")
    },
    "model_runs": {
        "pk": "model_run_id",
        "columns": [
            "model_run_id", "module_name", "algorithm_name",
            "model_version", "run_timestamp", "status", "parameters"
        ]
    },
    "resource_priorities": {
        "pk": "priority_id",
        "columns": [
            "priority_id", "assessment_id", "priority_rank",
            "resource_type", "justification", "created_at"
        ]
    },
    "risk_assessments": {
        "pk": "assessment_id",
        "columns": [
            "assessment_id", "location_id", "model_run_id",
            "flood_score", "heat_score", "infrastructure_score",
            "overall_score", "risk_level", "assessed_at"
        ]
    },
    "road_segments": {
        "pk": "road_id",
        "columns": [
            "road_id", "dataset_id", "osm_id", "road_name", "road_type",
            "maxspeed", "oneway", "length_km", "latitude", "longitude"
        ],
        "geometry": (
            "representative_point", "longitude", "latitude"
        )
    },
    "spatial_locations": {
        "pk": "location_id",
        "columns": [
            "location_id", "location_type", "external_key",
            "latitude", "longitude", "created_at"
        ],
        "geometry": ("geom", "longitude", "latitude")
    }
}


def convert_value(value):
    """Convert MySQL values into BSON-compatible values."""

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, dict):
        return {
            key: convert_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [convert_value(item) for item in value]

    return value


def create_document(row, config):
    """Build a MongoDB document while preserving original IDs."""

    document = {
        key: convert_value(value)
        for key, value in dict(row).items()
    }

    primary_key = config["pk"]

    # Preserve the original MySQL primary key as MongoDB _id.
    document["_id"] = document[primary_key]

    # Convert MySQL POINT columns into GeoJSON.
    if "geometry" in config:
        geometry_name, longitude_name, latitude_name = (
            config["geometry"]
        )

        document[geometry_name] = {
            "type": "Point",
            "coordinates": [
                float(document[longitude_name]),
                float(document[latitude_name])
            ]
        }

    return document


def migrate_table(mysql_connection, table_name, config):
    """Migrate one MySQL table in batches using safe upserts."""

    collection = db[table_name]

    columns = ", ".join(
        f"`{column}`"
        for column in config["columns"]
    )

    primary_key = config["pk"]

    query = text(
        f"SELECT {columns} "
        f"FROM `{table_name}` "
        f"ORDER BY `{primary_key}`"
    )

    result = mysql_connection.execution_options(
        stream_results=True
    ).execute(query)

    total = 0

    while True:
        rows = result.mappings().fetchmany(BATCH_SIZE)

        if not rows:
            break

        operations = []

        for row in rows:
            document = create_document(row, config)

            operations.append(
                ReplaceOne(
                    {"_id": document["_id"]},
                    document,
                    upsert=True
                )
            )

        collection.bulk_write(
            operations,
            ordered=False
        )

        total += len(operations)

        print(
            f"  {table_name}: migrated {total} records"
        )

    result.close()

    return total


def create_indexes():
    """Create indexes needed by the application."""

    index_definitions = {
        "dataset_versions": [
            ("dataset_name", ASCENDING),
            ("retrieved_at", ASCENDING)
        ],
        "flood_events": [
            ("dataset_id", ASCENDING),
            ("district", ASCENDING)
        ],
        "hazard_observations": [
            ("dataset_id", ASCENDING),
            ("location_id", ASCENDING),
            ("hazard_type", ASCENDING)
        ],
        "infrastructure_assets": [
            ("dataset_id", ASCENDING),
            ("category", ASCENDING),
            ("geom", GEOSPHERE)
        ],
        "model_runs": [
            ("module_name", ASCENDING)
        ],
        "resource_priorities": [
            ("assessment_id", ASCENDING)
        ],
        "risk_assessments": [
            ("location_id", ASCENDING),
            ("model_run_id", ASCENDING)
        ],
        "road_segments": [
            ("dataset_id", ASCENDING),
            ("road_type", ASCENDING),
            ("representative_point", GEOSPHERE)
        ],
        "spatial_locations": [
            ("location_type", ASCENDING),
            ("geom", GEOSPHERE)
        ]
    }

    print("\nCreating MongoDB indexes...")

    for collection_name, indexes in index_definitions.items():
        collection = db[collection_name]

        for field, index_type in indexes:
            collection.create_index(
                [(field, index_type)]
            )

        print(f"  Indexes ready: {collection_name}")


def main():
    print("========================================")
    print(" MYSQL TO MONGODB MIGRATION")
    print("========================================")

    print("MongoDB database:", db.name)

    # Ensure all nine collections exist, including empty tables.
    existing = set(db.list_collection_names())

    for table_name in TABLES:
        if table_name not in existing:
            db.create_collection(table_name)

    migration_counts = {}

    print("\nStarting migration...\n")

    with engine.connect() as mysql_connection:
        for table_name, config in TABLES.items():

            print(f"Migrating: {table_name}")

            count = migrate_table(
                mysql_connection,
                table_name,
                config
            )

            migration_counts[table_name] = count

    create_indexes()

    print("\n========================================")
    print(" MIGRATION VERIFICATION")
    print("========================================")

    success = True

    for table_name, source_count in migration_counts.items():

        target_count = db[table_name].count_documents({})

        status = (
            "MATCH"
            if source_count == target_count
            else "MISMATCH"
        )

        print(
            f"{table_name}: "
            f"MySQL={source_count}, "
            f"MongoDB={target_count} [{status}]"
        )

        if source_count != target_count:
            success = False

    print("\n========================================")

    if success:
        print("MIGRATION COMPLETED AND VERIFIED")
    else:
        print("MIGRATION COMPLETED WITH COUNT MISMATCHES")

    print("========================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("\nMIGRATION FAILED")
        print("Error:", repr(error))
        raise
