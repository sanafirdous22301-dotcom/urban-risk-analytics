"""
Package Creator for URBANRISK Kaggle Submission
URBANRISK -- Integrated Urban Risk Analytics Platform

Creates a self-contained, clean archive excluding secrets, virtual environments,
raw GIS behemoths, and temporary build caches.
"""

import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = PROJECT_ROOT / "kaggle_package"
ZIP_PATH = PROJECT_ROOT / "URBANRISK_Kaggle_Submission.zip"

def create_kaggle_package():
    print("=" * 65)
    print(" Creating URBANRISK Kaggle Submission Package & Archive")
    print("=" * 65)

    PKG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy Data Files
    data_dest = PKG_DIR / "data"
    data_dest.mkdir(parents=True, exist_ok=True)
    
    files_to_copy_data = [
        ("data/processed/heat/hyderabad_modis_heat.csv", "data/hyderabad_modis_heat.csv"),
        ("data/processed/heat/hyderabad_yale_heat.csv", "data/hyderabad_yale_heat.csv"),
        ("data/processed/integrated_urban_risk/integrated_urban_risk_priority_grid_1km.csv", "data/integrated_urban_risk_priority_grid_1km.csv"),
        ("data/processed/flood/hyderabad_floods_historical.geojson", "data/hyderabad_floods_historical.geojson"),
        ("data/processed/infrastructure/osm_amenities_hyderabad.geojson", "data/osm_amenities_hyderabad.geojson"),
        ("data/processed/flood/hyderabad_historical_flood_events.csv", "data/hyderabad_historical_flood_events.csv")
    ]

    for src_rel, dest_rel in files_to_copy_data:
        src = PROJECT_ROOT / src_rel
        dest = PKG_DIR / dest_rel
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  [+] Copied: {dest_rel} ({dest.stat().st_size / 1024:.1f} KB)")

    # 2. Copy Trained Models
    models_dest = PKG_DIR / "models"
    models_to_copy = [
        "models/heat/modis/modis_daytime_temperature_regression_candidate.joblib",
        "models/heat/modis/modis_daytime_temperature_regression_metadata.json",
        "models/heat/yale/yale_daytime_uhi_regression_candidate.joblib",
        "models/heat/yale/yale_daytime_uhi_regression_metadata.json"
    ]
    for m in models_to_copy:
        src = PROJECT_ROOT / m
        dest = PKG_DIR / m
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  [+] Copied: {m} ({dest.stat().st_size / (1024*1024):.2f} MB)")

    # 3. Copy Requirements
    shutil.copy2(PROJECT_ROOT / "requirements.txt", PKG_DIR / "requirements.txt")
    print("  [+] Copied: requirements.txt")

    # 4. Create Clean Zip Archive
    print("\nCompressing into URBANRISK_Kaggle_Submission.zip...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in PKG_DIR.rglob("*"):
            if p.is_file() and not p.name.endswith(".zip"):
                arcname = p.relative_to(PROJECT_ROOT)
                zf.write(p, arcname)

    zip_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"\n[SUCCESS] Archive created: {ZIP_PATH.name} ({zip_mb:.2f} MB)")
    print("=" * 65)

if __name__ == "__main__":
    create_kaggle_package()
