import os
import shutil
import csv
import json
import re

from deep_sweep_and_build import build_bundle_preview
from gumroad_utils import build_gumroad_url

# ----------------- CONFIGURATION ----------------- #
SOURCE_DIR = "/home/wildbill/adult_clipart_factory/gumroad_ready_assets"
OUTPUT_DIR = os.environ.get("VAULT_FINAL_STORE_DIR", "/run/media/wildbill/storage/completed_bundles")
OUTPUT_CSV = "products.csv"
OUTPUT_JSON = "products.json"  
DEFAULT_PRICE = "15.00"
DEFAULT_DESC = "High-quality premium digital asset pack collection bundle."
MIN_FILES_PER_ZIP = 100
# ------------------------------------------------- #

def clean_title(folder_name):
    spaced_name = re.sub(r'[_.\-]+', ' ', folder_name)
    return spaced_name.strip().title()


def collect_bundle_images(folder_path):
    image_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    image_paths = []

    for root, _, files in os.walk(folder_path):
        for filename in sorted(files):
            if filename.lower().endswith(image_extensions):
                image_paths.append(os.path.join(root, filename))

    return image_paths

def process_assets():
    print(f"📂 Scanning assets folder: {SOURCE_DIR}")
    if not os.path.exists(SOURCE_DIR):
        print(f"❌ Error: Source folder '{SOURCE_DIR}' not found.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    bundle_folders = [d for d in os.listdir(SOURCE_DIR) if os.path.isdir(os.path.join(SOURCE_DIR, d))]
    print(f"📦 Found {len(bundle_folders)} unzipped asset folders to process.")

    products_data = []

    for index, folder in enumerate(sorted(bundle_folders), start=1):
        folder_path = os.path.join(SOURCE_DIR, folder)
        clean_name = clean_title(folder)
        
        zip_filename = f"{folder}.zip"
        target_zip_path = os.path.join(OUTPUT_DIR, zip_filename)
        
        print(f"\n⚡ [{index}/{len(bundle_folders)}] Processing bundle folder: '{folder}'...")

        # 1. SMART PREVIEW EXTRACTION
        preview_filename = "MISSING_PREVIEW.jpg"
        images_inside = collect_bundle_images(folder_path)

        if len(images_inside) < MIN_FILES_PER_ZIP:
            print(f"   ⏭️ Skipping '{folder}' because it only has {len(images_inside)} images.")
            continue

        if images_inside:
            preview_filename = f"{folder}.jpg"
            target_img_path = os.path.join(OUTPUT_DIR, preview_filename)

            if build_bundle_preview(images_inside, target_img_path):
                print(f"   🎨 Built stitched preview: {preview_filename} ({len(images_inside)} images)")
            else:
                preview_filename = "MISSING_PREVIEW.jpg"
                print(f"   ⚠️ Warning: Could not build preview for '{folder}'")
        else:
            print(f"   ⚠️ Warning: No cover image found inside '{folder}'")

        # 2. AUTOMATIC FOLDER COMPRESSION (ZIPPING)
        if not os.path.exists(target_zip_path):
            print(f"   🤐 Compressing folder into a secure .zip file...")
            shutil.make_archive(os.path.join(OUTPUT_DIR, folder), 'zip', SOURCE_DIR, folder)
            print(f"   ✅ Created: {zip_filename}")
        else:
            print(f"   ℹ️ Zip file already exists, skipping compression step.")

        # 3. RECORD DATA
        products_data.append({
            "Title": clean_name,
            "Description": DEFAULT_DESC,
            "Price": DEFAULT_PRICE,
            "Zip_URL": zip_filename,
            "Preview_URL": preview_filename,
            "Gumroad_URL": build_gumroad_url(clean_name),
        })

    # Write CSV Master Catalog
    headers = ["Title", "Description", "Price", "Zip_URL", "Preview_URL"]
    with open(OUTPUT_CSV, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(products_data)

    # Write JSON data explicitly into your website folder directory
    with open(OUTPUT_JSON, mode="w", encoding="utf-8") as f:
        json.dump(products_data, f, indent=4)

    print(f"\n🏁 Complete! Catalog metadata saved to '{OUTPUT_CSV}' and inventory dataset written to '{OUTPUT_JSON}'.")

if __name__ == "__main__":
    process_assets()
