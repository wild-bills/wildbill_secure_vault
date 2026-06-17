import os
import zipfile
import sqlite3
import re
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')
VAULT_DIR = os.path.join(BASE_DIR, 'static', 'wildbill_vault')
ZIP_SOURCE_DIR = os.path.expanduser('~/vault_secure_backups')

def extract_and_populate():
    if not os.path.exists(ZIP_SOURCE_DIR):
        print(f"❌ Error: Source directory '{ZIP_SOURCE_DIR}' does not exist.")
        return

    all_files = os.listdir(ZIP_SOURCE_DIR)
    zip_files = sorted([f for f in all_files if f.lower().startswith('clipart_zips_item_') and f.lower().endswith('.zip')])

    if not zip_files:
        print(f"❌ Error: No clipart_zips_item_###.zip files found inside {ZIP_SOURCE_DIR}")
        return

    print(f"🚀 Found {len(zip_files)} archives. Extracting 1st, 3rd, 5th, and 7th files for previews...")

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
        num_match = re.search(r'item_(\d+)', z_file.lower())
        if not num_match:
            continue
        
        item_num = int(num_match.group(1))
        sku = f"WB-ART-{item_num:03d}"
        zip_path = os.path.join(ZIP_SOURCE_DIR, z_file)
        
        extracted_previews = []
        clean_name = f"Premium Asset Bundle {item_num}"
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as archive:
                file_list = archive.namelist()
                
                # Check for metadata name
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

                # Filter down to true images inside the ZIP
                img_files = [f for f in file_list if f.lower().endswith(image_extensions) and not f.startswith('__MACOSX')]
                
                # Crucial Fix: Specifically target indices 0 (1st), 2 (3rd), 4 (5th), and 6 (7th)
                target_indices = [0, 2, 4, 6]
                
                for preview_num, target_idx in enumerate(target_indices):
                    if target_idx < len(img_files):
                        img_name = img_files[target_idx]
                        ext = os.path.splitext(img_name)[1].lower()
                        new_img_name = f"{sku.lower()}_preview_{preview_num + 1}{ext}"
                        target_img_path = os.path.join(VAULT_DIR, new_img_name)
                        
                        with archive.open(img_name) as source, open(target_img_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                        
                        extracted_previews.append(f"/static/wildbill_vault/{new_img_name}")
                    else:
                        extracted_previews.append("") # Keep array slot structured even if ZIP has fewer than 7 images

        except Exception as e:
            print(f"⚠️ Error reading zip file {z_file}: {e}")
            continue

        # Map URLs safely based on structural extraction outputs
        image_url = extracted_previews[0] if extracted_previews[0] else ""
        p1 = extracted_previews[0] if extracted_previews[0] else ""
        p2 = extracted_previews[1] if extracted_previews[1] else ""
        p3 = extracted_previews[2] if extracted_previews[2] else ""
        p4 = extracted_previews[3] if extracted_previews[3] else ""

        theme = "gothic"
        if "cyberpunk" in clean_name.lower():
            theme = "cyberpunk"
        elif "streetwear" in clean_name.lower():
            theme = "streetwear"

        zip_filename = f"{sku.lower()}.zip"
        cursor.execute("""
            INSERT INTO products (sku, name, theme, price, image_url, zip_filename, file_count, paddle_price_id, preview_1, preview_2, preview_3, preview_4)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (sku, clean_name, theme, 10.00, image_url, zip_filename, len(img_files), '', p1, p2, p3, p4))
        
        # Rename the source ZIP file to match your clean wb-art-###.zip layout configuration
        new_zip_name = os.path.join(ZIP_SOURCE_DIR, zip_filename)
        if os.path.exists(zip_path) and not os.path.exists(new_zip_name):
            os.rename(zip_path, new_zip_name)

        imported_count += 1
        print(f" ✅ Processed [{sku}] -> {clean_name} (Extracted targeted files)")

    conn.commit()
    conn.close()
    print(f"\n🏁 Complete! Clean schema populated with {imported_count} image-mapped items.")

if __name__ == '__main__':
    extract_and_populate()
