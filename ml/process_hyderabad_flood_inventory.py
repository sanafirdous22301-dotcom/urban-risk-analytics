
import os
import pandas as pd

INPUT_FILE = "data/raw/flood/India_Flood_Inventory_v3.csv"
OUTPUT_FILE = "data/processed/flood/hyderabad_historical_flood_events.csv"

# Load national flood inventory
df = pd.read_csv(INPUT_FILE)

# Select records explicitly mentioning Hyderabad in Districts
mask = df["Districts"].fillna("").str.contains(
    r"(?i)(?<![a-z])hyderabad(?![a-z])",
    regex=True
)

hyderabad = df.loc[mask].copy()

# Parse dates correctly
hyderabad["Start_Date_Parsed"] = pd.to_datetime(
    hyderabad["Start Date"],
    format="%d-%m-%Y %H:%M",
    errors="coerce"
)

hyderabad["End_Date_Parsed"] = pd.to_datetime(
    hyderabad["End Date"],
    format="%d-%m-%Y %H:%M",
    errors="coerce"
)

# Keep relevant columns
columns = [
    "UEI",
    "Start Date",
    "End Date",
    "Start_Date_Parsed",
    "End_Date_Parsed",
    "Main Cause",
    "Districts",
    "State",
    "Duration(Days)",
    "Human fatality",
    "Human injured"
]

hyderabad = hyderabad[columns].sort_values(
    "Start_Date_Parsed"
)

# Save
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
hyderabad.to_csv(OUTPUT_FILE, index=False)

print("========== HYDERABAD HISTORICAL FLOOD DATA ==========")
print("Total events:", len(hyderabad))
print("Date range:",
      hyderabad["Start_Date_Parsed"].min(),
      "to",
      hyderabad["Start_Date_Parsed"].max())

print("\nEvents by decade:")
decades = (
    hyderabad["Start_Date_Parsed"]
    .dt.year.floordiv(10)
    .mul(10)
    .value_counts()
    .sort_index()
)
print(decades.to_string())

# Verify exact rainfall event matches
rainfall_dates = ["2020-09-25", "2021-10-08"]

print("\n========== RAINFALL EVENT MATCHES ==========")

for date in rainfall_dates:
    matches = hyderabad[
        hyderabad["Start_Date_Parsed"].dt.strftime("%Y-%m-%d") == date
    ]

    print(f"\nDate: {date}")
    print("Matching inventory records:", len(matches))

    if not matches.empty:
        print(matches[
            ["UEI", "Main Cause", "Districts", "Human fatality"]
        ].to_string(index=False))

print("\nSaved:", OUTPUT_FILE)
