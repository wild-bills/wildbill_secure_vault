import os
import zipfile
import math
import sqlite3
import re
# --- MULTI-DIRECTORY PATH CONFIGURATION ---
# Add every single folder path here where you keep your generator outputs
SOURCE_DIRECTORIES = [
    "/home/wildbill/all_combined_zips",                  # Where Backblaze syncs down
    "/home/wildbill/adult_clipart_factory",              # Your primary generator home folder
    "/home/wildbill/adult_graphics_factory"              # Your alternative output path
]

OUTPUT_DIR = "/home/wildbill/vault_secure_backups"
DB_PATH = "/home/wildbill/wildbill_secure_vault/store.db"

def scan_zip_contents(zip_path):
    """Counts the actual total number of vector formats, banners, and files inside a zip."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            return len([f for f in z.namelist() if not f.endswith('/')])
    except Exception as e:
        print(f"⚠️ Error reading file contents for {zip_path}: {e}")
        return 0

def create_mega_bundles(theme_keyword, items_per_bundle=60, base_price=12.00):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    matching_zips = []
    file_location_map = {}

    # 1. Scan all folders inside your array to catch everything without moving files manually
    for directory in SOURCE_DIRECTORIES:
        if not os.path.exists(directory):
            continue
        print(f"🔍 Scanning directory: {directory} for theme '{theme_keyword}'...")
        for f in os.listdir(directory):
            if f.endswith('.zip') and theme_keyword.lower() in f.lower():
                # Avoid duplicates if a file exists in multiple staging folders
                if f not in file_location_map:
                    matching_zips.append(f)
                    file_location_map[f] = os.path.join(directory, f)
    
    total_zips = len(matching_zips)
    if total_zips == 0:
        print(f"❌ No asset packages found anywhere matching theme: '{theme_keyword}'")
        return

    print(f"📂 Found {total_zips} total unique source packs for theme '{theme_keyword}'.")
    total_bundles = math.ceil(total_zips / items_per_bundle)
    print(f"📦 Compiling into {total_bundles} separate high-value Mega-Vault volumes...\n")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Build the split mega bundles
    for i in range(total_bundles):
        bundle_num = i + 1
        start_idx = i * items_per_bundle
        end_idx = start_idx + items_per_bundle
        chunk = matching_zips[start_idx:end_idx]
        
        bundle_filename = f"{theme_keyword.lower()}-mega-vault-vol{bundle_num}.zip"
        output_path = os.path.join(OUTPUT_DIR, bundle_filename)
        sku = f"WB-{theme_keyword.upper()[:5]}-{bundle_num:03d}"
        display_name = f"{theme_keyword.capitalize()} Mega-Vault Vol {bundle_num}"
        
        print(f"🔒 Packing volume {bundle_num} ({len(chunk)} assets) into: {bundle_filename}...")
        
        total_sub_files = 0
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as master_zip:
            for file in chunk:
                full_source_path = file_location_map[file]
                total_sub_files += scan_zip_contents(full_source_path)
                master_zip.write(full_source_path, arcname=file)

        # 3. Dynamic marketing descriptions based on your rich file formats
        description_text = (
            f"A premium, high-volume thematic bundle compiling {len(chunk)} individual asset packages. "
            f"Includes a massive archive of {total_sub_files} total graphics files, highlighting "
            f"backgroundless vector art files, custom promotional banners, transparent layout elements, "
            f"and high-resolution design alternatives. Engineered specifically for digital creators, developer bundles, and rapid content scaling."
        )

        cursor.execute("DELETE FROM products WHERE sku = ?", (sku,))
        cursor.execute("""
            INSERT INTO products (name, theme, sku, price, zip_filename, file_count, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (display_name, theme_keyword.lower(), sku, base_price, bundle_filename, total_sub_files, description_text))
        
        print(f"✅ Vol {bundle_num} recorded! Injected file count of {total_sub_files} assets to database row.")

    conn.commit()
    conn.close()
    print(f"\n🚀 System synchronization complete! Fresh master bundles saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    # Connect to the source folders and extract every unique theme name available
    all_discovered_themes = set()
    
    for directory in SOURCE_DIRECTORIES:
        if not os.path.exists(directory):
            continue
        for f in os.listdir(directory):
            if f.endswith('.zip'):
                # Extracts the theme part out of the filename automatically
                # e.g., 'vintage_neon_04.zip' -> 'vintage_neon'
                base_theme = re.split(r'[-_]\d+$|\d+$', os.path.splitext(f)[0])[0].strip().lower()
                if base_theme:
                    all_discovered_themes.add(base_theme)
                    
    print(f"👁️ Discovered {len(all_discovered_themes)} total unique themes across your drives: {list(all_discovered_themes)}")
    print("🚀 Starting global warehouse packaging loop...\n")
    
    # Run the compiler over every single theme found
    for theme in sorted(all_discovered_themes):
        # Skips empty strings if any bad file formats exist
        if not theme:
            continue
        create_mega_bundles(theme, items_per_bundle=60, base_price=12.00)
        
    print("\n👑 ALL WAREHOUSE BUNDLES GENERATED AND LOGGED TO DATABASE SUCCESSFULLY!")

