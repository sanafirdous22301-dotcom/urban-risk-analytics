import json
import os
from collections import Counter

folder = "data/raw/infrastructure/OSM"

files = [
    "hospitals.geojson",
    "fire_stations.geojson",
    "roads.geojson",
    "buildings.geojson"
]

for filename in files:

    path = os.path.join(folder, filename)

    print("\n==========", filename, "==========")

    if not os.path.exists(path):
        print("FILE NOT FOUND!")
        continue

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])

    print("Total features:", len(features))

    geometry_types = Counter(
        feature.get("geometry", {}).get("type")
        for feature in features
    )

    print("Geometry types:", geometry_types)

    print("Sample records:")

    for feature in features[:3]:
        properties = feature.get("properties", {})
        print({
            "name": properties.get("name"),
            "amenity": properties.get("amenity"),
            "highway": properties.get("highway"),
            "building": properties.get("building")
        })