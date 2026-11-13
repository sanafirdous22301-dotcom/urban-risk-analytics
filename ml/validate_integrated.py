import pandas as pd

FILE = "data/processed/integrated/hyderabad_urban_risk_dataset.csv"

df = pd.read_csv(FILE)

print("\n========== DATASET VALIDATION ==========")

print("\nShape:")
print(df.shape)

print("\nColumn types:")
print(df.dtypes)

print("\nMissing values:")
print(df.isnull().sum())

print("\nEnvironmental statistics:")
print(df[
    [
        "rainfall_mm",
        "daytime_temp_c",
        "nighttime_temp_c",
        "daytime_uhi",
        "nighttime_uhi"
    ]
].describe())

print("\nInfrastructure statistics:")
print(df[
    [
        "hospital_count",
        "fire_station_count",
        "building_count",
        "road_count",
        "road_length_km"
    ]
].describe())

print("\nNon-zero infrastructure locations:")
for col in [
    "hospital_count",
    "fire_station_count",
    "building_count",
    "road_count"
]:
    print(col, ":", (df[col] > 0).sum())

print("\nCoordinate ranges:")
print("Latitude:", df["latitude"].min(), "to", df["latitude"].max())
print("Longitude:", df["longitude"].min(), "to", df["longitude"].max())

print("\nRisk score distribution:")
print(df["overall_risk_score"].describe())

print("\nRisk categories:")
print(
    pd.cut(
        df["overall_risk_score"],
        bins=[-1, 0.4, 0.6, 1],
        labels=["Low", "Medium", "High"]
    ).value_counts()
)

print("\n========== VALIDATION COMPLETE ==========")