
import pandas as pd

path = "data/processed/infrastructure/infrastructure_points.csv"

df = pd.read_csv(path)

duplicates = df[
    df.duplicated(subset=["osm_id"], keep=False)
].sort_values("osm_id")

print("========== DUPLICATE OSM IDs ==========")

print("Duplicate records:", len(duplicates))

print(
    duplicates[
        ["osm_id", "category", "name", "subtype"]
    ].to_string(index=False)
)

print("\n========== DUPLICATES WITHIN CATEGORIES ==========")

same_category = df[
    df.duplicated(
        subset=["osm_id", "category"],
        keep=False
    )
]

print(same_category.to_string(index=False))

print("\n========== CROSS-CATEGORY DUPLICATES ==========")

category_counts = df.groupby("osm_id")["category"].nunique()

cross_category = category_counts[category_counts > 1]

print(cross_category)

print("\nDuplicate investigation completed!")
