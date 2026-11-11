
import pandas as pd
import json
import os

# Create processed folder if it doesn't exist
os.makedirs("data/processed/heat", exist_ok=True)

# ==================================
# 1. YALE UHI DATASET
# ==================================

yale = pd.read_csv(
    "data/raw/heat/Hyderabad_UHI_Heat_Data.csv"
)

# Extract latitude and longitude
yale_geo = yale[".geo"].apply(json.loads)

yale["longitude"] = yale_geo.apply(
    lambda x: x["coordinates"][0]
)
yale["latitude"] = yale_geo.apply(
    lambda x: x["coordinates"][1]
)

# Select and rename columns
yale_processed = yale[
    ["system:index", "latitude", "longitude",
     "Daytime", "Nighttime"]
].rename(columns={
    "system:index": "pixel_id",
    "Daytime": "daytime_uhi",
    "Nighttime": "nighttime_uhi"
})

# Remove duplicate records
yale_processed = yale_processed.drop_duplicates()

# Save processed data
yale_processed.to_csv(
    "data/processed/heat/hyderabad_yale_heat.csv",
    index=False
)


# ==================================
# 2. NASA MODIS DATASET
# ==================================

modis = pd.read_csv(
    "data/raw/heat/Hyderabad_MODIS_Heat_2018.csv"
)

# Extract latitude and longitude
modis_geo = modis[".geo"].apply(json.loads)

modis["longitude"] = modis_geo.apply(
    lambda x: x["coordinates"][0]
)
modis["latitude"] = modis_geo.apply(
    lambda x: x["coordinates"][1]
)

# Select and rename columns
modis_processed = modis[
    ["system:index", "latitude", "longitude",
     "LST_Day_1km", "LST_Night_1km"]
].rename(columns={
    "system:index": "pixel_id",
    "LST_Day_1km": "daytime_temp_c",
    "LST_Night_1km": "nighttime_temp_c"
})

# Remove duplicate records
modis_processed = modis_processed.drop_duplicates()

# Save processed data
modis_processed.to_csv(
    "data/processed/heat/hyderabad_modis_heat.csv",
    index=False
)


# ==================================
# 3. DATA VALIDATION
# ==================================

print("\n========== YALE HEAT DATA ==========")
print("Shape:", yale_processed.shape)
print(yale_processed.head())
print("\nMissing values:")
print(yale_processed.isnull().sum())

print("\n========== MODIS HEAT DATA ==========")
print("Shape:", modis_processed.shape)
print(modis_processed.head())
print("\nMissing values:")
print(modis_processed.isnull().sum())

print("\nHeat preprocessing completed successfully!")
