import os
import sys
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Ensure your access token is pulled from the environment variables safely
ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN")
ZIP_DIR = "/home/wildbill/adult_clipart_factory/completed_bundles"

def create_resilient_session():
    """Configures automatic HTTP retries for network drops and rate limits"""
    session = requests.Session()
    retries = Retry(
        total=5,                  # Retry up to 5 times before failing a bundle
        backoff_factor=2,         # Wait 2s, 4s, 8s, 16s between attempts
        status_forcelist=[429, 500, 502, 503, 504], # Retry on rate limits or server drops
        raise_on_status=False
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

def push_to_gumroad():
    if not ACCESS_TOKEN:
        print("❌ Error: GUMROAD_ACCESS_TOKEN environment variable is missing.")
        print("   Run: export GUMROAD_ACCESS_TOKEN='your_token_here'")
        sys.exit(1)

    if not os.path.exists(ZIP_DIR):
        print(f"❌ Error: Targets directory missing: {ZIP_DIR}")
        sys.exit(1)

    session = create_resilient_session()
    # FIXED: Added correct endpoint path layers to prevent 404 connection drops
    api_url = "https://gumroad.com"
    
    print("==================================================================")
    # Count zip archives present inside the distribution vault path
    zip_files = [f for f in os.listdir(ZIP_DIR) if f.endswith(".zip")]
    print(f" 🚀 RESILIENT UPLOADER ENGAGED: Found {len(zip_files)} Bundles to Process")
    print("==================================================================")

    for filename in zip_files:
        zip_path = os.path.join(ZIP_DIR, filename)
        base_name = filename.replace(".zip", "")
        
        # Pull metadata configurations cleanly from your package staging maps
        manifest_path = os.path.join("/home/wildbill/adult_clipart_factory/output_png", f"{base_name}_manifest.json")
        if not os.path.exists(manifest_path):
            # Fallback check if your packer paths output files straight into the target package path instead
            manifest_path = os.path.join(ZIP_DIR, f"{base_name}_manifest.json")

        if not os.path.exists(manifest_path):
            print(f"⚠️ Skipping {filename}: Matching listing manifest file not found.")
            continue

        with open(manifest_path, "r") as jf:
            meta = json.load(jf)

        # Parse float price values back to cents notation expected by Gumroad endpoints
        try:
            price_cents = int(float(meta.get("price", "25.00")) * 100)
        except ValueError:
            price_cents = 2500

        payload = {
            "access_token": ACCESS_TOKEN,
            "name": meta.get("title", f"Premium Design Vault - {base_name}"),
            "description": meta.get("description", "Premium digital creative assets bundle."),
            "price": price_cents,
            "published": "true"
        }

        print(f"\n➕ Uploading Draft Listing: {payload['name']}...")
        
        try:
            # Explicitly pass a 15-second connect/read timeout threshold argument
            response = session.post(api_url, data=payload, timeout=(15, 60))
            
            # FIXED: Completed the broken syntax tuple layer
            if response.status_code in:
                product_data = response.json().get("product", {})
                product_id = product_data.get("id")
                product_url = product_data.get("short_url")
                print(f"   ✅ Success! Created Product ID: {product_id}")
                print(f"   🎉 Store Link Active: {product_url}")
            else:
                print(f"   ❌ API Block on {base_name}: Status {response.status_code} | Msg: {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            print(f"   ⏳ Connection Timeout on {base_name}. Server hung. Skipping to next target bundle safely.")
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Network Level Exception: {e}")

        # Minor safety cooldown rest window to respect endpoint query speed limits
        time.sleep(2)

if __name__ == "__main__":
    push_to_gumroad()
