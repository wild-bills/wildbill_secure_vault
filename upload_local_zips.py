import csv
import time
import os
import requests

# ----------------- CONFIGURATION ----------------- #
GUMROAD_TOKEN = "7UAA_2Bu6PLFQslkhCAHCrwmdh16XHh3HE17HNdLoTg"
CSV_FILE_NAME = "products.csv"
BASE_URL = "https://api.gumroad.com/v2"  # FIXED: Pointing back to verified v2 endpoint
LOCAL_BUNDLE_DIR = "/home/wildbill/adult_clipart_factory/completed_bundles"
# ------------------------------------------------- #

def get_all_gumroad_products():
    print("🔍 Fetching your active drafts from your Gumroad Dashboard...")
    
    # FIXED: Access token passed explicitly as a query parameter for v2 listing resource
    url = f"{BASE_URL}/products?access_token={GUMROAD_TOKEN}"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"❌ Failed to contact Gumroad API. Code: {response.status_code}")
        return []
        
    try:
        return response.json().get("products", [])
    except Exception:
        print("❌ Server returned non-JSON data. Please double-check your API token permissions.")
        return []

def upload_physical_files():
    live_products = get_all_gumroad_products()
    if not live_products:
        print("❌ No matching draft profiles found to update.")
        return
        
    print(f"📋 Verification complete: Found {len(live_products)} total products on your dashboard.")
    
    # Map listing titles to their matching IDs
    product_map = {p["name"].strip().lower(): p["id"] for p in live_products if "name" in p and "id" in p}

    try:
        with open(CSV_FILE_NAME, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            
            success_count = 0
            for index, row in enumerate(reader, start=1):
                title = row["Title"].strip()
                title_lower = title.lower()
                zip_filename = row["Zip_URL"].strip()
                preview_filename = row["Preview_URL"].strip()

                # Skip items that haven't been created on Gumroad yet
                if title_lower not in product_map:
                    continue

                product_id = product_map[title_lower]
                
                # Build physical folder absolute path structures
                full_zip_path = os.path.join(LOCAL_BUNDLE_DIR, zip_filename)
                full_preview_path = os.path.join(LOCAL_BUNDLE_DIR, preview_filename)

                # Verify files exist locally
                if not os.path.exists(full_zip_path):
                    print(f"⚠️ Row [{index}]: Skipped '{title}'. ZIP not found at: {full_zip_path}")
                    continue

                print(f"\n📦 Processing [{index}]: '{title}'...")

                # STEP 1: Upload physical thumbnail image file if it exists locally
                if os.path.exists(full_preview_path):
                    print(f"   🎨 Uploading thumbnail cover image: {preview_filename}")
                    with open(full_preview_path, "rb") as thumb_img:
                        thumb_payload = {"access_token": GUMROAD_TOKEN}
                        thumb_files = {"file": thumb_img}
                        requests.post(f"{BASE_URL}/products/{product_id}/thumbnail", data=thumb_payload, files=thumb_files)
                    time.sleep(2)

                print(f"   📁 Uploading local ZIP file: {zip_filename} ({os.path.getsize(full_zip_path) / (1024*1024):.2f} MB)")

                # STEP 2: Read and stream the physical file data to Gumroad storage
                with open(full_zip_path, "rb") as file_data:
                    file_payload = {"access_token": GUMROAD_TOKEN}
                    files_payload = {"file": file_data}
                    file_response = requests.post(
                        f"{BASE_URL}/products/{product_id}/attachments", 
                        data=file_payload, 
                        files=files_payload
                    )

                if file_response.status_code == 200 or file_response.status_code == 201:
                    print(f"   ✅ Success! Local file uploaded and attached to '{title}'.")
                    success_count += 1
                else:
                    print(f"   ❌ Upload failed for '{title}'. Code: {file_response.status_code}")
                    print(f"   Details: {file_response.text}")

                # Rate limiting cushion
                time.sleep(5)

            print(f"\n🏁 Complete! Successfully uploaded physical files to {success_count} existing listings.")

    except FileNotFoundError:
        print(f"❌ Script Error: Could not find the file '{CSV_FILE_NAME}' in this directory.")

if __name__ == "__main__":
    upload_physical_files()
