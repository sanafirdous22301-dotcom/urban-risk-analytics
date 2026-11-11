
import json
import csv
import os
import math

RAW = "data/raw/infrastructure/OSM"
OUTPUT = "data/processed/infrastructure"

os.makedirs(OUTPUT, exist_ok=True)


def load_geojson(filename):
    path = os.path.join(RAW, filename)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["features"]


# Calculate distance between two geographical coordinates
def haversine(coord1, coord2):
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    radius = 6371

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = lat2 - lat1
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 2 * radius * math.asin(math.sqrt(a))


# --------------------------------
# 1. PROCESS POINT INFRASTRUCTURE
# --------------------------------

point_files = {
    "hospitals.geojson": "hospital",
    "fire_stations.geojson": "fire_station",
    "buildings.geojson": "building"
}

point_records = []

for filename, category in point_files.items():

    features = load_geojson(filename)

    for feature in features:

        geometry = feature.get("geometry")
        if not geometry or geometry.get("type") != "Point":
            continue

        lon, lat = geometry["coordinates"]
        properties = feature.get("properties", {})

        point_records.append({
            "osm_id": feature.get("id"),
            "category": category,
            "name": properties.get("name"),
            "subtype": (
                properties.get("amenity")
                or properties.get("building")
            ),
            "latitude": lat,
            "longitude": lon
        })


point_path = os.path.join(
    OUTPUT, "infrastructure_points.csv"
)

with open(point_path, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "osm_id", "category", "name",
            "subtype", "latitude", "longitude"
        ]
    )

    writer.writeheader()
    writer.writerows(point_records)


# --------------------------------
# 2. PROCESS ROAD NETWORK
# --------------------------------

road_features = load_geojson("roads.geojson")

road_records = []

for feature in road_features:

    geometry = feature.get("geometry")

    if not geometry or geometry.get("type") != "LineString":
        continue

    coordinates = geometry.get("coordinates", [])

    if len(coordinates) < 2:
        continue

    properties = feature.get("properties", {})

    # Approximate representative location
    longitude = sum(p[0] for p in coordinates) / len(coordinates)
    latitude = sum(p[1] for p in coordinates) / len(coordinates)

    # Calculate road segment length
    length_km = sum(
        haversine(coordinates[i], coordinates[i + 1])
        for i in range(len(coordinates) - 1)
    )

    road_records.append({
        "osm_id": feature.get("id"),
        "road_name": properties.get("name"),
        "road_type": properties.get("highway"),
        "maxspeed": properties.get("maxspeed"),
        "oneway": properties.get("oneway"),
        "latitude": latitude,
        "longitude": longitude,
        "length_km": round(length_km, 4)
    })


road_path = os.path.join(
    OUTPUT, "roads_processed.csv"
)

with open(road_path, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "osm_id", "road_name", "road_type",
            "maxspeed", "oneway", "latitude",
            "longitude", "length_km"
        ]
    )

    writer.writeheader()
    writer.writerows(road_records)


# --------------------------------
# 3. FINAL REPORT
# --------------------------------

print("\n========== INFRASTRUCTURE PROCESSING ==========")

print("Hospital records:",
      sum(r["category"] == "hospital" for r in point_records))

print("Fire station records:",
      sum(r["category"] == "fire_station" for r in point_records))

print("Building records:",
      sum(r["category"] == "building" for r in point_records))

print("Total point records:", len(point_records))

print("Road segments processed:", len(road_records))

print(
    "Total approximate road length:",
    round(sum(r["length_km"] for r in road_records), 2),
    "km"
)

print("\nSaved files:")
print(point_path)
print(road_path)

print("\nInfrastructure preprocessing completed!")
