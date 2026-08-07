import argparse
import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PRODUCTS_JSON = BASE_DIR / "products.json"
DEFAULT_MIGRATION_CSV = BASE_DIR / "gumroad_permalink_migration.csv"

def load_catalog(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("products.json must contain a top-level list")
    return payload

def load_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))

def sync_catalog(products_json: Path, migration_csv: Path, dry_run: bool):
    records = load_catalog(products_json)
    rows = load_rows(migration_csv)
    updated = 0
    skipped = 0
    mismatched = 0

    for row in rows:
        try:
            idx = int(str(row.get("row_index") or "0"))
        except ValueError:
            skipped += 1
            continue

        if idx <= 0 or idx > len(records):
            skipped += 1
            continue

        rec = records[idx - 1]
        current_in_csv = str(row.get("current_gumroad_url") or "").strip()
        target_url = str(row.get("target_gumroad_url") or "").strip()
        status = str(row.get("status") or "").strip().lower()

        if not target_url:
            skipped += 1
            continue

        # Defining current_local first so the following check works properly
        current_local = str(rec.get("Gumroad_URL") or "").strip()

        if current_local and current_in_csv and current_local != current_in_csv:
            mismatched += 1

        if current_local == target_url:
            skipped += 1
            continue

        rec["Gumroad_URL"] = target_url
        updated += 1

    print("Catalog permalink sync summary")
    print("-" * 38)
    print(f"records: {len(records)}")
    print(f"csv_rows: {len(rows)}")
    print(f"updated: {updated}")
    print(f"skipped: {skipped}")
    print(f"mismatched_rows: {mismatched}")
    print(f"mode: {'DRY-RUN' if dry_run else 'WRITE'}")

    if not dry_run:
        with products_json.open("w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=4)
            handle.write("\n")
        print(f"saved: {products_json}")

def main():
    parser = argparse.ArgumentParser(description="Apply Gumroad permalink migration CSV to local products.json")
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS_JSON, help="Path to products.json")
    parser.add_argument("--csv", type=Path, default=DEFAULT_MIGRATION_CSV, help="Path to migration CSV")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    sync_catalog(args.products, args.csv, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
