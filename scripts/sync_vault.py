#!/usr/bin/env python3
"""
Sync Vault Script
Scans the two source directories for .zip files, normalises filenames,
extracts product metadata and upserts records into the SQLite store.
All URLs are hard‑coded to the design subdomain.
"""

import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
# Database location (relative to the project root)
DB_PATH = Path(__file__).resolve().parents[1] / "database" / "store.db"

# Source directories to scan (absolute paths)
SOURCE_ROOTS = [
    Path("/home/wildbill/adult_graphics_factory"),
    Path("/home/wildbill/adult_clipart_factory"),
]

# Hard‑coded price matrix (theme name → price)
PRO_PRICE_MATRIX = {
    "Minimalist High-Contrast Crimson": 39.99,
    "Grimy Streetwear Alternative": 49.99,
}
DEFAULT_PRICE = 89.99

# Base URL for preview images – must stay on the design subdomain
PREVIEW_BASE_URL = "https://design.wildbillsproplans.com/previews"


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------
def clean_filename(name: str) -> str:
    """
    Normalise a filename:
    * lower‑case
    * replace spaces with hyphens
    """
    return name.lower().replace(" ", "-")

def rename_if_needed(zip_path: Path) -> Path:
    """
    If the zip file name contains spaces, rename it on‑disk using the
    normalisation rules and return the new Path.
    """
    if " " in zip_path.name:
        new_name = clean_filename(zip_path.name)
        new_path = zip_path.with_name(new_name)
        zip_path.rename(new_path)
        return new_path
    return zip_path

def extract_bundle_id(sku: str) -> str | None:
    """
    Extract the numeric bundle identifier that follows a 'b' (case‑insensitive)
    in the SKU. Returns None if not found.
    """
    match = re.search(r"b(\d+)", sku, re.IGNORECASE)
    return match.group(1) if match else None

def build_image_url(bundle_id: str | None) -> str:
    """
    Construct the preview image URL. If the bundle ID cannot be determined,
    an empty string is returned – the storefront will simply omit the image.
    """
    if not bundle_id:
        return ""
    return f"{PREVIEW_BASE_URL}/B{bundle_id}_Storefront_cover.png"

def determine_price(theme: str) -> float:
    """
    Look up the price for a given theme; fall back to the default price.
    """
    return PRO_PRICE_MATRIX.get(theme, DEFAULT_PRICE)

def upsert_product(
    conn: sqlite3.Connection,
    name: str,
    theme: str,
    sku: str,
    price: float,
    image_url: str,
    zip_path: Path,
) -> None:
    """
    Insert a new product or replace the existing row with the same SKU.
    """
    conn.execute(
        """
        INSERT INTO products (name, theme, sku, price, image_url, zip_filename)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(sku) DO UPDATE SET
            name=excluded.name,
            theme=excluded.theme,
            price=excluded.price,
            image_url=excluded.image_url,
            zip_filename=excluded.zip_filename;
        """,
        (name, theme, sku, price, image_url, str(zip_path)),
    )
    conn.commit()

def process_zip(zip_path: Path) -> dict:
    """
    Extract all required product metadata from a zip file path.
    Returns a dictionary ready for upserting.
    """
    # Theme is the immediate parent directory name
    theme = zip_path.parent.name

    # Normalise the filename for the SKU (remove .zip, lower‑case, hyphens)
    sku = clean_filename(zip_path.stem)

    # Bundle ID for the preview image
    bundle_id = extract_bundle_id(sku)
    image_url = build_image_url(bundle_id)

    # Pricing based on theme
    price = determine_price(theme)

    # Human‑readable product name (original stem, not normalised)
    name = zip_path.stem

    return {
        "name": name,
        "theme": theme,
        "sku": sku,
        "price": price,
        "image_url": image_url,
        "zip_path": zip_path,
    }

# ----------------------------------------------------------------------
# Main execution
# ----------------------------------------------------------------------
def main() -> None:
    # Ensure the database exists
    conn = sqlite3.connect(DB_PATH)

    for root in SOURCE_ROOTS:
        if not root.is_dir():
            # Skip missing roots – they may be optional in some environments
            continue

        # Recursively find all .zip files
        for zip_path in root.rglob("*.zip"):
            # Normalise the filename on disk if required
            zip_path = rename_if_needed(zip_path)

            # Gather product data
            product = process_zip(zip_path)

            # Upsert into the SQLite store
            upsert_product(
                conn,
                product["name"],
                product["theme"],
                product["sku"],
                product["price"],
                product["image_url"],
                product["zip_path"],
            )

    conn.close()


if __name__ == "__main__":
    # Running the script directly will perform a full sync
    main()