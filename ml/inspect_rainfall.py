
import rasterio
import numpy as np
import pandas as pd
from pathlib import Path

rainfall_folder = Path("data/raw/flood/rainfall")

# Hyderabad bounding box
left, bottom = 78.30, 17.25
right, top = 78.65, 17.55

all_data = []

for file_path in rainfall_folder.glob("*.cog"):

    print("\nProcessing:", file_path.name)

    with rasterio.open(file_path) as src:

        window = rasterio.windows.from_bounds(
            left, bottom, right, top,
            transform=src.transform
        )

        rainfall = src.read(
            1, window=window, masked=True
        )

        crop_transform = src.window_transform(window)

        rows, cols = np.indices(rainfall.shape)

        longitudes, latitudes = rasterio.transform.xy(
            crop_transform, rows, cols
        )

        date = (
            file_path.name
            .replace("chirps-v3.0.rnl.", "")
            .replace(".cog", "")
            .replace(".", "-")
        )

        df = pd.DataFrame({
            "date": date,
            "latitude": np.array(latitudes).ravel(),
            "longitude": np.array(longitudes).ravel(),
            "rainfall_mm": rainfall.filled(np.nan).ravel()
        })

        all_data.append(df)

        print("Valid pixels:", rainfall.count())
        print("Mean rainfall:", rainfall.mean(), "mm")

# Combine all dates
combined = pd.concat(all_data, ignore_index=True)

output_path = (
    "data/processed/flood/hyderabad_rainfall.csv"
)

combined.to_csv(output_path, index=False)

print("\n--- FINAL DATASET ---")
print("Shape:", combined.shape)
print("Dates:", combined["date"].nunique())
print("Saved to:", output_path)
print(combined.head())
