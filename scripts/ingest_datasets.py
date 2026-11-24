#!/usr/bin/env python3
"""
CLI Dataset Ingestion Utility for URBANRISK Hyderabad.
Allows administrators to manually run dataset ingestions, preview data (dry-run),
inspect dataset statuses, and review ingestion history.

Usage:
    python scripts/ingest_datasets.py --status
    python scripts/ingest_datasets.py --history
    python scripts/ingest_datasets.py --dataset weather [--force] [--dry-run]
    python scripts/ingest_datasets.py --dataset modis [--force] [--dry-run]
    python scripts/ingest_datasets.py --dataset sentinel2 [--force] [--dry-run]
    python scripts/ingest_datasets.py --dataset worldcover [--force] [--dry-run]
    python scripts/ingest_datasets.py --dataset floods [--force] [--dry-run]
    python scripts/ingest_datasets.py --dataset all [--force] [--dry-run]
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.ingestion_service import DatasetIngestionService, DATASET_CADENCE_CONFIG


def main():
    parser = argparse.ArgumentParser(description="URBANRISK Dataset Ingestion Utility")
    parser.add_argument(
        "--dataset",
        choices=["weather", "modis", "sentinel2", "worldcover", "floods", "all"],
        help="Target dataset to ingest"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass publishing cadence interval checks"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview data without writing to database"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display operational status and cadence for all supported datasets"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Display recent ingestion runs history"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit number of history items to show (default: 10)"
    )

    args = parser.parse_args()
    service = DatasetIngestionService()

    if args.status:
        print("\n=== URBANRISK DATASET STATUS & CADENCE ===")
        statuses = service.get_datasets_status()
        for item in statuses:
            last_run = item.get("last_run")
            last_status = last_run.get("status") if last_run else "NEVER RUN"
            last_time = str(last_run.get("completed_at")) if last_run else "N/A"
            print(f"- [{item['dataset_key']}] {item['display_name']}")
            print(f"  Provider: {item['provider']}")
            print(f"  Cadence: {item['cadence_description']} (Min interval: {item['min_interval_hours']}h)")
            print(f"  Last Run: {last_status} at {last_time}\n")
        return

    if args.history:
        print(f"\n=== URBANRISK RECENT INGESTION RUNS (Last {args.limit}) ===")
        runs = service.get_ingestion_history(limit=args.limit)
        if not runs:
            print("No ingestion runs recorded.")
            return
        for r in runs:
            status = r.get("status")
            badge = "[OK]" if status == "success" else f"[{status.upper()}]"
            print(f"{badge} {r.get('run_id')} | {r.get('dataset_key')} | {r.get('trigger_type')}")
            print(f"     Time: {r.get('completed_at')} | Duration: {r.get('duration_seconds')}s")
            print(f"     Fetched: {r.get('records_fetched')} | Upserted: {r.get('records_upserted')} | Rejected: {r.get('records_rejected')}")
            if r.get("error_message"):
                print(f"     Error: {r.get('error_message')}")
            print()
        return

    if not args.dataset:
        parser.print_help()
        sys.exit(1)

    print(f"\n[URBANRISK INGESTION] Triggering ingestion for: {args.dataset}")
    print(f"  Mode: {'DRY RUN (no DB writes)' if args.dry_run else 'LIVE PERSISTENCE'}")
    print(f"  Force: {args.force}\n")

    res = service.trigger_ingestion(
        dataset_key=args.dataset,
        trigger_type="manual_cli",
        force=args.force,
        dry_run=args.dry_run
    )

    print("\n[RESULT]")
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
