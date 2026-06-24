import csv
import time
import os
import requests

# ----------------- CONFIGURATION ----------------- #
GUMROAD_TOKEN = "7UAA_2Bu6PLFQslkhCAHCrwmdh16XHh3HE17HNdLoTg"
CSV_FILE_NAME = "products.csv"
BASE_URL = "https://gumroad.com"
LOG_FILE_NAME = "uploaded_log.txt"
# ------------------------------------------------- #

def load_uploaded_log():
    if not os.path.exists(LOG_FILE_NAME):
        return set()
    with open(LOG_FILE_NAME, "r") as f:
        return set(line.strip() for line in f if line.strip())

def log_success(title):
    with open(LOG_FILE_NAME, "a") as f:
        f.write(f"{title}\n")

def upload_catalog():
    print("🚀 Initializing Gumroad Resumable Bulk Uploader...")
    uploaded_items = load_uploaded_log()
    print(f"📋 Found {len(uploaded_items)} items already uploaded in previous runs.")

    headers = {
        "Authorization": f"Bearer {GUMROAD_TOKEN}"
    }

    try:
        with open(CSV_FILE_NAME, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            
            required_headers = ["Title", "Description", "Price", "Zip_URL", "Preview_URL"]
            if not all(h in reader.fieldnames for h in required_headers):
                print(f"❌ Error: Your CSV columns must match exactly: {required_headers}")
                return

            success_count = 0
            for index, row in enumerate(reader, start=1):
                title = row["Title"]
                
                # Check if this precise item was already created
                if title in uploaded_items:
                    continue

                description = row["Description"]
                price_cents = int(float(row["Price"]) * 100)
                zip_url = row["Zip_URL"]
                preview_url = row["Preview_URL"]

                print(f"\n📦 Processing Row [{index}]: '{title}'...")

                create_payload = {
                    "name": title,
                    "description": description,
                    "price": price_cents,
                    "product_type": "digital",
                    "file_url": zip_url
                }
                
                prod_response = requests.post(f"{BASE_URL}/products", headers=headers, data=create_payload)
                
                # Handle active rate-limits cleanly
                if prod_response.status_code == 429:
                    print("⚠️ Daily limit or speed limit hit. Pausing for 60 seconds...")
                    time.sleep(60)
                    prod_response = requests.post(f"{BASE_URL}/products", headers=headers, data=create_payload)

                # If Gumroad locks down due to the 100-item limit, stop cleanly
                if prod_response.status_code == 404 or "limit" in prod_response.text.lower():
                    print("\n🛑 Gumroad's 100-per-day upload limit has been reached for this account.")
                    print("Please run this script again in 24 hours! Your progress has been saved.")
                    break

                if prod_response.status_code != 200 and prod_response.status_code != 201:
                    print(f"❌ Failed to create '{title}'. Code: {prod_response.status_code}")
                    continue

                # Safely parse response data even if structures fluctuate
                response_json = prod_response.json()
                product_data = response_json.get("product", response_json)
                product_id = product_data.get("id")

                if product_id:
                    # Attach Thumbnail Cover
                    thumb_payload = {"url": preview_url}
                    requests.post(f"{BASE_URL}/products/{product_id}/thumbnail", headers=headers, data=thumb_payload)
                
                print(f"✅ Success! '{title}' uploaded.")
                log_success(title)
                success_count += 1

                # Safe pacing delay
                time.sleep(6)

            print(f"\n🏁 Run complete. Successfully uploaded {success_count} listings in this session.")

    except FileNotFoundError:
        print(f"❌ Script Error: Could not find the file '{CSV_FILE_NAME}' in this directory.")

if __name__ == "__main__":
    upload_catalog()
