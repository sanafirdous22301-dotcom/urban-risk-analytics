
import json
import csv
import os

RAW = "data/raw/infrastructure/OSM"
OUTPUT = "data/processed/infrastructure"

os.makedirs(OUTPUT, exist_ok=True)

files = {
    "hospitals.geojson": "hospital",
    "fire_stations.geojson": "fire_station",
    "buildings.geojson": "building"
}

records = {}

for filename, fallback in files.items():

    path = os.path.join(RAW, filename)

    with open(path, "r", encoding="utf-8") as f:
        features = json.load(f)["features"]

    for feature in features:

        geometry = feature.get("geometry")

        if not geometry or geometry.get("type") != "Point":
            continue

        properties = feature.get("properties", {})
        osm_id = feature.get("id")

        if not osm_id:
            continue

        amenity = properties.get("amenity")
        building = properties.get("building")

        # Use actual OSM tags instead of assuming
        # every feature belongs to its source file category.

        if amenity == "hospital":
            category = "hospital"

        elif amenity == "fire_station":
            category = "fire_station"

        elif fallback == "building":
            category = "building"

        else:
            category = fallback

        lon, lat = geometry["coordinates"]

        record = {
            "osm_id": osm_id,
            "category": category,
            "name": properties.get("name"),
            "subtype": amenity or building,
            "latitude": lat,
            "longitude": lon
        }

        # Prefer classification based on actual amenity tags.
        # This prevents the same OSM object being counted
        # as both a hospital and a fire station.

        priority = {
            "building": 1,
            "hospital": 2,
            "fire_station": 2
        }

        existing = records.get(osm_id)

        if (
            existing is None
            or priority[category] > priority[existing["category"]]
        ):
            records[osm_id] = record


output_path = os.path.join(
    OUTPUT, "infrastructure_points.csv"
)

with open(output_path, "w", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "osm_id",
            "category",
            "name",
            "subtype",
            "latitude",
            "longitude"
        ]
    )

    writer.writeheader()
    writer.writerows(records.values())


print("========== CORRECTED INFRASTRUCTURE ==========")

from collections import Counter

counts = Counter(
    record["category"] for record in records.values()
)

for category, count in counts.items():
    print(category, ":", count)

print("Total unique OSM objects:", len(records))

print("Duplicate IDs remaining:",
      len(records) - len(set(records.keys())))

print("\nSaved:", output_path)
print("Point preprocessing corrected!")
