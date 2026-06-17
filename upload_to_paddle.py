import requests
import sqlite3
import os
import time

# 1. Configuration Settings
PADDLE_API_KEY = "pdl_live_apikey_01kvasv79wgshpva5gt5ceqy1f_Ajn9QezGW97P2tjNEFBRn3_AwR"  # <-- Paste your actual Secret Key string here
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')

HEADERS = {
    "Authorization": f"Bearer {PADDLE_API_KEY}",
    "Content-Type": "application/json"
}

def sync_catalog():
    if PADDLE_API_KEY == "PASTE_YOUR_SECRET_API_KEY_HERE" or PADDLE_API_KEY == "":
        print("❌ Error: Please paste your real Paddle Secret API Key at the top of the script first!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Pull products needing mapping keys
        cursor.execute("SELECT sku, name, price FROM products WHERE paddle_price_id IS NULL OR paddle_price_id = '';")
        products = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"❌ Database Error: {e}")
        conn.close()
        return
    
    total_items = len(products)
    print(f"🚀 Found {total_items} items needing Paddle synchronization...")
    
    count = 0
    for sku, name, price in products:
        count += 1
        
        # Format string nicely for display in your checkout window
        clean_name = name.replace('_', ' ').title()
        print(f"[{count}/{total_items}] Syncing: {clean_name}...")
        
        desc_text = f"Premium digital design asset bundle artwork collection: {clean_name}."
        
        try:
            # FIX: Pointing to the real Paddle API endpoint instead of the home root page
            prod_resp = requests.post("https://api.paddle.com/products", headers=HEADERS, json={
                "name": clean_name,
                "tax_category": "standard",
                "description": desc_text
            })
            
            if prod_resp.status_code != 201:
                print(f"  ❌ Product error for {sku}: [{prod_resp.status_code}] {prod_resp.text}")
                continue
                
            product_id = prod_resp.json()['data']['id']
            
            # FIX: Pointing to the real Paddle API prices collection path
            price_cents = int(float(price) * 100)
            price_resp = requests.post("https://api.paddle.com/prices", headers=HEADERS, json={
                "product_id": product_id,
                "description": f"Standard Price for {clean_name}",
                "name": "One-time Purchase",
                "unit_price": {
                    "amount": str(price_cents),
                    "currency_code": "USD"
                }
            })
            
            if price_resp.status_code != 201:
                print(f"  ❌ Price error for {sku}: [{price_resp.status_code}] {price_resp.text}")
                continue
                
            paddle_price_id = price_resp.json()['data']['id']
            
            # Save the newly generated item pricing key back into your store rows
            cursor.execute("UPDATE products SET paddle_price_id = ? WHERE sku = ?;", (paddle_price_id, sku))
            conn.commit()
            print(f"    ✅ Successfully mapped to: {paddle_price_id}")
            
            # Tiny processing buffer time delay
            time.sleep(0.1)
            
        except Exception as e:
            print(f"💥 Connection failure on item {sku}: {e}")
            break

    conn.close()
    print("\n🏁 Catalog synchronization process complete!")

if __name__ == '__main__':
    sync_catalog()
