"""
Updated Satellite & Environmental Intelligence Service for URBANRISK Hyderabad.
Acquires, validates, and manages updated multi-source satellite datasets:
1. Thermal: MODIS Terra/Aqua 8-Day 1-km Land Surface Temperature (2023, NASA LP DAAC).
2. Vegetation: Sentinel-2 Level-2A 10m NDVI with cloud/shadow masking (2024, ESA/Copernicus).
3. Built-up / Impervious: ESA WorldCover 10m Land Cover (2021, ESA).

Preserves historical MODIS 2018 and Yale 2003-2018 baselines without modification.
Maintains clear boundaries between surface radiative temperature (LST) and ambient air temperature.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import urllib.request
import urllib.parse

import numpy as np
import pandas as pd
import pymongo
import rasterio
import rasterio.warp

logger = logging.getLogger("urbanrisk.environmental")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "environmental"
GRID_BACKBONE_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "infrastructure"
    / "integrated_infrastructure_experiments"
    / "integrated_infrastructure_road_grid_1km.csv"
)

# Open STAC & Cloud-Optimized GeoTIFF (COG) endpoints
SENTINEL2_B04_URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/Q/HV/2024/4/S2A_43QHV_20240427_0_L2A/B04.tif"
SENTINEL2_B08_URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/Q/HV/2024/4/S2A_43QHV_20240427_0_L2A/B08.tif"
SENTINEL2_SCL_URL = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/43/Q/HV/2024/4/S2A_43QHV_20240427_0_L2A/SCL.tif"

ESA_WORLDCOVER_MAP_URL = "https://ai4edataeuwest.blob.core.windows.net/esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_N15E078_Map.tif"
MODIS_LST_DAY_2023_URL = "https://modiseuwest.blob.core.windows.net/modis-061-cogs/MYD11A2/25/07/2023145/MYD11A2.A2023145.h25v07.061.2023154051316_LST_Day_1km.tif"
MODIS_QC_DAY_2023_URL = "https://modiseuwest.blob.core.windows.net/modis-061-cogs/MYD11A2/25/07/2023145/MYD11A2.A2023145.h25v07.061.2023154051316_QC_Day.tif"

ENVIRONMENTAL_CATALOG_META = {
    "thermal": {
        "dataset_name": "MODIS Aqua Land Surface Temperature & Emissivity 8-Day L3 Global 1km",
        "product_id": "MYD11A2.061",
        "publisher": "NASA LP DAAC / USGS via Microsoft Planetary Computer",
        "observation_period": "2023-05-25 to 2023-06-01 (DOY 145)",
        "observation_season": "Peak Dry Pre-Monsoon Summer",
        "spatial_resolution": "1 km (926.6 m sinusoidal grid)",
        "coverage": "Greater Hyderabad (Sinusoidal Tile h25v07)",
        "physical_variable": "Radiometric Land Surface Temperature (LST, °C)",
        "quality_filtering": "QC_Day mandatory QA flag filtering (Bits 0–1 == 00 or 01: LST produced with acceptable cloud-free conditions; rejecting cloud-obscured pixels bits 10/11 and fill value 0)",
        "lst_vs_air_temp_disclaimer": (
            "Land Surface Temperature (LST) is the radiative skin temperature of the ground surface, "
            "not the 2-meter ambient air temperature. On solar-irradiated impervious urban surfaces "
            "(asphalt, concrete, masonry), daytime LST is typically 5°C to 12°C higher than ambient air temperature."
        ),
        "source_url": "https://planetarycomputer.microsoft.com/dataset/modis-11A2-061"
    },
    "vegetation": {
        "dataset_name": "Sentinel-2 MSI Level-2A Bottom-Of-Atmosphere Surface Reflectance",
        "product_id": "S2A_MSIL2A",
        "tile_id": "43QHV (MGRS Tile 43QHV fully encloses Greater Hyderabad: 77.82°E–78.87°E, 17.06°N–18.07°N)",
        "granule_id": "S2A_43QHV_20240427_0_L2A",
        "publisher": "European Space Agency (ESA) / Copernicus via AWS Earth Search",
        "observation_date": "2024-04-27",
        "observation_season": "Pre-Monsoon Summer",
        "spatial_resolution": "10 meters",
        "cloud_cover_scene_pct": 0.003,
        "quality_filtering": "Scene Classification Layer (SCL) cloud, cloud-shadow, and cirrus masking",
        "derived_index": "Normalized Difference Vegetation Index (NDVI = (B08 - B04) / (B08 + B04))",
        "vegetation_vs_cooling_disclaimer": (
            "NDVI measures photosynthetic active green biomass and canopy density (-1.0 to +1.0). "
            "While dense canopy correlates with localized microclimate shading, NDVI is an ecological "
            "canopy index, NOT a direct physical measurement of air cooling degrees."
        ),
        "source_url": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a"
    },
    "builtup": {
        "dataset_name": "ESA WorldCover 10m 2021 v200 Global Land Cover",
        "product_id": "ESA_WorldCover_10m_2021_v200",
        "publisher": "European Space Agency (ESA) / VITO via Microsoft Planetary Computer",
        "baseline_year": "2021",
        "spatial_resolution": "10 meters",
        "quality_filtering": "Multi-temporal Sentinel-1 and Sentinel-2 algorithm fusion (76.7% global validation accuracy)",
        "target_class": "Class 50: Built-up (artificial surfaces, buildings, paved roads, and urban structures)",
        "source_url": "https://planetarycomputer.microsoft.com/dataset/esa-worldcover"
    }
}


class EnvironmentalService:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_PROCESSED_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_csv_path = self.data_dir / "hyderabad_environmental_indicators_1km.csv"

    @staticmethod
    def _sign_pc_href(href: str) -> str:
        """Obtain signed asset URL from Planetary Computer sign API."""
        sign_url = f"https://planetarycomputer.microsoft.com/api/sas/v1/sign?href={urllib.parse.quote_plus(href)}"
        req = urllib.request.Request(sign_url, headers={"User-Agent": "URBANRISK-Analytics/1.0"})
        with urllib.request.urlopen(req, timeout=12) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data["href"]

    def extract_satellite_indicators(self, save_csv: bool = True) -> pd.DataFrame:
        """
        Samples authoritative remote satellite COGs across all 791 1-km grid cell centroids.
        Applies cloud/quality masking and derives:
        - 2023 MODIS Summer Daytime LST (°C)
        - 2024 Sentinel-2 Pre-Monsoon NDVI
        - 2021 ESA WorldCover Built-Up Land Cover Class (Class 50 indicator)
        """
        if not GRID_BACKBONE_PATH.exists():
            raise FileNotFoundError(f"1-km Grid backbone file not found at: {GRID_BACKBONE_PATH}")

        grid = pd.read_csv(GRID_BACKBONE_PATH)
        if len(grid) != 791:
            raise ValueError(f"Expected 791 grid cells in backbone, found {len(grid)}")

        lons = grid["cell_center_longitude"].tolist()
        lats = grid["cell_center_latitude"].tolist()
        grid_ids = grid["grid_id"].tolist()

        # -------------------------------------------------------------
        # 1. ESA WorldCover 10m Built-Up Extraction
        # -------------------------------------------------------------
        logger.info("Extracting ESA WorldCover 10m built-up classification...")
        signed_wc_url = self._sign_pc_href(ESA_WORLDCOVER_MAP_URL)

        pts_wgs84 = list(zip(lons, lats))
        with rasterio.open(signed_wc_url) as src_wc:
            raw_wc = [v[0] for v in src_wc.sample(pts_wgs84)]

        # Class 50 = Built-up
        is_builtup = [bool(v == 50) for v in raw_wc]
        builtup_class_code = [int(v) for v in raw_wc]

        # -------------------------------------------------------------
        # 2. Sentinel-2 10m Pre-Monsoon NDVI Extraction with SCL Masking
        # -------------------------------------------------------------
        logger.info("Extracting Sentinel-2 10m NDVI and cloud masking...")
        with rasterio.open(SENTINEL2_B04_URL) as src_b04, \
             rasterio.open(SENTINEL2_B08_URL) as src_b08, \
             rasterio.open(SENTINEL2_SCL_URL) as src_scl:

            # Project coordinates from WGS84 to UTM 43N
            xs, ys = rasterio.warp.transform("EPSG:4326", src_b04.crs, lons, lats)
            pts_utm = list(zip(xs, ys))

            raw_b04 = [v[0] for v in src_b04.sample(pts_utm)]
            raw_b08 = [v[0] for v in src_b08.sample(pts_utm)]
            raw_scl = [v[0] for v in src_scl.sample(pts_utm)]

        ndvi_vals = []
        for red, nir, scl in zip(raw_b04, raw_b08, raw_scl):
            # SCL quality filter:
            # 3 = cloud shadow, 8 = cloud medium prob, 9 = cloud high prob, 10 = thin cirrus
            # Valid ground: 4 (vegetation), 5 (bare soils), 6 (water), 7 (unclassified/urban), 11 (snow)
            if scl in [3, 8, 9, 10] or (nir + red) == 0:
                ndvi_vals.append(np.nan)
            else:
                ndvi = (float(nir) - float(red)) / (float(nir) + float(red))
                ndvi_vals.append(round(float(ndvi), 4))

        # -------------------------------------------------------------
        # 3. MODIS Aqua 2023 Summer LST Day Extraction & Quality Filter
        # -------------------------------------------------------------
        logger.info("Extracting updated 2023 MODIS Land Surface Temperature...")
        signed_lst_url = self._sign_pc_href(MODIS_LST_DAY_2023_URL)
        signed_qc_url = self._sign_pc_href(MODIS_QC_DAY_2023_URL)

        with rasterio.open(signed_lst_url) as src_lst, rasterio.open(signed_qc_url) as src_qc:
            xs_m, ys_m = rasterio.warp.transform("EPSG:4326", src_lst.crs, lons, lats)
            pts_modis = list(zip(xs_m, ys_m))

            raw_lst = [v[0] for v in src_lst.sample(pts_modis)]
            raw_qc = [v[0] for v in src_qc.sample(pts_modis)]

        lst_celsius = []
        for lst_dn, qc in zip(raw_lst, raw_qc):
            # QC filter: bits 0-1: 00 = good quality, 01 = other quality, 10/11 = cloud/not produced
            qc_bits = qc & 0b11
            if lst_dn == 0 or qc_bits in [2, 3]:
                lst_celsius.append(np.nan)
            else:
                # Scale factor: 0.02, Convert Kelvin to Celsius
                temp_c = float(lst_dn) * 0.02 - 273.15
                if -10.0 <= temp_c <= 70.0:
                    lst_celsius.append(round(temp_c, 2))
                else:
                    lst_celsius.append(np.nan)

        # Assemble environmental dataframe
        df_env = pd.DataFrame({
            "grid_id": grid_ids,
            "latitude": [round(lat, 5) for lat in lats],
            "longitude": [round(lon, 5) for lon in lons],
            "modis_lst_day_2023_c": lst_celsius,
            "sentinel2_ndvi_2024": ndvi_vals,
            "is_builtup_surface": is_builtup,
            "landcover_class_code": builtup_class_code,
            "thermal_observation_period": "2023-05-25 to 2023-06-01",
            "vegetation_observation_date": "2024-04-27",
            "builtup_baseline_year": "2021",
            "thermal_source_product": "MODIS Aqua 8-Day LST (MYD11A2.061)",
            "vegetation_source_product": "Sentinel-2 MSI Level-2A (10m)",
            "builtup_source_product": "ESA WorldCover 10m v200"
        })

        if save_csv:
            df_env.to_csv(self.output_csv_path, index=False)
            logger.info("Saved environmental indicators to: %s", self.output_csv_path)

        return df_env

    def persist_to_mongodb(self, df_env: pd.DataFrame, db) -> Dict[str, Any]:
        """
        Stores environmental indicators in MongoDB with duplicate-prevention on grid_id.
        Preserves all historical records in dataset_versions and flood collections.
        """
        if db is None:
            raise ConnectionError("MongoDB database connection is unavailable")

        col = db["environmental_indicators"]
        col.create_index([("grid_id", pymongo.ASCENDING)], unique=True)

        catalog_col = db["environmental_catalog"]
        catalog_col.create_index([("dataset_key", pymongo.ASCENDING)], unique=True)

        # 1. Upsert catalog metadata
        now_utc = datetime.now(timezone.utc).isoformat()
        for key, meta in ENVIRONMENTAL_CATALOG_META.items():
            catalog_col.update_one(
                {"dataset_key": key},
                {"$set": {**meta, "ingestion_timestamp": now_utc}},
                upsert=True
            )

        # 2. Bulk upsert 791 indicator records
        bulk_ops = []
        for _, row in df_env.iterrows():
            record = row.to_dict()
            # Convert numpy NaN to None for clean BSON nulls
            clean_record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
            bulk_ops.append(
                pymongo.UpdateOne(
                    {"grid_id": clean_record["grid_id"]},
                    {"$set": clean_record},
                    upsert=True
                )
            )

        res = col.bulk_write(bulk_ops, ordered=False)

        return {
            "status": "success",
            "collection": "environmental_indicators",
            "matched_count": res.matched_count,
            "modified_count": res.modified_count,
            "upserted_count": len(res.upserted_ids),
            "total_documents": col.count_documents({}),
            "catalog_datasets_registered": catalog_col.count_documents({})
        }

    def get_environmental_summary(self, db) -> Dict[str, Any]:
        """Returns metadata, observation dates, coverage, and statistics for all products."""
        summary = {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "catalog": ENVIRONMENTAL_CATALOG_META,
            "grid_integration_status": self.get_grid_integration_status()
        }

        if db is not None and "environmental_indicators" in db.list_collection_names():
            col = db["environmental_indicators"]
            total = col.count_documents({})

            lst_docs = col.find({"modis_lst_day_2023_c": {"$ne": None}})
            lst_vals = [d["modis_lst_day_2023_c"] for d in lst_docs]

            ndvi_docs = col.find({"sentinel2_ndvi_2024": {"$ne": None}})
            ndvi_vals = [d["sentinel2_ndvi_2024"] for d in ndvi_docs]

            builtup_count = col.count_documents({"is_builtup_surface": True})

            summary["indicators_coverage"] = {
                "total_grid_cells": total,
                "modis_lst_2023": {
                    "valid_cells": len(lst_vals),
                    "mean_lst_day_c": round(float(np.mean(lst_vals)), 2) if lst_vals else None,
                    "min_lst_day_c": round(float(np.min(lst_vals)), 2) if lst_vals else None,
                    "max_lst_day_c": round(float(np.max(lst_vals)), 2) if lst_vals else None
                },
                "sentinel2_ndvi_2024": {
                    "valid_cells": len(ndvi_vals),
                    "mean_ndvi": round(float(np.mean(ndvi_vals)), 3) if ndvi_vals else None,
                    "min_ndvi": round(float(np.min(ndvi_vals)), 3) if ndvi_vals else None,
                    "max_ndvi": round(float(np.max(ndvi_vals)), 3) if ndvi_vals else None
                },
                "esa_builtup_2021": {
                    "builtup_cells_count": builtup_count,
                    "total_grid_cells": total,
                    "builtup_cells_pct": round((builtup_count / total) * 100.0, 1) if total else 0.0,
                    "metric_label": "Grid cells containing built-up land",
                    "metric_display": f"{builtup_count} / {total} ({round((builtup_count / total) * 100.0, 1)}%)",
                    "methodology": "Point-sampled 10m ESA WorldCover Class 50 at cell centroids; indicates cell-level built-up presence, not citywide area-weighted land cover fraction."
                }
            }

        return summary

    @staticmethod
    def get_grid_integration_status() -> Dict[str, Any]:
        """Explains dynamic grid non-interference boundary."""
        return {
            "grid_weights_modified": False,
            "historical_baselines_overwritten": False,
            "decision_rationale": (
                "Updated environmental indicators (2023 MODIS LST, 2024 Sentinel-2 NDVI, and 2021 ESA WorldCover Built-up) "
                "are integrated as dedicated additive environmental layers. To maintain Phase 1 & Phase 2 baseline scoring stability, "
                "the approved IUPS scoring weights (35% flood, 35% heat, 15% infra, 15% road) and thresholds remain 100% unaltered. "
                "Historical 2018 MODIS and 2003-2018 Yale records are preserved uncorrupted for longitudinal comparison."
            )
        }
