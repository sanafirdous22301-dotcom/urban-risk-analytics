
import pandas as pd

folder = "data/processed/infrastructure"

points = pd.read_csv(
    f"{folder}/infrastructure_points.csv"
)

roads = pd.read_csv(
    f"{folder}/roads_processed.csv"
)

print("========== POINT DATA VALIDATION ==========")

print("Shape:", points.shape)
print("\nMissing values:")
print(points.isnull().sum())

print("\nDuplicate OSM IDs:", points["osm_id"].duplicated().sum())

print("\nCategory distribution:")
print(points["category"].value_counts())

print("\nInvalid coordinates:")
print(
    ((points["latitude"].abs() > 90) |
     (points["longitude"].abs() > 180)).sum()
)

print("\n========== ROAD DATA VALIDATION ==========")

print("Shape:", roads.shape)
print("\nMissing values:")
print(roads.isnull().sum())

print("\nRoad type distribution:")
print(roads["road_type"].value_counts())

print("\nInvalid road lengths:")
print((roads["length_km"] <= 0).sum())

print("\nDuplicate OSM IDs:", roads["osm_id"].duplicated().sum())

print("\nValidation completed!")
