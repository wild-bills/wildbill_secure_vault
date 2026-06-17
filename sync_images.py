import os
import sqlite3
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')
TARGET_DIR = os.path.join(BASE_DIR, 'static', 'wildbill_vault')

def sync_new_assets():
    if not os.path.exists(TARGET_DIR):
        print(f"❌ Error: The directory '{TARGET_DIR}' does not exist.")
        return

    # List all files inside your new folder
    all_files = os.listdir(TARGET_DIR)
    print(f"📂 Found {len(all_files)} total asset files inside static/wildbill_vault/")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Grab current database items
    cursor.execute("SELECT sku, name FROM products;")
    products = cursor.fetchall()
    
    updated_covers = 0
    
    for sku, name in products:
        # Extract the digital number from your bundle name (e.g., 'Bundle_129' -> '129')
        match = re.search(r'bundle_(\d+)', name.lower())
        if not match:
            continue
            
        bundle_num = match.group(1)
        
        # Look for a storefront cover file matching this specific bundle number
        cover_file = None
        for filename in all_files:
            fn_lower = filename.lower()
            if bundle_num in fn_lower and "cover" in fn_lower and fn_lower.endswith(('.jpg', '.jpeg', '.png')):
                cover_file = filename
                break
                
        # If no explicit 'cover' file is found, fallback to any image containing that bundle number
        if not cover_file:
            for filename in all_files:
                fn_lower = filename.lower()
                if bundle_num in fn_lower and fn_lower.endswith(('.jpg', '.jpeg', '.png')):
                    cover_file = filename
                    break

        if cover_file:
            # Set the relative internet route path for the browser
            web_path = f"/static/wildbill_vault/{cover_file}"
            cursor.execute("UPDATE products SET image_url = ? WHERE sku = ?;", (web_path, sku))
            updated_covers += 1

    conn.commit()
    conn.close()
    print(f"🏁 Image sync complete! Successfully re-mapped {updated_covers} item cover paths.")

if __name__ == '__main__':
    sync_new_assets()
