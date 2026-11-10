
import rasterio
import numpy as np
import matplotlib.pyplot as plt

from rasterio.windows import from_bounds

file_path = "data/raw/flood/VCDWD_L3_F2_NRT.A2026307.h25v07.002.tif"

# Approximate Hyderabad bounding box
left = 78.30
bottom = 17.25
right = 78.65
top = 17.55

with rasterio.open(file_path) as src:
    window = from_bounds(
        left, bottom, right, top,
        transform=src.transform
    )

    data = src.read(1, window=window)

    values, counts = np.unique(data, return_counts=True)

    print("Hyderabad area dimensions:", data.shape)
    print("\nFlood classification:")

    for value, count in zip(values, counts):
        print(f"Class {value}: {count} pixels")

# Plotting section
masked_data = np.ma.masked_equal(data, 255)

cmap = plt.colormaps["viridis"].copy()
cmap.set_bad("lightgray")

plt.figure(figsize=(9, 6))

plt.imshow(
    masked_data,
    cmap=cmap,
    vmin=0,
    vmax=3,
    interpolation="nearest"
)

plt.title("NASA Flood Classification - Hyderabad")
plt.colorbar(label="Flood Classification", ticks=[0, 1, 2, 3])

plt.xlabel("Columns")
plt.ylabel("Rows")
plt.tight_layout()
plt.show()
