import os
import csv
import re

# ----------------- CONFIGURATION ----------------- #
TARGET_DIR = "/home/wildbill/adult_clipart_factory/completed_bundles"
OUTPUT_CSV = "products.csv"
DEFAULT_PRICE = "15.00"  # Set your standard product price here
DEFAULT_DESC = "High-quality premium digital asset pack collection bundle."
# ------------------------------------------------- #

def clean_title(filename):
    # Remove file extension
    name_without_ext = os.path.splitext(filename)[0]
    # Replace underscores, hyphens, or dots with spaces
    spaced_name = re.sub(r'[_.\-]+', ' ', name_without_ext)
    # Capitalize the words nicely
    return spaced_name.strip().title()

def generate_csv():
    print(f"📂 Scanning directory: {TARGET_DIR}")
    
    if not os.path.exists(TARGET_DIR):
        print(f"❌ Error: The directory '{TARGET_DIR}' does not exist.")
        return

    # Gather all files in the folder
    all_files = os.listdir(TARGET_DIR)
    
    # Filter out zip files and image files
    zip_files = [f for f in all_files if f.lower().endswith('.zip')]
    image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
    image_files = [f for f in all_files if f.lower().endswith(image_extensions)]

    print(f"📦 Found {len(zip_files)} ZIP files and {len(image_files)} potential preview images.")

    products_data = []

    for zip_file in sorted(zip_files):
        base_name = os.path.splitext(zip_file)[0]
        title = clean_title(zip_file)
        
        # Smart Matching: Look for an image that shares the same base name
        preview_file = ""
        for img in image_files:
            img_base = os.path.splitext(img)[0]
            if img_base.lower() == base_name.lower():
                preview_file = img
                break
        
        # Fallback: If no direct match, check if the image name is "contained" within it
        if not preview_file:
            for img in image_files:
                img_base = os.path.splitext(img)[0]
                if img_base.lower() in base_name.lower() or base_name.lower() in img_base.lower():
                    preview_file = img
                    break

        # If still no preview image found, alert the user but add the row anyway
        if not preview_file:
            print(f"⚠️ Warning: No matching preview image found for '{zip_file}'")
            preview_file = "MISSING_PREVIEW.png"

        products_data.append({
            "Title": title,
            "Description": DEFAULT_DESC,
            "Price": DEFAULT_PRICE,
            "Zip_URL": zip_file,       # Saves just the filename for upload_local_zips.py
            "Preview_URL": preview_file # Saves just the filename for upload_local_zips.py
        })

    # Write everything to your products.csv spreadsheet
    headers = ["Title", "Description", "Price", "Zip_URL", "Preview_URL"]
    with open(OUTPUT_CSV, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(products_data)

    print(f"\n🏁 Success! Created '{OUTPUT_CSV}' with {len(products_data)} matched product rows.")

if __name__ == "__main__":
    generate_csv()
