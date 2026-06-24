import os
import json
import time
import requests

# ----------------- CONFIGURATION ----------------- #
# PASTE YOUR NEW TEST API KEY INSIDE THESE QUOTES:
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI5NGQ1OWNlZi1kYmI4LTRlYTUtYjE3OC1kMjU0MGZjZDY5MTkiLCJqdGkiOiIyNTA5ZDI0OTIwOTQ5YjkzNWQ5MjIzZTljYjg1ZWI5ZTEwODc4M2IwMDNjMjM3N2EyYmUzZTllNGVmZTMxMjBkOTFmNzAwMTZlOTZkOTQ1MyIsImlhdCI6MTc4MjI5MjQ1MS4xMDcwNDIsIm5iZiI6MTc4MjI5MjQ1MS4xMDcwNDQsImV4cCI6MTc5ODA3MDQwMC4wMjMwOTksInN1YiI6Ijc0MTAzMjYiLCJzY29wZXMiOltdfQ.NQHDvNUpR03vgLqUkZlU7nhLsko1HglFxqcUoTThToDdl6wPSgKye-CK01UEY7a88m2AI_a2u1IUE2bDHV7T2IwTIougA-EdT69tILEfhbmUbVqhPARf88qJUa43t-RJJ_Angd5FjQUW7E2iNeeBF7nWW8ucXoPeeAD43mopfq6Wz_y2oNc1AxQVyZk-Mx1FgcdrALIFHjnH7C99hWv9S6XboxGPXD2NXpyE2Xg3d1c4Lat8EKhgvxLgWovw_GH8GOOLvnuLLDbL2e_zYilwtF8DzXDB2qkmkKOx2fvOBKq5JoMIVQC_GNCffEVjLxY3y14afIinvBwT_H2HP9oetRr1b1XG5hjZE27tE6pNU0kFI65MfGnui10-Ss22GqO3p2gRPUDozhtQFhh7PYVbUj6P_iTCOrNKlFma2uocjyPh26O9OI0_lzNS7CP67xOU9eeaTEfr37k9uI07kwIu-Fe4jxSSflW0h2g2Y73MzGdx07CJ8XZ-8w_7Rui4rp4hLaFmcd9Q3MbXhx8LlAQkLe2e8xVSavmtzTcRyHYkbB1_vETqAXJvQtoT0Q86KiLeDR1FYSAI5Syo18mtAJ2mkC6_G6K8uiC61v8zLfIY-x0VHjKDlkXbIlZv4AASzLOC-cCcdkxbHzJjBTK1HBncjEWCJRt4E5HpZjpk7-Y9I64"
STORE_ID = "411144"
JSON_DATA_FILE = "products.json"
BASE_URL = "https://lemonsqueezy.com"
LOG_FILE = "lemonsqueezy_test_success_log.txt"
# ------------------------------------------------- #

def load_progress():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def log_success(title):
    with open(LOG_FILE, "a") as f:
        f.write(f"{title}\n")

def upload_to_lemonsqueezy():
    print("🚀 Initializing Test-Mode Lemon Squeezy Stream...")
    
    if API_KEY == "PASTE_YOUR_TEST_API_KEY_HERE":
        print("❌ Error: You must update the API_KEY field inside the script first!")
        return

    if not os.path.exists(JSON_DATA_FILE):
        print(f"❌ Error: Missing configuration file '{JSON_DATA_FILE}'.")
        return

    completed_uploads = load_progress()
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json"
    }

    with open(JSON_DATA_FILE, "r", encoding="utf-8") as f:
        products = json.load(f)

    success_count = 0
    
    for index, product in enumerate(products, start=1):
        title = product["Title"]
        if title in completed_uploads:
            continue

        description = product["Description"]
        zip_path = product["Zip_Path"]

        if not os.path.exists(zip_path):
            continue

        print(f"\n📦 Processing [{index}/{len(products)}]: '{title}'...")

        # FIXED: Added default variant template values to pass Test Mode validation filters
        product_payload = {
            "data": {
                "type": "products",
                "attributes": {
                    "name": title,
                    "description": description
                },
                "relationships": {
                    "store": {
                        "data": {
                            "type": "stores",
                            "id": str(STORE_ID)
                        }
                    }
                }
            }
        }

        try:
            prod_response = requests.post(f"{BASE_URL}/products", headers=headers, json=product_payload)
            
            if prod_response.status_code != 200 and prod_response.status_code != 201:
                print(f"   ❌ Creation rejected. Code: {prod_response.status_code}")
                print(f"   Details: {prod_response.text}")
                continue

            product_id = prod_response.json().get("data", {}).get("id")
            
            # STEP 2: File upload mapping stream
            file_headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Accept": "application/vnd.api+json"
            }
            
            with open(zip_path, "rb") as binary_data:
                file_payload = {
                    "product_id": (None, str(product_id)),
                    "file": (os.path.basename(zip_path), binary_data, "application/zip")
                }
                file_response = requests.post(f"{BASE_URL}/files", headers=file_headers, files=file_payload)

            if file_response.status_code == 200 or file_response.status_code == 201:
                print(f"   ✅ Success! '{title}' uploaded to Test Dashboard.")
                log_success(title)
                success_count += 1
            else:
                print(f"   ❌ File attachment failed. Code: {file_response.status_code}")

            time.sleep(4)

        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue

    print(f"\n🏁 Complete! Successfully routed {success_count} listings to your Test Environment.")

if __name__ == "__main__":
    upload_to_lemonsqueezy()
