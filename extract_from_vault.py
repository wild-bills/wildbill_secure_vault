import os
import zipfile
import sqlite3
import re
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')
VAULT_DIR = os.path.join(BASE_DIR, 'static', 'wildbill_vault')

# FIXED: Pointing exactly to your safe backups folder path location
ZIP_SOURCE_DIR = os.path.expanduser('~/vault_secure_backups')

def extract_and_populate():
    if not os.path.exists(ZIP_SOURCE_DIR):
        print(f"❌ Error: Source directory '{ZIP_SOURCE_DIR}' does not exist.")
        return

    all_files = os.listdir(ZIP_SOURCE_DIR)
    zip_files = sorted([f for f in all_files if f.lower().startswith('wb-art-') and f.lower().endswith('.zip')])

    if not zip_files:
        print(f"❌ Error: No wb-art-###.zip files found inside {ZIP_SOURCE_DIR}")
        return

    print(f"🚀 Found {len(zip_files)} sanitized archives inside vault_secure_backups. Running extraction loop...")

    os.makedirs(VAULT_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS products;")
    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE,
            name TEXT,
            theme TEXT,
            price REAL,
            image_url TEXT,
            zip_filename TEXT,
            file_count INTEGER,
            paddle_price_id TEXT,
            preview_1 TEXT,
            preview_2 TEXT,
            preview_3 TEXT,
            preview_4 TEXT
        );
    """)

    image_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    imported_count = 0

    for z_file in zip_files:
        sku_match = re.search(r'(wb-art-\d+)', z_file.lower())
        if not sku_match:
            continue
        
        sku = sku_match.group(1).upper()
        zip_path = os.path.join(ZIP_SOURCE_DIR, z_file)
        
        extracted_previews = []
        clean_name = sku.replace('-', ' ').title()
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as archive:
                file_list = archive.namelist()
                
                for inner_file in file_list:
                    if inner_file.lower().endswith('.txt') and 'metadata' in inner_file.lower():
                        try:
                            with archive.open(inner_file) as mf:
                                first_line = mf.readline().decode('utf-8', errors='ignore').strip()
                                if first_line and len(first_line) < 100:
                                    clean_name = first_line.replace('_', ' ').replace('-', ' ').title()
                                    break
                        except:
                            pass

                img_files = [f for f in file_list if f.lower().endswith(image_extensions) and not f.startswith('__MACOSX')]
                
                # Targets file system index orders: 1st, 3rd, 5th, 7th
                target_indices = [0, 2, 4, 6]
                
                for target_idx in target_indices:
                    if target_idx < len(img_files):
                        img_name = img_files[target_idx]
                        ext = os.path.splitext(img_name)[1].lower()
                        preview_num = len(extracted_previews) + 1
                        new_img_name = f"{sku.lower()}_preview_{preview_num}{ext}"
                        target_img_path = os.path.join(VAULT_DIR, new_img_name)
                        
                        with archive.open(img_name) as source, open(target_img_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        
                        extracted_previews.append(f"/static/wildbill_vault/{new_img_name}")

        except Exception as e:
            print(f"⚠️ Error reading archive {z_file}: {e}")
            continue

        # Safely assign static index strings to your database columns
        image_url = extracted_previews[0] if len(extracted_previews) > 0 else ""
        p1 = extracted_previews[0] if len(extracted_previews) > 0 else ""
        p2 = extracted_previews[1] if len(extracted_previews) > 1 else ""
        p3 = extracted_previews[2] if len(extracted_previews) > 2 else ""
        p4 = extracted_previews[3] if len(extracted_previews) > 3 else ""

        theme = "gothic"
        if "cyberpunk" in clean_name.lower():
            theme = "cyberpunk"
        elif "streetwear" in clean_name.lower():
            theme = "streetwear"

        cursor.execute("""
            INSERT INTO products (sku, name, theme, price, image_url, zip_filename, file_count, paddle_price_id, preview_1, preview_2, preview_3, preview_4)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (sku, clean_name, theme, 10.00, image_url, z_file, len(img_files), '', p1, p2, p3, p4))
        
        imported_count += 1
        print(f" ✅ Processed [{sku}] -> {clean_name}")

    conn.commit()
    conn.close()
    print(f"\n🏁 Complete! Standardized database populated with {imported_count} unique items.")

if __name__ == '__main__':
    extract_and_populate()
