
import pandas as pd

file_path = "data/raw/flood/India_Flood_Inventory_v3.csv"

# Load dataset
df = pd.read_csv(file_path)

# Basic information
print("\n--- DATASET SHAPE ---")
print(df.shape)

print("\n--- COLUMN NAMES ---")
print(df.columns.tolist())

print("\n--- DATA TYPES ---")
print(df.dtypes)

print("\n--- FIRST 5 ROWS ---")
print(df.head())

print("\n--- MISSING VALUES ---")
print(df.isnull().sum())

print("\n--- DUPLICATE ROWS ---")
print(df.duplicated().sum())

# Search for Hyderabad or Telangana in text columns
text_columns = df.select_dtypes(include="object").columns

mask = df[text_columns].apply(
    lambda col: col.astype(str).str.contains(
        "Hyderabad|Telangana",
        case=False,
        na=False
    )
).any(axis=1)

print("\n--- HYDERABAD / TELANGANA RECORDS ---")
print(df[mask].head(20))

print("\nMatching records:", mask.sum())

# Exact Telangana records
telangana = df[
    df["State"].astype(str).str.strip().str.lower()
    == "telangana"
]

print("\n--- TELANGANA RECORD COUNT ---")
print(len(telangana))

print("\n--- TELANGANA DISTRICTS ---")
print(telangana["Districts"].value_counts().head(30))

print("\n--- TELANGANA FLOOD EVENTS ---")
print(
    telangana[
        ["Start Date", "End Date", "Main Cause",
         "Districts", "State", "Duration(Days)"]
    ].head(30).to_string(index=False)
)
