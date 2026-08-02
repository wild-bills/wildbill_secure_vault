import argparse
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PRODUCTS_JSON = BASE_DIR / "products.json"
DEFAULT_DB_PATH = BASE_DIR / "database" / "store.db"


def slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    out = []
    last_dash = False
    for ch in text:
        if ch.isalnum() or ch == "-":
            out.append(ch)
            last_dash = False
        else:
            if not last_dash:
                out.append("-")
                last_dash = True
    slug = "".join(out).strip("-")
    return slug or "item"


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
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("products.json must contain a top-level list")
    return data


def load_db_skus(db_path: Path):
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT sku, zip_filename FROM products").fetchall()
    conn.close()

    mapping = {}
    for row in rows:
        sku = str(row["sku"] or "").strip()
        zip_name = str(row["zip_filename"] or "").strip().lower()
        if zip_name:
            mapping[zip_name] = sku
            if zip_name.endswith(".zip"):
                mapping[zip_name[:-4]] = sku
    return mapping


def get_zip_name(record):
    zip_path = str(record.get("Zip_Path") or "").strip()
    if zip_path:
        return Path(zip_path).name

    zip_url = str(record.get("Zip_URL") or "").strip()
    if zip_url:
        return Path(zip_url).name

    return ""


def validate(products_path: Path, db_path: Path, strict_sku: bool):
    records = load_products(products_path)
    db_skus = load_db_skus(db_path)

    total = len(records)
    sku_match = 0
    legacy_match = 0
    mismatch = 0
    missing_url = 0

    details = []

    for idx, record in enumerate(records, start=1):
        title = str(record.get("Title") or record.get("name") or "").strip()
        gumroad_url = str(record.get("Gumroad_URL") or "").strip()
        permalink = extract_permalink(gumroad_url)

        if not permalink:
            missing_url += 1
            details.append((idx, "MISSING_URL", title, "", "", ""))
            continue

        raw_sku = str(record.get("SKU") or record.get("sku") or "").strip()
        if not raw_sku:
            zip_name = get_zip_name(record).lower()
            raw_sku = db_skus.get(zip_name, "")

        expected_sku_permalink = slugify(raw_sku) if raw_sku else ""
        expected_legacy_permalink = "wildbill_" + slugify(title)

        if expected_sku_permalink and permalink == expected_sku_permalink:
            sku_match += 1
            continue

        if permalink == expected_legacy_permalink:
            legacy_match += 1
            if strict_sku and expected_sku_permalink:
                mismatch += 1
                details.append(
                    (
                        idx,
                        "LEGACY_NOT_SKU",
                        title,
                        permalink,
                        expected_sku_permalink,
                        gumroad_url,
                    )
                )
            continue

        mismatch += 1
        details.append(
            (
                idx,
                "MISMATCH",
                title,
                permalink,
                expected_sku_permalink or expected_legacy_permalink,
                gumroad_url,
            )
        )

    print("Gumroad permalink validation summary")
    print("-" * 40)
    print(f"products:           {total}")
    print(f"sku-match:          {sku_match}")
    print(f"legacy-title-match: {legacy_match}")
    print(f"missing-url:        {missing_url}")
    print(f"mismatch:           {mismatch}")

    if details:
        print("\nDetails")
        print("-" * 40)
        for row in details[:100]:
            idx, status, title, permalink, expected, url = row
            print(f"[{idx}] {status}")
            print(f"  title:    {title}")
            print(f"  permalink:{permalink}")
            print(f"  expected: {expected}")
            if url:
                print(f"  url:      {url}")

        if len(details) > 100:
            print(f"... and {len(details) - 100} more")

    return 1 if (mismatch > 0 or missing_url > 0) else 0


def main():
    parser = argparse.ArgumentParser(description="Validate Gumroad permalink consistency")
    parser.add_argument(
        "--products",
        type=Path,
        default=DEFAULT_PRODUCTS_JSON,
        help="Path to products.json",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to store.db",
    )
    parser.add_argument(
        "--strict-sku",
        action="store_true",
        help="Fail when legacy title-based permalinks are found and SKU is available",
    )
    args = parser.parse_args()

    exit_code = validate(args.products, args.db, args.strict_sku)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
