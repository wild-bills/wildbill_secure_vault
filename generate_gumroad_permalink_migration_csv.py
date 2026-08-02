import argparse
import csv
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PRODUCTS_JSON = BASE_DIR / "products.json"
DEFAULT_DB_PATH = BASE_DIR / "database" / "store.db"
DEFAULT_OUTPUT_CSV = BASE_DIR / "gumroad_permalink_migration.csv"
GUMROAD_BASE = "https://wildbill.gumroad.com/l"


def slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    out = []
    dash = False
    for ch in text:
        if ch.isalnum() or ch == "-":
            out.append(ch)
            dash = False
        else:
            if not dash:
                out.append("-")
                dash = True
    slug = "".join(out).strip("-")
    return slug


def normalize_name(value: str) -> str:
    return slugify(value).replace("-", "")


def extract_permalink(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    path = parsed.path.rstrip("/")
    if not path:
        return ""
    return path.split("/")[-1]


def load_products(products_path: Path):
    with products_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("products.json must contain a top-level list")
    return payload


def load_db_mappings(db_path: Path):
    by_zip = {}
    by_name = {}

    if not db_path.exists():
        return by_zip, by_name

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT sku, name, zip_filename FROM products").fetchall()
    conn.close()

    for row in rows:
        sku = str(row["sku"] or "").strip()
        if not sku:
            continue

        zip_name = str(row["zip_filename"] or "").strip().lower()
        if zip_name:
            by_zip[zip_name] = sku
            if zip_name.endswith(".zip"):
                by_zip[zip_name[:-4]] = sku

        db_name = str(row["name"] or "").strip()
        if db_name:
            by_name[normalize_name(db_name)] = sku

    return by_zip, by_name


def get_zip_name(record):
    zip_path = str(record.get("Zip_Path") or "").strip()
    if zip_path:
        return Path(zip_path).name

    zip_url = str(record.get("Zip_URL") or "").strip()
    if zip_url:
        return Path(zip_url).name

    return ""


def resolve_sku(record, by_zip, by_name):
    direct = str(record.get("SKU") or record.get("sku") or "").strip()
    if direct:
        return direct, "record"

    zip_name = get_zip_name(record).lower()
    if zip_name and zip_name in by_zip:
        return by_zip[zip_name], "db_zip_filename"

    title = str(record.get("Title") or record.get("name") or "").strip()
    title_key = normalize_name(title)
    if title_key and title_key in by_name:
        return by_name[title_key], "db_name"

    return "", "unresolved"


def build_target_url(target_permalink: str) -> str:
    if not target_permalink:
        return ""
    return f"{GUMROAD_BASE}/{target_permalink}"


def generate(products_path: Path, db_path: Path, output_csv: Path, only_updates: bool):
    rows = load_products(products_path)
    by_zip, by_name = load_db_mappings(db_path)

    prepared = []
    stats = {
        "total": 0,
        "already_sku": 0,
        "needs_update": 0,
        "missing_url": 0,
        "missing_sku": 0,
    }

    for idx, row in enumerate(rows, start=1):
        title = str(row.get("Title") or row.get("name") or "").strip()
        gumroad_url = str(row.get("Gumroad_URL") or "").strip()
        current_permalink = extract_permalink(gumroad_url)
        zip_name = get_zip_name(row)
        sku, sku_source = resolve_sku(row, by_zip, by_name)
        target_permalink = slugify(sku)
        target_url = build_target_url(target_permalink)

        status = ""
        notes = ""

        if not gumroad_url:
            status = "missing_url"
            notes = "No Gumroad_URL in products.json"
        elif not sku:
            status = "missing_sku"
            notes = "Could not resolve SKU from record or database"
        elif current_permalink == target_permalink:
            status = "already_sku"
            notes = "Already uses SKU permalink"
        else:
            status = "needs_update"
            notes = "Update Gumroad permalink to target_sku_permalink"

        stats["total"] += 1
        if status in stats:
            stats[status] += 1

        output_row = {
            "row_index": idx,
            "title": title,
            "zip_filename": zip_name,
            "sku": sku,
            "sku_source": sku_source,
            "current_gumroad_url": gumroad_url,
            "current_permalink": current_permalink,
            "target_sku_permalink": target_permalink,
            "target_gumroad_url": target_url,
            "status": status,
            "notes": notes,
        }

        if only_updates and status != "needs_update":
            continue

        prepared.append(output_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_index",
                "title",
                "zip_filename",
                "sku",
                "sku_source",
                "current_gumroad_url",
                "current_permalink",
                "target_sku_permalink",
                "target_gumroad_url",
                "status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(prepared)

    print("Gumroad permalink migration CSV generated")
    print("-" * 46)
    print(f"output:        {output_csv}")
    print(f"total:         {stats['total']}")
    print(f"already_sku:   {stats['already_sku']}")
    print(f"needs_update:  {stats['needs_update']}")
    print(f"missing_sku:   {stats['missing_sku']}")
    print(f"missing_url:   {stats['missing_url']}")
    if only_updates:
        print(f"rows_written:  {len(prepared)} (needs_update only)")
    else:
        print(f"rows_written:  {len(prepared)}")


def main():
    parser = argparse.ArgumentParser(description="Generate Gumroad permalink migration CSV")
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS_JSON, help="Path to products.json")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to store.db")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CSV, help="Output CSV path")
    parser.add_argument(
        "--only-updates",
        action="store_true",
        help="Write only rows that need permalink updates",
    )
    args = parser.parse_args()

    generate(
        products_path=args.products,
        db_path=args.db,
        output_csv=args.output,
        only_updates=args.only_updates,
    )


if __name__ == "__main__":
    main()
