import os
import sqlite3
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')
VAULT_DIR = os.path.join(BASE_DIR, 'static', 'wildbill_vault')

def import_from_filenames():
    if not os.path.exists(VAULT_DIR):
        print(f"❌ Error: The directory '{VAULT_DIR}' does not exist.")
        return

    # Scan the folder for new files
    all_files = os.listdir(VAULT_DIR)
    
    # Filter out only the primary storefront cover image files
    cover_files = [f for f in all_files if "storefront_cover" in f.lower() and f.endswith(('.jpg', '.jpeg', '.png'))]
    
    if not cover_files:
        print("ℹ️ No files found with 'Storefront_Cover' in the name. Scanning for any image file...")
        cover_files = [f for f in all_files if f.endswith(('.jpg', '.jpeg', '.png', '.svg'))]

    print(f"🚀 Found {len(cover_files)} new artwork items to import.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Wipe old product schema records to avoid collision
    cursor.execute("DELETE FROM products;")
    
    imported_count = 0
    for filename in sorted(cover_files):
        # Extract SKU numbering sequence (e.g., looks for 'wb-art-001')
        sku_match = re.search(r'(wb-art-\d+)', filename.lower())
        if sku_match:
            sku = sku_match.group(1).upper()
        else:
            # Fallback if the filename lacks a strict matching pattern
            sku = f"WB-ART-{imported_count+1:03d}"

        # Generate a clean, polished item name by stripping out common extensions and structural prefixes
        clean_name = filename.replace('_Storefront_Cover', '').replace('_storefront_cover', '')
        clean_name = os.path.splitext(clean_name)[0] # Remove file extension (.jpg)
        clean_name = clean_name.replace('-', ' ').replace('_', ' ').strip().title()

        # Build clean pathways
        image_url = f"/static/wildbill_vault/{filename}"
        
        # Build the exact standardized zip name matching your new Backblaze naming convention
        zip_filename = f"{sku.lower()}.zip"
        
        # Map dynamic default themes based on keyword matching
        theme = "gothic"
        if "cyberpunk" in clean_name.lower():
            theme = "cyberpunk"
        elif "streetwear" in clean_name.lower():
            theme = "streetwear"

        try:
            cursor.execute("""
                INSERT INTO products (sku, name, theme, price, image_url, zip_filename, file_count, paddle_price_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (sku, clean_name, theme, 10.00, image_url, zip_filename, 0, ''))
            imported_count += 1
            print(f" Added: [{sku}] {clean_name}")
        except sqlite3.IntegrityError:
            print(f"⚠️ Duplicate skipped: {sku}")

    conn.commit()
    conn.close()
    print(f"\n🏁 Complete! Standardized database populated with {imported_count} new clean records.")

if __name__ == '__main__':
    import_from_filenames()
