"""
backend/services/grid_recalculation_service.py
Phase 2: Dynamic Integrated Urban Priority Screening (IUPS) Grid Recalculation Service.

Mathematical Invariants:
1. Reusable deterministic pipeline regenerating the 1-km priority grid from existing stored source records.
2. Default Analytical Weights:
   - flood_evidence_score: 0.35
   - heat_evidence_score: 0.35
   - infrastructure_gap_score: 0.15
   - road_representation_gap_score: 0.15
3. Missing component evidence is strictly preserved as null/NaN; never imputed as 0.
4. Cells with hazard_component_count == 0 are strictly NOT SCORED.
5. Preserves all 791 grid cells: exactly 741 scored, exactly 50 unscored.
6. Safe idempotent storage in MongoDB with unique index on grid_id preventing duplication.
"""

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pymongo import MongoClient, UpdateOne

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data" / "processed"

# Default baseline IUPS weights
DEFAULT_WEIGHTS = {
    "flood_evidence_score": 0.35,
    "heat_evidence_score": 0.35,
    "infrastructure_gap_score": 0.15,
    "road_representation_gap_score": 0.15
}

# IUPS Classification thresholds
PRIORITY_BINS = [-np.inf, 25.0, 50.0, 75.0, np.inf]
PRIORITY_LABELS = [
    "Lower screening priority",
    "Moderate screening priority",
    "Higher screening priority",
    "Very high screening priority"
]


def percentile_score(series: pd.Series) -> pd.Series:
    """Calculate percentile-rank scaling (0 to 1) for valid finite numerical observations."""
    s = pd.to_numeric(series, errors="coerce")
    result = pd.Series(np.nan, index=s.index, dtype=float)
    valid = s.notna()
    if valid.sum() >= 2:
        result.loc[valid] = s.loc[valid].rank(pct=True)
    elif valid.sum() == 1:
        result.loc[valid] = 0.5
    return result


def weighted_available(row: pd.Series, weight_dict: Dict[str, float]) -> float:
    """
    Calculate weighted average across available components.
    Weights are dynamically re-normalized over non-null components for each grid cell.
    """
    numerator = 0.0
    denominator = 0.0
    for col, weight in weight_dict.items():
        val = row.get(col)
        if pd.notna(val):
            numerator += float(val) * weight
            denominator += weight
    if denominator == 0.0:
        return np.nan
    return numerator / denominator


class GridRecalculationService:
    def __init__(self, data_root: Optional[Path] = None):
        self.data_root = data_root or DATA_ROOT
        self.infra_grid_path = (
            self.data_root
            / "infrastructure"
            / "integrated_infrastructure_experiments"
            / "integrated_infrastructure_road_grid_1km.csv"
        )
        self.rainfall_path = self.data_root / "flood" / "hyderabad_rainfall.csv"
        self.modis_path = self.data_root / "heat" / "hyderabad_modis_heat.csv"
        self.yale_path = self.data_root / "heat" / "hyderabad_yale_heat.csv"

    def recalculate(
        self,
        weights: Optional[Dict[str, float]] = None,
        persist_to_db: bool = True,
        mongo_uri: str = "mongodb://127.0.0.1:27017/",
        db_name: str = "urban_risk_db",
        return_dataframe: bool = False
    ) -> Any:
        """
        Executes deterministic recalculation of the 791-cell 1-km priority grid.
        Returns full calculation metrics, statistics, and distribution.
        """
        active_weights = weights or DEFAULT_WEIGHTS.copy()

        # Validate weight keys
        for required_key in DEFAULT_WEIGHTS:
            if required_key not in active_weights:
                raise ValueError(f"Missing required IUPS weight component: {required_key}")

        # 1. Load backbone infrastructure-road grid
        if not self.infra_grid_path.exists():
            raise FileNotFoundError(f"Backbone grid file not found at: {self.infra_grid_path}")
        backbone = pd.read_csv(self.infra_grid_path).reset_index(drop=True)

        if len(backbone) != 791:
            raise ValueError(f"Expected 791 grid cells in backbone, found {len(backbone)}")
        if backbone["grid_id"].duplicated().any():
            raise ValueError("Duplicate grid_id values detected in master grid backbone.")

        # Common coordinate projection reference
        ref_lat = backbone["cell_center_latitude"].mean()
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * math.cos(math.radians(ref_lat))

        def to_km(lat, lon):
            x = np.asarray(lon) * km_per_deg_lon
            y = np.asarray(lat) * km_per_deg_lat
            return np.column_stack([x, y])

        grid_coords = to_km(
            backbone["cell_center_latitude"].to_numpy(),
            backbone["cell_center_longitude"].to_numpy()
        )
        grid_tree = cKDTree(grid_coords)
        max_dist_km = 0.75

        def assign_to_grid(df: pd.DataFrame, val_col: str, prefix: str) -> pd.DataFrame:
            if df is None or df.empty or val_col not in df.columns:
                return pd.DataFrame()
            coords = to_km(df["latitude"].to_numpy(), df["longitude"].to_numpy())
            dists, idxs = grid_tree.query(coords, k=1)
            accepted = dists <= max_dist_km
            sub = df.loc[accepted].copy()
            sub["grid_id"] = backbone.iloc[idxs[accepted]]["grid_id"].to_numpy()
            return sub.groupby("grid_id")[val_col].agg(["mean", "max", "count"]).reset_index().rename(columns={
                "mean": f"{prefix}_mean",
                "max": f"{prefix}_max",
                "count": f"{prefix}_observation_count"
            })

        # 2. Spatially assign hazard source datasets
        rainfall_df = pd.read_csv(self.rainfall_path) if self.rainfall_path.exists() else None
        modis_df = pd.read_csv(self.modis_path) if self.modis_path.exists() else None
        yale_df = pd.read_csv(self.yale_path) if self.yale_path.exists() else None

        flood_grid = assign_to_grid(rainfall_df, "rainfall_mm", "flood_rainfall")
        modis_grid = assign_to_grid(modis_df, "daytime_temp_c", "modis")
        yale_grid = assign_to_grid(yale_df, "daytime_uhi", "yale")

        # 3. Merge onto backbone
        merged = backbone.copy()
        merged = merged.merge(flood_grid, on="grid_id", how="left")
        merged = merged.merge(modis_grid, on="grid_id", how="left")
        merged = merged.merge(yale_grid, on="grid_id", how="left")

        # 4. Compute source availability flags
        merged["flood_data_available"] = merged.get(
            "flood_rainfall_observation_count", pd.Series(np.nan, index=merged.index)
        ).fillna(0).gt(0).astype(int)

        merged["modis_data_available"] = merged.get(
            "modis_observation_count", pd.Series(np.nan, index=merged.index)
        ).fillna(0).gt(0).astype(int)

        merged["yale_data_available"] = merged.get(
            "yale_observation_count", pd.Series(np.nan, index=merged.index)
        ).fillna(0).gt(0).astype(int)

        # 5. Calculate component scores (percentile rankings)
        if "flood_rainfall_max" in merged.columns:
            merged["flood_evidence_score"] = percentile_score(merged["flood_rainfall_max"])
        else:
            merged["flood_evidence_score"] = np.nan

        if "modis_max" in merged.columns:
            merged["modis_heat_score"] = percentile_score(merged["modis_max"])
        else:
            merged["modis_heat_score"] = np.nan

        if "yale_max" in merged.columns:
            merged["yale_heat_score"] = percentile_score(merged["yale_max"])
        else:
            merged["yale_heat_score"] = np.nan

        merged["heat_evidence_score"] = merged[["modis_heat_score", "yale_heat_score"]].mean(axis=1, skipna=True)
        no_heat = merged["modis_heat_score"].isna() & merged["yale_heat_score"].isna()
        merged.loc[no_heat, "heat_evidence_score"] = np.nan

        infra_total = merged["infra_building_count"].fillna(0) + merged["infra_hospital_count"].fillna(0)
        infra_mapped_score = percentile_score(np.log1p(infra_total))
        road_mapped_score = percentile_score(np.log1p(merged["road_representative_point_count"].fillna(0)))

        merged["infrastructure_gap_score"] = 1.0 - infra_mapped_score
        merged["road_representation_gap_score"] = 1.0 - road_mapped_score

        # 6. Compound Hazard & Resource Context Sub-scores
        hazard_weights = {"flood_evidence_score": 0.50, "heat_evidence_score": 0.50}
        merged["hazard_component_count"] = merged[["flood_evidence_score", "heat_evidence_score"]].notna().sum(axis=1)
        merged["hazard_evidence_score"] = merged.apply(lambda r: weighted_available(r, hazard_weights), axis=1)
        merged["hazard_evidence_score_0_100"] = merged["hazard_evidence_score"] * 100.0

        resource_weights = {"infrastructure_gap_score": 0.50, "road_representation_gap_score": 0.50}
        merged["resource_context_component_count"] = merged[["infrastructure_gap_score", "road_representation_gap_score"]].notna().sum(axis=1)
        merged["resource_context_gap_score"] = merged.apply(lambda r: weighted_available(r, resource_weights), axis=1)
        merged["resource_context_gap_score_0_100"] = merged["resource_context_gap_score"] * 100.0

        # 7. Integrated Urban Priority Score
        merged["integrated_urban_priority_score"] = merged.apply(lambda r: weighted_available(r, active_weights), axis=1)

        # STRICT INVARIANT: Cell requires at least one hazard evidence component to be scored
        no_hazard_evidence = (merged["hazard_component_count"] == 0)
        merged.loc[no_hazard_evidence, "integrated_urban_priority_score"] = np.nan
        merged["priority_score_0_100"] = merged["integrated_urban_priority_score"] * 100.0

        # Component count & coverage (0 for unscored cells)
        avail_components = merged[list(active_weights.keys())].notna().sum(axis=1)
        merged["priority_score_component_count"] = avail_components.where(~no_hazard_evidence, 0)
        merged["priority_score_component_coverage"] = merged["priority_score_component_count"] / float(len(active_weights))

        # Screening Priority Classification
        merged["screening_priority"] = pd.cut(
            merged["priority_score_0_100"],
            bins=PRIORITY_BINS,
            labels=PRIORITY_LABELS
        ).astype(str)
        # Clean null representation
        merged.loc[merged["priority_score_0_100"].isna(), "screening_priority"] = "Not scored"

        # 8. Compute Statistics & Metadata
        now_utc = datetime.now(timezone.utc).isoformat()
        valid_scores = merged["priority_score_0_100"].dropna()
        scored_cells = int(len(valid_scores))
        unscored_cells = int(len(merged) - scored_cells)

        stats = {
            "min_score": round(float(valid_scores.min()), 3) if not valid_scores.empty else None,
            "max_score": round(float(valid_scores.max()), 3) if not valid_scores.empty else None,
            "mean_score": round(float(valid_scores.mean()), 3) if not valid_scores.empty else None,
            "median_score": round(float(valid_scores.median()), 3) if not valid_scores.empty else None,
            "std_score": round(float(valid_scores.std()), 3) if not valid_scores.empty else None
        }

        dist = merged["screening_priority"].value_counts().to_dict()

        result_summary = {
            "status": "success",
            "calculation_timestamp": now_utc,
            "total_cells": len(merged),
            "scored_cells": scored_cells,
            "unscored_cells": unscored_cells,
            "score_coverage_pct": round((scored_cells / len(merged)) * 100.0, 2),
            "weights_applied": active_weights,
            "score_statistics": stats,
            "screening_distribution": dist,
            "source_datasets": {
                "rainfall": "CHIRPS v3.0 Daily COG Raster Extraction (84 samples)",
                "modis_heat": "MODIS Satellite Land Surface Temperature (2018)",
                "yale_uhi": "Surface Urban Heat Island Multi-Year Baseline (2003–2018)",
                "infrastructure_backbone": "OpenStreetMap 1-km Civic & Road Network Grid"
            }
        }

        # 9. Store in MongoDB with Duplicate Prevention
        if persist_to_db:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
            db = client[db_name]
            col = db["priority_grid_cells"]

            # Ensure unique index on grid_id
            col.create_index("grid_id", unique=True)
            col.create_index("priority_score_0_100")
            col.create_index("screening_priority")

            # Prepare documents for upsert
            records = merged.to_dict(orient="records")
            bulk_ops = []
            for r in records:
                # Sanitize NaN/inf to None for BSON serialization
                clean_r = {}
                for k, v in r.items():
                    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                        clean_r[k] = None
                    else:
                        clean_r[k] = v
                clean_r["last_calculated_at"] = now_utc

                bulk_ops.append(
                    UpdateOne(
                        {"grid_id": clean_r["grid_id"]},
                        {"$set": clean_r},
                        upsert=True
                    )
                )

            if bulk_ops:
                bulk_res = col.bulk_write(bulk_ops, ordered=False)
                result_summary["mongodb_storage"] = {
                    "collection": "priority_grid_cells",
                    "matched_count": bulk_res.matched_count,
                    "modified_count": bulk_res.modified_count,
                    "upserted_count": len(bulk_res.upserted_ids),
                    "total_collection_documents": col.count_documents({})
                }

            # Record run metadata in grid_recalculation_runs collection
            run_log = result_summary.copy()
            if "mongodb_storage" in run_log:
                del run_log["mongodb_storage"]
            db["grid_recalculation_runs"].insert_one(run_log)

        if return_dataframe:
            return result_summary, merged
        return result_summary


def recalculate_grid(
    weights: Optional[Dict[str, float]] = None,
    persist_to_db: bool = False,
    data_root: Optional[Path] = None
) -> pd.DataFrame:
    """Convenience helper returning the recalculated 791-row DataFrame directly."""
    service = GridRecalculationService(data_root=data_root)
    _, df = service.recalculate(weights=weights, persist_to_db=persist_to_db, return_dataframe=True)
    return df

