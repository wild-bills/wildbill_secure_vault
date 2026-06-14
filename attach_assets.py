import os
import sqlite3
import time

# --- CONFIGURATION SETTINGS ---
DB_PATH = "database/store.db"
ROOT_ZIPS_DIR = "/home/wildbill/adult_clipart_factory/"
PREVIEW_IMAGES_DIR = os.path.expanduser("~/wildbill_secure_vault/static/images/")

# 1. PASTE YOUR GUMROAD ACCESS TOKEN INSIDE THE QUOTES BELOW:
GUMROAD_ACCESS_TOKEN = "HbzMfBBfOpQinnnabZhlpS2P4ZjoagGpUcdsblZmBrQ"

def get_db_products():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT sku, name, theme FROM products WHERE file_count > 0")
    rows = cursor.fetchall()
    conn.close()
    return rows

def attach_assets_via_curl():
    products = get_db_products()
    if not products:
        print("❌ No products available to process in database.")
        return

    print(f"🚀 Starting database-driven uploader for {len(products)} vault packages...")

    for index, item in enumerate(products, 1):
        sku_id = item['sku']
        clean_name = item['name'].replace('_', ' ')
        db_filename = item['name']
        
        print(f"\n📦 Processing [{index}/{len(products)}]: {clean_name} (SKU: {sku_id})")

        # --- PART A: ATTACH THE PHYSICAL ZIP PACKAGE VIA CURL ---
        local_zip_path = None
        for root, dirs, files in os.walk(ROOT_ZIPS_DIR):
            if db_filename + ".zip" in files:
                local_zip_path = os.path.join(root, db_filename + ".zip")
                break

        if local_zip_path and os.path.exists(local_zip_path):
            print(f"   ⏳ Uploading ZIP archive: {db_filename}.zip...")
            # We target the custom permalink (SKU) you generated in Make.com
            upload_cmd = (
                f"curl -s -X POST https://gumroad.com{sku_id}/attachments "
                f"-F \"access_token={GUMROAD_ACCESS_TOKEN}\" "
                f"-F \"file=@{local_zip_path}\""
            )
            os.system(upload_cmd)
            print("   ✅ ZIP Command Executed.")
        else:
            print(f"   ❌ File Missing: {db_filename}.zip not found.")

        # --- PART B: ATTACH THE PREVIEW COVER IMAGE VIA CURL ---
        expected_img_name = f"{db_filename}_preview.jpg"
        local_img_path = os.path.join(PREVIEW_IMAGES_DIR, expected_img_name)

        if os.path.exists(local_img_path):
            print(f"   ⏳ Uploading Cover Thumbnail: {expected_img_name}...")
            cover_cmd = (
                f"curl -s -X POST https://gumroad.com{sku_id}/cover "
                f"-F \"access_token={GUMROAD_ACCESS_TOKEN}\" "
                f"-F \"file=@{local_img_path}\""
            )
            os.system(cover_cmd)
            print("   ✅ Cover Command Executed.")
        else:
            print(f"   ❌ Image Missing: {expected_img_name} not found.")

        # Delay pass cushion
        time.sleep(2)

    print("\n🎉 Process complete! Your files and graphics have been pushed to Gumroad.")

if __name__ == "__main__":
    attach_assets_via_curl()
