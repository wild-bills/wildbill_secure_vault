import os
import sqlite3
import time
import requests

# --- CONFIGURATION SETTINGS ---
DB_PATH = "database/store.db"
GUMROAD_ACCESS_TOKEN = "7UAA_2Bu6PLFQslkhCAHCrwmdh16XHh3HE17HNdLoTg"

def get_db_products():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT sku, name, theme, file_count FROM products WHERE file_count > 0")
    rows = cursor.fetchall()
    conn.close()
    return rows

def push_to_gumroad():
    products = get_db_products()
    if not products:
        print("❌ No products available to process in database.")
        return

    print(f"🚀 Launching smart-retry creator engine for {len(products)} packages...")
    api_url = "https://gumroad.com"

    for index, item in enumerate(products, 1):
        clean_name = item['name'].replace('_', ' ').strip()
        clean_theme = item['theme'].replace('_', ' ').strip()
        
        description_pitch = (
            f"Unlock premium access to the {clean_name} collection!\n\n"
            f"• Total high-definition graphics assets included: {item['file_count']} files\n"
            f"• Vault Collection Category: {clean_theme}\n"
            f"• Complete licensing usage rights included with every purchase."
        )

        file_qty = item['file_count']
        if file_qty <= 50:
            final_price = 4.99   
        elif file_qty > 50 and file_qty < 600:
            final_price = 14.99  
        else:
            final_price = 39.99  

        payload = {
            "access_token": GUMROAD_ACCESS_TOKEN,
            "product[name]": clean_name,
            "product[price]": final_price,
            "product[description]": description_pitch,
            "product[custom_permalink]": f"wildbill_{item['sku']}"
        }

        # INTELLIGENT BACKOFF RATE-LIMIT HANDLING
        max_retries = 5
        base_delay = 6  # Start with a safe 6-second wait block
        success = False

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(api_url, data=payload)
                
                if response.status_code == 201:
                    res_data = response.json()
                    prod_url = res_data['product'].get('url', 'Published')
                    print(f"✅ [{index}/{len(products)}] Success: {clean_name} | Link: {prod_url}")
                    success = True
                    break
                elif response.status_code == 429:
                    # Catch the rate limit, back off, and retry the same product row
                    wait_time = base_delay * attempt
                    print(f"⏳ [{index}/{len(products)}] Rate Limited (429) on {clean_name}. Sleeping {wait_time}s before retry {attempt}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ [{index}/{len(products)}] API Block on {clean_name}: Status {response.status_code} | Msg: {response.text}")
                    break
            except Exception as e:
                print(f"❌ Connection error on {clean_name}: {e}")
                time.sleep(3)

        # Safe baseline delay to prevent spamming Gumroad's firewall endpoints
        time.sleep(4)

    print("\n🎉 Process Finished! All product listings are safely generated.")

if __name__ == "__main__":
    push_to_gumroad()
