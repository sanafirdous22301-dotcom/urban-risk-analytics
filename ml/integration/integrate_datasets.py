
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree


# ============================================================
# 1. PROJECT PATHS AND SETTINGS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data" / "processed"

FLOOD_DIR = DATA_DIR / "flood"
HEAT_DIR = DATA_DIR / "heat"
INFRA_DIR = DATA_DIR / "infrastructure"

OUTPUT_DIR = DATA_DIR / "integrated"

OUTPUT_FILE = OUTPUT_DIR / "hyderabad_spatial_features.csv"
REPORT_FILE = OUTPUT_DIR / "integration_quality_report.txt"

EARTH_RADIUS_KM = 6371.0088

INFRA_RADIUS_KM = 1.0
ROAD_RADIUS_KM = 1.0

RAINFALL_MAX_DISTANCE_KM = 10.0
YALE_MAX_DISTANCE_KM = 5.0


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def load_csv(path):

    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}"
        )

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(
            f"Dataset is empty: {path.name}"
        )

    print(f"{path.name}: {df.shape}")

    return df


def validate_spatial_data(df, filename):

    required = [
        "latitude",
        "longitude"
    ]

    for column in required:

        if column not in df.columns:
            raise ValueError(
                f"{filename} is missing {column}"
            )

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    original_count = len(df)

    df = df.dropna(
        subset=["latitude", "longitude"]
    ).copy()

    invalid_count = original_count - len(df)

    if invalid_count:
        print(
            f"{filename}: removed {invalid_count} rows "
            "with invalid coordinates"
        )

    if df.empty:
        raise ValueError(
            f"No valid coordinates found in {filename}"
        )

    if (
        (df["latitude"] < -90).any()
        or (df["latitude"] > 90).any()
        or (df["longitude"] < -180).any()
        or (df["longitude"] > 180).any()
    ):
        raise ValueError(
            f"Invalid coordinate ranges in {filename}"
        )

    return df.reset_index(drop=True)


def nearest_join(base, source, columns, max_distance_km):

    if source.empty:
        raise ValueError(
            "Cannot perform nearest join with empty data."
        )

    base_coordinates = np.radians(
        base[["latitude", "longitude"]].to_numpy()
    )

    source_coordinates = np.radians(
        source[["latitude", "longitude"]].to_numpy()
    )

    tree = BallTree(
        source_coordinates,
        metric="haversine"
    )

    distances, indices = tree.query(
        base_coordinates,
        k=1
    )

    distances_km = (
        distances[:, 0] * EARTH_RADIUS_KM
    )

    matched_values = (
        source.iloc[indices[:, 0]][columns]
        .reset_index(drop=True)
        .copy()
    )

    matched = distances_km <= max_distance_km

    for column in columns:
        matched_values.loc[~matched, column] = np.nan

    return matched_values, distances_km, matched

def nearest_source_distance(base, source):

    if source.empty:
        return np.full(len(base), np.nan)

    base_coordinates = np.radians(
        base[["latitude", "longitude"]].to_numpy()
    )

    source_coordinates = np.radians(
        source[["latitude", "longitude"]].to_numpy()
    )

    tree = BallTree(
        source_coordinates,
        metric="haversine"
    )

    distances, _ = tree.query(
        base_coordinates,
        k=1
    )

    return distances[:, 0] * EARTH_RADIUS_KM

def count_nearby_points(base, source, radius_km):

    if source.empty:
        return np.zeros(len(base), dtype=int)

    base_coordinates = np.radians(
        base[["latitude", "longitude"]].to_numpy()
    )

    source_coordinates = np.radians(
        source[["latitude", "longitude"]].to_numpy()
    )

    tree = BallTree(
        source_coordinates,
        metric="haversine"
    )

    neighbours = tree.query_radius(
        base_coordinates,
        r=radius_km / EARTH_RADIUS_KM
    )

    return np.array([
        len(indices)
        for indices in neighbours
    ])

def aggregate_nearby_roads(base, roads, radius_km):

    base_coordinates = np.radians(
        base[["latitude", "longitude"]].to_numpy()
    )

    road_coordinates = np.radians(
        roads[["latitude", "longitude"]].to_numpy()
    )

    tree = BallTree(
        road_coordinates,
        metric="haversine"
    )

    neighbours = tree.query_radius(
        base_coordinates,
        r=radius_km / EARTH_RADIUS_KM
    )

    road_counts = []
    road_lengths = []

    lengths = roads["length_km"].to_numpy()

    for indices in neighbours:

        road_counts.append(len(indices))

        road_lengths.append(
            np.nansum(lengths[indices])
        )

    return (
        np.array(road_counts),
        np.array(road_lengths)
    )


# ============================================================
# 3. LOAD ALL DATASETS
# ============================================================

print("\n========== LOADING DATA ==========")

rain = load_csv(
    FLOOD_DIR / "hyderabad_rainfall.csv"
)

historical_flood = load_csv(
    FLOOD_DIR / "hyderabad_historical_flood_events.csv"
)

modis = load_csv(
    HEAT_DIR / "hyderabad_modis_heat.csv"
)

yale = load_csv(
    HEAT_DIR / "hyderabad_yale_heat.csv"
)

infra = load_csv(
    INFRA_DIR / "infrastructure_points.csv"
)

roads = load_csv(
    INFRA_DIR / "roads_processed.csv"
)


# ============================================================
# 4. VALIDATE SPATIAL DATASETS
# ============================================================

print("\n========== VALIDATING COORDINATES ==========")

rain = validate_spatial_data(
    rain,
    "Rainfall"
)

modis = validate_spatial_data(
    modis,
    "MODIS"
)

yale = validate_spatial_data(
    yale,
    "Yale"
)

infra = validate_spatial_data(
    infra,
    "Infrastructure"
)

roads = validate_spatial_data(
    roads,
    "Roads"
)


# ============================================================
# 5. VALIDATE RAINFALL OBSERVATIONS
# ============================================================

print("\n========== VALIDATING RAINFALL ==========")

required_rain = [
    "date",
    "rainfall_mm"
]

for column in required_rain:

    if column not in rain.columns:
        raise ValueError(
            f"Rainfall dataset missing {column}"
        )

rain["date"] = pd.to_datetime(
    rain["date"],
    errors="coerce"
).dt.strftime("%Y-%m-%d")

rain["rainfall_mm"] = pd.to_numeric(
    rain["rainfall_mm"],
    errors="coerce"
)

if rain["date"].isna().any():
    raise ValueError(
        "Rainfall contains invalid dates."
    )

if rain["rainfall_mm"].isna().any():
    raise ValueError(
        "Rainfall contains invalid measurements."
    )

rainfall_dates = sorted(
    rain["date"].unique()
)

print("Rainfall observation dates:", rainfall_dates)

for event_date in rainfall_dates:

    event_data = rain[
        rain["date"] == event_date
    ]

    if event_data.duplicated(
        subset=["latitude", "longitude"]
    ).any():

        raise ValueError(
            f"Duplicate rainfall coordinates on {event_date}"
        )

    print(
        event_date,
        "records:",
        len(event_data)
    )


# ============================================================
# 6. VALIDATE HEAT DATASETS
# ============================================================

print("\n========== VALIDATING HEAT DATA ==========")

modis_columns = [
    "daytime_temp_c",
    "nighttime_temp_c"
]

yale_columns = [
    "daytime_uhi",
    "nighttime_uhi"
]

for column in modis_columns:

    if column not in modis.columns:
        raise ValueError(
            f"MODIS dataset missing {column}"
        )

    modis[column] = pd.to_numeric(
        modis[column],
        errors="coerce"
    )

for column in yale_columns:

    if column not in yale.columns:
        raise ValueError(
            f"Yale dataset missing {column}"
        )

    yale[column] = pd.to_numeric(
        yale[column],
        errors="coerce"
    )


# ============================================================
# 7. CREATE BASE SPATIAL GRID
# ============================================================

print("\n========== CREATING BASE GRID ==========")

grid_columns = [
    "latitude",
    "longitude",
    "daytime_temp_c",
    "nighttime_temp_c"
]

if "pixel_id" in modis.columns:
    grid_columns.insert(0, "pixel_id")

grid = (
    modis[grid_columns]
    .drop_duplicates(
        subset=["latitude", "longitude"]
    )
    .reset_index(drop=True)
)

print("Base grid cells:", len(grid))

integrated = grid.copy()


# ============================================================
# 8. MATCH RAINFALL SEPARATELY BY DATE
# ============================================================

print("\n========== MATCHING RAINFALL ==========")

for event_date in rainfall_dates:

    event_data = rain[
        rain["date"] == event_date
    ].reset_index(drop=True)

    values, distances, matched = nearest_join(
        integrated,
        event_data,
        ["rainfall_mm"],
        RAINFALL_MAX_DISTANCE_KM
    )

    label = event_date.replace("-", "_")

    integrated[
        f"rainfall_{label}_mm"
    ] = values["rainfall_mm"]

    integrated[
        f"rainfall_{label}_distance_km"
    ] = distances

    integrated[
        f"rainfall_{label}_matched"
    ] = matched

    print(
        event_date,
        "matched:",
        int(matched.sum()),
        "/",
        len(integrated)
    )


# ============================================================
# 9. MATCH YALE HEAT
# ============================================================

print("\n========== MATCHING YALE HEAT ==========")

values, yale_distances, yale_matched = nearest_join(
    integrated,
    yale,
    yale_columns,
    YALE_MAX_DISTANCE_KM
)

for column in yale_columns:
    integrated[column] = values[column]

integrated["yale_nearest_distance_km"] = yale_distances
integrated["yale_matched"] = yale_matched

print(
    "Yale matched:",
    int(yale_matched.sum()),
    "/",
    len(integrated)
)


# ============================================================
# 10. AGGREGATE INFRASTRUCTURE
# ============================================================

print("\n========== AGGREGATING INFRASTRUCTURE ==========")

if "category" not in infra.columns:
    raise ValueError(
        "Infrastructure dataset missing category column."
    )

infra["category"] = (
    infra["category"]
    .astype(str)
    .str.strip()
    .str.lower()
)

print("\nInfrastructure categories:")
print(infra["category"].value_counts().to_string())

category_mapping = {
    "hospital": "hospital_count_1km",
    "fire_station": "fire_station_count_1km",
    "building": "building_count_1km"
}

for category, output_column in category_mapping.items():

    subset = infra[
        infra["category"] == category
    ]

    integrated[output_column] = count_nearby_points(
        integrated,
        subset,
        INFRA_RADIUS_KM
    )

    print(
        category,
        "source records:",
        len(subset)
    )

# Store distance to nearest infrastructure source

for category in category_mapping:

    subset = infra[
        infra["category"] == category
    ]

    distance_column = category + "_nearest_distance_km"

    integrated[distance_column] = nearest_source_distance(
        integrated,
        subset
    )


# ============================================================
# 11. AGGREGATE ROADS
# ============================================================

print("\n========== AGGREGATING ROADS ==========")

if "length_km" not in roads.columns:
    raise ValueError(
        "Road dataset missing length_km."
    )

roads["length_km"] = pd.to_numeric(
    roads["length_km"],
    errors="coerce"
)

if roads["length_km"].isna().any():
    raise ValueError(
        "Road dataset contains invalid length measurements."
    )

road_count, road_length = aggregate_nearby_roads(
    integrated,
    roads,
    ROAD_RADIUS_KM
)

integrated["road_count_1km"] = road_count

integrated["road_length_km_1km_approx"] = road_length

print("Road source records:", len(roads))
integrated["road_nearest_distance_km"] = nearest_source_distance(
    integrated,
    roads
)

# ============================================================
# 12. ADD DATA PROVENANCE AND LIMITATIONS
# ============================================================

integrated["modis_source"] = "hyderabad_modis_heat.csv"

integrated["modis_temporal_reference"] = (
    "2018 source label; exact observation dates unavailable"
)

integrated["yale_source"] = "hyderabad_yale_heat.csv"

integrated["yale_temporal_reference"] = (
    "2003-2018 historical coverage"
)

integrated["infrastructure_source"] = (
    "infrastructure_points.csv"
)

integrated["roads_source"] = "roads_processed.csv"

# Rainfall dates are explicitly represented by separate columns.
# Historical flood events remain separate because they have
# district-level descriptions without event coordinates.


# ============================================================
# 13. SAVE SPATIAL FEATURE DATASET
# ============================================================

print("\n========== SAVING SPATIAL FEATURES ==========")

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

integrated = integrated.sort_values(
    ["latitude", "longitude"]
).reset_index(drop=True)

integrated.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# 14. GENERATE QUALITY REPORT
# ============================================================

report = []

report.append("HYDERABAD SPATIAL INTEGRATION REPORT")
report.append("=" * 55)

report.append(
    f"Output rows: {len(integrated)}"
)

report.append(
    f"Output columns: {len(integrated.columns)}"
)

report.append(
    f"Rainfall dates: {', '.join(rainfall_dates)}"
)

report.append(
    f"Historical flood records kept separate: {len(historical_flood)}"
)

report.append(
    f"MODIS source records: {len(modis)}"
)

report.append(
    f"Yale source records: {len(yale)}"
)

report.append(
    f"Infrastructure source records: {len(infra)}"
)

report.append(
    f"Road source records: {len(roads)}"
)

report.append("")
report.append("MISSING VALUES")
report.append("-" * 55)

report.append(
    integrated.isna().sum().to_string()
)

report.append("")
report.append("IMPORTANT LIMITATIONS")
report.append("-" * 55)

report.append(
    "Historical flood events do not contain point coordinates."
)

report.append(
    "Rainfall observations are retained as separate dated features."
)

report.append(
    "MODIS and Yale heat observations have different historical periods."
)

report.append(
    "Infrastructure and road extraction dates are not recorded here."
)

report.append(
    "Road lengths are approximate local aggregates based on representative coordinates."
)

report.append(
    "No supervised predictions or artificial risk scores were generated."
)

REPORT_FILE.write_text(
    "\n".join(report),
    encoding="utf-8"
)


# ============================================================
# 15. FINAL SUMMARY
# ============================================================

print("\n==============================================")
print("SPATIAL FEATURE INTEGRATION COMPLETED")
print("==============================================")

print("Output:", OUTPUT_FILE)
print("Quality report:", REPORT_FILE)

print("Shape:", integrated.shape)

print("\nMissing values:")
print(integrated.isna().sum().to_string())

print("\nFirst five records:")
print(integrated.head().to_string(index=False))