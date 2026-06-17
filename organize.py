import os
import shutil
import csv
import re

ZIP_SOURCE_DIR = "/home/wildbill/all_combined_zips"
IMG_SOURCE_DIR = "/home/wildbill/adult_clipart_factory/storefront_previews"

OUTPUT_DIR = "/home/wildbill/gumroad_ready_assets"
CSV_OUTPUT_PATH = "/home/wildbill/gumroad_products.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("==================================================")
print("Running Smart File Name Matcher & CSV Builder...")
print("==================================================")

zip_inventory = []
img_inventory = []
IMG_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')

# Helper function to clean filename variants for matching
def normalize_name(filename):
    # Convert to lowercase
    name = filename.lower().strip()
    # Strip common file wrappers/prefixes/suffixes
    name = re.sub(r'^(preview_|thumb_|image_|cover_)', '', name)
    name = re.sub(r'(_preview|_thumb|_image|_cover|_png|_jpg)$', '', name)
    # Remove all non-alphanumeric characters to keep only core words/numbers
    name = re.sub(r'[^a-z0-9]', '', name)
    return name

def get_clean_theme(path_string, default_fallback="general_clipart"):
    folder_name = os.path.basename(path_string)
    if folder_name in ['', 'all_combined_zips', 'storefront_previews', 'adult_clipart_factory']:
        folder_name = os.path.basename(os.path.dirname(path_string))
    
    clean = re.sub(r'[^a-zA-Z0-9_]', '_', folder_name.strip().lower())
    if not clean or clean in ['wildbill', 'factory', 'vault', 'storefront', 'previews']:
        return default_fallback
    return clean

# 2. Inventory all ZIP files
if os.path.exists(ZIP_SOURCE_DIR):
    print(f"Scanning ZIP files in: {ZIP_SOURCE_DIR}")
    for root, _, files in os.walk(ZIP_SOURCE_DIR):
        theme = get_clean_theme(root, "clipart_zips")
        for file in files:
            if file.startswith('.') or not file.lower().endswith('.zip'):
                continue
            name_part, _ = os.path.splitext(file)
            zip_inventory.append({
                'path': os.path.join(root, file),
                'theme': theme,
                'original_name': name_part,
                'match_key': normalize_name(name_part)
            })

# 3. Inventory all Preview Image files
if os.path.exists(IMG_SOURCE_DIR):
    print(f"Scanning Previews in: {IMG_SOURCE_DIR}")
    for root, _, files in os.walk(IMG_SOURCE_DIR):
        for file in files:
            if file.startswith('.') or not file.lower().endswith(IMG_EXTENSIONS):
                continue
            name_part, ext = os.path.splitext(file)
            img_inventory.append({
                'path': os.path.join(root, file),
                'original_name': name_part,
                'match_key': normalize_name(name_part),
                'ext': ext.lower()
            })

print(f"\nFound {len(zip_inventory)} ZIP files and {len(img_inventory)} preview images.")
print("Executing smart matching engine...")

# 4. Perform Smart Matching Matrix
csv_rows = []
theme_counters = {}
matched_total = 0
matched_img_paths = set()

for zip_item in zip_inventory:
    matched_img = None
    z_key = zip_item['match_key']
    
    if not z_key: # Skip blank names
        continue

    # Attempt 1: Exact normalized key match
    for img_item in img_inventory:
        if img_item['path'] in matched_img_paths:
            continue
        if img_item['match_key'] == z_key:
            matched_img = img_item
            break
            
    # Attempt 2: Partial/Contains match if exact fails
    if not matched_img:
        for img_item in img_inventory:
            if img_item['path'] in matched_img_paths:
                continue
            # Check if one core name string is inside the other
            if z_key in img_item['match_key'] or img_item['match_key'] in z_key:
                matched_img = img_item
                break

    # If pair found, execute rename and record tracking entries
    if matched_img:
        matched_img_paths.add(matched_img['path'])
        theme = zip_item['theme']
        
        if theme not in theme_counters:
            theme_counters[theme] = 1
            
        padded_num = f"{theme_counters[theme]:03d}"
        new_base_name = f"{theme}_item_{padded_num}"
        
        new_zip_file = f"{new_base_name}.zip"
        new_img_file = f"{new_base_name}{matched_img['ext']}"
        
        # Copy to production folder workspace
        shutil.copy2(zip_item['path'], os.path.join(OUTPUT_DIR, new_zip_file))
        shutil.copy2(matched_img['path'], os.path.join(OUTPUT_DIR, new_img_file))
        
        # Clean title naming conversion strings
        clean_title = zip_item['original_name'].replace('_', ' ').replace('-', ' ').title()
        if theme.replace('_', ' ') in clean_title.lower():
            display_name = clean_title
        else:
            display_name = f"[{theme.replace('_', ' ').upper()}] {clean_title}"
            
        display_desc = f"Premium digital design asset bundle artwork collection: {clean_title}."
        
        csv_rows.append({
            'name': display_name,
            'description': display_desc,
            'price': "9.99",
            'zip_file': new_zip_file,
            'preview_file': new_img_file
        })
        
        theme_counters[theme] += 1
        matched_total += 1

# 5. Output modern CSV data sheet configuration
with open(CSV_OUTPUT_PATH, mode='w', newline='', encoding='utf-8') as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=['name', 'description', 'price', 'zip_file', 'preview_file'])
    writer.writeheader()
    writer.writerows(csv_rows)

print("==================================================")
print(f"🚀 Execution Complete! Successfully matched {matched_total} file pairs.")
print(f"📁 Unified Assets copied to: {OUTPUT_DIR}")
print(f"📄 Gumroad CSV generated at: {CSV_OUTPUT_PATH}")
if theme_counters:
    print("\nCategorized Breakdown:")
    for t, count in theme_counters.items():
        print(f"  🔹 {t}: {count - 1} items aligned.")
print("==================================================")
