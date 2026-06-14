import os
import sqlite3
import time
import requests

# --- CONFIGURATION SETTINGS ---
DB_PATH = "database/store.db"
ROOT_ZIPS_DIR = "/home/wildbill/adult_clipart_factory/"

# 1. PASTE YOUR GUMROAD ACCESS TOKEN INSIDE THE QUOTES BELOW:
GUMROAD_ACCESS_TOKEN = "HbzMfBbf0PqinnnabZHLpS2P4ZJoagGpUcdSblZMBrQ"

def get_db_products():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        return []
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT sku, name, theme, price, file_count FROM products WHERE file_count > 0")
    rows = cursor.fetchall()
    conn.close()
    return rows

def push_to_gumroad():
    products = get_db_products()
    if not products:
        print("❌ No products available to upload.")
        return

    print(f"🚀 Starting fixed uploader engine for {len(products)} vault packages...")
    create_url = "https://gumroad.com"

    for index, item in enumerate(products, 1):
        clean_name = item['name'].replace('_', ' ')
        clean_theme = item['theme'].replace('_', ' ')
        
        description_pitch = (
            f"Unlock premium access to the {clean_name} collection!\n\n"
            f"• Total high-definition graphics assets included: {item['file_count']} files\n"
            f"• Vault Collection Category: {clean_theme}\n"
            f"• Complete licensing usage rights included with every purchase."
        )

        file_qty = item['file_count']
        if file_qty <= 50:
            final_price = 499   
        elif file_qty > 50 and file_qty < 600:
            final_price = 1499  
        else:
            final_price = 3999  

        payload = {
            "access_token": GUMROAD_ACCESS_TOKEN,
            "name": clean_name,
            "price": final_price,
            "description": description_pitch,
            "custom_permalink": item['sku']
        }

        try:
            response = requests.post(create_url, data=payload)
            
            # FIXED BY USING SIMPLE EQUALS TO SYMBOLS TO BYPASS THE BUG
            if response.status_code == 201:
                res_data = response.json()
                product_id = res_data['product']['id']
                prod_url = res_data['product'].get('url', 'Published')
                print(f"📦 Container Ready [{index}/{len(products)}]: {clean_name}")
                
                local_zip_path = None
                for root, dirs, files in os.walk(ROOT_ZIPS_DIR):
                    if item['name'] + ".zip" in files:
                        local_zip_path = os.path.join(root, item['name'] + ".zip")
                        break
                
                if local_zip_path and os.path.exists(local_zip_path):
                    print(f"   ⏳ Uploading attachment: {os.path.basename(local_zip_path)}...")
                    
                    attach_url = f"https://gumroad.com/{product_id}/attachments"
                    attach_payload = {"access_token": GUMROAD_ACCESS_TOKEN}
                    
                    with open(local_zip_path, 'rb') as f:
                        file_data = {'file': (os.path.basename(local_zip_path), f, 'application/zip')}
                        attach_res = requests.post(attach_url, data=attach_payload, files=file_data)
                        
                        if attach_res.status_code == 201:
                            print(f"   ✅ Fully Published! | Live Link: {prod_url}")
                        else:
                            print(f"   ⚠️ Attachment upload failed with status: {attach_res.status_code}")
                else:
                    print(f"   ⚠️ File Missing: Could not find physical zip for {item['name']}.zip")
            else:
                print(f"❌ Error creating {clean_name}: Status {response.status_code} | Msg: {response.text}")
        
        except Exception as e:
            print(f"❌ Connection Failure on {clean_name}: {e}")
        
        time.sleep(1)

    print("\n🎉 Process Finished! Check your Gumroad products panel portfolio items list.")

if __name__ == "__main__":
    push_to_gumroad()
