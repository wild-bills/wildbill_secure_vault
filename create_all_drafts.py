import csv
import time
import requests

# ----------------- CONFIGURATION ----------------- #
GUMROAD_TOKEN = "7UAA_2Bu6PLFQslkhCAHCrwmdh16XHh3HE17HNdLoTg"
CSV_FILE_NAME = "products.csv"
BASE_URL = "https://gumroad.com"  # FIXED: Swapped to the working v1 creation endpoint
START_ROW = 1  
# ------------------------------------------------- #

def create_catalog():
    print("🚀 Initializing Gumroad Draft Profile Creator...")
    url = f"{BASE_URL}/products"

    try:
        with open(CSV_FILE_NAME, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            
            success_count = 0
            for index, row in enumerate(reader, start=1):
                if index < START_ROW:
                    continue

                title = row["Title"].strip()
                description = row["Description"].strip()
                price_cents = int(float(row["Price"]) * 100)

                print(f"\n📦 Row [{index}]: Creating profile for '{title}'...")

                # FIXED: Access token passed inside the body payload as required by v1
                create_payload = {
                    "access_token": GUMROAD_TOKEN,
                    "name": title,
                    "description": description,
                    "price": price_cents
                }
                
                response = requests.post(url, data=create_payload)
                
                if response.status_code == 429:
                    print("⚠️ Speed limit hit. Cooling down for 60 seconds...")
                    time.sleep(60)
                    response = requests.post(url, data=create_payload)

                if "limit" in response.text.lower() or response.status_code == 403:
                    print("\n🛑 Gumroad's 100-per-day upload limit has been reached for today.")
                    print(f"Please run this script again in 24 hours and change START_ROW to {index}!")
                    break

                if response.status_code == 200 or response.status_code == 201:
                    print(f"✅ Success! Profile draft created for '{title}'.")
                    success_count += 1
                else:
                    print(f"❌ Failed to create '{title}'. Code: {response.status_code}. Response: {response.text}")

                time.sleep(6)  # Safe delay between creations

            print(f"\n🏁 Complete! Created {success_count} new product drafts.")

    except FileNotFoundError:
        print(f"❌ Script Error: Could not find '{CSV_FILE_NAME}' in this directory.")

if __name__ == "__main__":
    create_catalog()
