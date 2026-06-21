import os
from b2sdk.v2 import InMemoryAccountInfo, B2Api

# --- BACKBLAZE CREDENTIALS ---
B2_KEY_ID = "005a9b63ec462530000000002"
B2_APPLICATION_KEY = "K005l0PuojaZ6sv1IiHJgJAoJkxiDp8"
B2_BUCKET_NAME = "wildbill-vault-zips"
LOCAL_TARGET_DIR = "/home/wildbill/all_combined_zips"

def download_all_zips():
    if not os.path.exists(LOCAL_TARGET_DIR):
        os.makedirs(LOCAL_TARGET_DIR)

    print("🔑 Connecting to Backblaze B2 cloud storage...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
    
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
    print(f"🛰️ Scanning bucket '{B2_BUCKET_NAME}' for files...")

    # List and loop through all items currently stored on B2
    for file_version, _ in bucket.ls():
        file_name = file_version.file_name
        
        # Only pull down the zip packages, skip folders or subdirectories
        if file_name.endswith('.zip'):
            local_path = os.path.join(LOCAL_TARGET_DIR, file_name)
            
            # Simple skip block so it doesn't waste time re-downloading files you already have local
            if os.path.exists(local_path):
                print(f"⏭️ Skipping {file_name} (Already downloaded local)")
                continue
                
            print(f"📥 Downloading: {file_name} -> {LOCAL_TARGET_DIR}")
            try:
                downloaded_file = bucket.download_file_by_name(file_name)
                downloaded_file.save_to(local_path)
                print(f"✅ Finished: {file_name}")
            except Exception as e:
                print(f"❌ Error downloading {file_name}: {e}")

    print("\n🚀 All Backblaze cloud zips successfully synced down to your drive workspace!")

if __name__ == "__main__":
    download_all_zips()
