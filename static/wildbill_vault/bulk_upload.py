import os
import csv
import requests
import json

# Configuration
TOKEN = "7UAA_2Bu6PLFQslkhCAHCrwmdh16XHh3HE17HNdLoTg"
ASSET_DIR = "/home/wildbill/gumroad_ready_assets"
CSV_PATH = os.path.join(ASSET_DIR, "products.csv")
LOG_PATH = os.path.join(ASSET_DIR, "upload_history.log")

def load_upload_history():
    if not os.path.exists(LOG_PATH):
        return set()
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def log_successful_upload(product_name):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{product_name}\n")

def create_and_upload():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    completed_products = load_upload_history()
    if completed_products:
        print(f"Found existing log. Skipping {len(completed_products)} previously uploaded items.")

    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            name = row.get('name')
            price = row.get('price')
            description = row.get('description', '')
            file_name = row.get('file_name')

            if name:
                name = name.strip()

            if not name or name.lower() == "name":
                continue

            if name in completed_products:
                print(f"Skipping (Already Uploaded): {name}")
                continue

            print(f"\n[Processing]: {name}...")

            # 1. Create the Product Listing
            create_url = "https://gumroad.com"
            headers = {"Authorization": f"Bearer {TOKEN}"}
            payload = {
                "name": name,
                "price": price,
                "description": description
            }

            try:
                res = requests.post(create_url, headers=headers, data=payload)
                
                # Check for HTTP Block/Error (e.g. 401 Unauthorized, 429 Rate Limit)
                if res.status_code != 200:
                    print(f"Server Error ({res.status_code}) creating {name}. Raw response: {res.text[:150]}")
                    continue

                try:
                    res_data = res.json()
                except json.JSONDecodeError:
                    print(f"Error: Server sent non-JSON output for {name}. Content snippet: {res.text[:150]}")
                    continue

                if not res_data.get('success'):
                    print(f"Failed to create listing for {name}: {res_data.get('message')}")
                    continue

                product_id = res_data['product']['id']
                print(f"Listing created successfully! ID: {product_id}")

                # 2. Attach the Digital File Asset
                file_path = os.path.join(ASSET_DIR, file_name)
                if not os.path.exists(file_path):
                    print(f"Warning: Asset file not found at {file_path}. Listing made, skipping file.")
                    log_successful_upload(name)
                    continue

                attach_url = f"https://gumroad.com/{product_id}/attachments"
                print(f"Uploading file: {file_name}...")
                
                with open(file_path, 'rb') as asset_file:
                    files = {'file': asset_file}
                    file_payload = {"access_token": TOKEN} 
                    
                    file_res = requests.post(attach_url, data=file_payload, files=files)
                    
                    if file_res.status_code != 200:
                        print(f"Server Error ({file_res.status_code}) during file attachment. Raw response: {file_res.text[:150]}")
                        continue
                        
                    try:
                        file_res_data = file_res.json()
                    except json.JSONDecodeError:
                        print(f"Error: Non-JSON file attachment response. Content snippet: {file_res.text[:150]}")
                        continue

                    if file_res_data.get('success'):
                        print(f"Successfully uploaded and attached {file_name}!")
                        log_successful_upload(name)
                    else:
                        print(f"File upload failed: {file_res_data.get('message')}")

            except Exception as e:
                print(f"Network or systemic exception occurred handling {name}: {e}")

    print("\nBulk processing batch complete!")

if __name__ == "__main__":
    create_and_upload()
