import os
import shutil
import csv
import json
import re

# ----------------- CONFIGURATION ----------------- #
SOURCE_DIR = "/home/wildbill/adult_clipart_factory/gumroad_ready_assets"
OUTPUT_DIR = "/home/wildbill/adult_clipart_factory/completed_bundles"
OUTPUT_CSV = "products.csv"
OUTPUT_JSON = "products.json"  
DEFAULT_PRICE = "15.00"
DEFAULT_DESC = "High-quality premium digital asset pack collection bundle."
# ------------------------------------------------- #

def clean_title(folder_name):
    spaced_name = re.sub(r'[_.\-]+', ' ', folder_name)
    return spaced_name.strip().title()

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
        preview_filename = "MISSING_PREVIEW.png"
        image_extensions = ('.png', '.jpg', '.jpeg', '.webp')
        
        inner_files = os.listdir(folder_path)
        images_inside = [f for f in inner_files if f.lower().endswith(image_extensions)]
        
        if images_inside:
            chosen_img = images_inside[0]
            source_img_path = os.path.join(folder_path, chosen_img)
            
            img_ext = os.path.splitext(chosen_img)[1]
            preview_filename = f"{folder}{img_ext}"
            target_img_path = os.path.join(OUTPUT_DIR, preview_filename)
            
            shutil.copy2(source_img_path, target_img_path)
            print(f"   🎨 Extracted cover preview: {preview_filename}")
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
            "Preview_URL": preview_filename
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
