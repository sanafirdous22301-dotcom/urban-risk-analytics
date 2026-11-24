"""
scripts/recalculate_priority_grid.py
Administrative execution script for Phase 2 IUPS priority grid recalculation.
"""

import sys
import json
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.grid_recalculation_service import GridRecalculationService, DEFAULT_WEIGHTS

def main():
    parser = argparse.ArgumentParser(description="Recalculate Hyderabad 1-km IUPS priority grid.")
    parser.add_argument("--dry-run", action="store_true", help="Calculate without persisting to MongoDB.")
    parser.add_argument("--mongo-uri", default="mongodb://127.0.0.1:27017/", help="MongoDB connection URI.")
    parser.add_argument("--db-name", default="urban_risk_db", help="Target database name.")
    args = parser.parse_args()

    service = GridRecalculationService()
    print("Executing IUPS Priority Grid Recalculation...")
    print(f" - Active Weights: {DEFAULT_WEIGHTS}")
    print(f" - Persistence: {'DRY RUN (No DB Write)' if args.dry_run else 'Enabled (urban_risk_db.priority_grid_cells)'}")

    res = service.recalculate(
        persist_to_db=not args.dry_run,
        mongo_uri=args.mongo_uri,
        db_name=args.db_name
    )

    print("\nRECALCULATION COMPLETE:")
    print(f" - Status:             {res['status']}")
    print(f" - Timestamp:          {res['calculation_timestamp']}")
    print(f" - Total Grid Cells:   {res['total_cells']}")
    print(f" - Scored Cells:       {res['scored_cells']}")
    print(f" - Unscored Cells:     {res['unscored_cells']} (Insufficient hazard evidence)")
    print(f" - Score Range:        {res['score_statistics']['min_score']} to {res['score_statistics']['max_score']}")
    print(f" - Mean Score:         {res['score_statistics']['mean_score']}")
    print(f" - Distribution:       {res['screening_distribution']}")

    if "mongodb_storage" in res:
        storage = res["mongodb_storage"]
        print("\nMONGODB STORAGE VERIFICATION:")
        print(f" - Target Collection:  {storage['collection']}")
        print(f" - Matched Count:      {storage['matched_count']}")
        print(f" - Modified Count:     {storage['modified_count']}")
        print(f" - Upserted Count:     {storage['upserted_count']}")
        print(f" - Total Collection Documents: {storage['total_collection_documents']}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
