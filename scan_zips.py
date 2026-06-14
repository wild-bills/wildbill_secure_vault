import os
import sqlite3
import zipfile
import re

DB_PATH = "database/store.db"
ROOT_ZIPS_DIR = "/home/wildbill/adult_clipart_factory/"

def clean_string(s):
    return re.sub(r'[^a-zA-Z0-9]', '', str(s)).lower()

if not os.path.exists(ROOT_ZIPS_DIR):
    print(f"Error: Could not find the folder '{ROOT_ZIPS_DIR}'")
    exit(1)

print("Scanning directory tree for all archive assets...")
clean_zip_map = {}

for root, dirs, files in os.walk(ROOT_ZIPS_DIR):
    for file in files:
        if file.lower().endswith('.zip'):
            clean_zip_map[clean_string(file)] = os.path.join(root, file)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT id, sku, name FROM products")
products = cursor.fetchall()

for prod_id, sku, name in products:
    clean_name = clean_string(name)
    clean_sku = clean_string(sku)
    
    found_zip = clean_zip_map.get(clean_name) or clean_zip_map.get(clean_sku)
    
    if not found_zip:
        for clean_f, path in clean_zip_map.items():
            if clean_name in clean_f or clean_sku in clean_f:
                found_zip = path
                break

    if found_zip:
        try:
            with zipfile.ZipFile(found_zip, 'r') as z:
                valid_files = [f for f in z.namelist() if not f.startswith('__MACOSX/') and not f.endswith('/')]
                count = len(valid_files)
                
                cursor.execute("UPDATE products SET file_count = ? WHERE id = ?", (count, prod_id))
                print(f"✅ Indexed: {name} -> {count} assets")
        except Exception as e:
            print(f"❌ Error indexing {found_zip}: {e}")

conn.commit()
conn.close()
print("\nDatabase file tracking successfully populated with matching item sizes!")
