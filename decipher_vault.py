import os
import zipfile
import shutil
import re

# ----------------- CONFIGURATION ----------------- #
BACKUP_DIR = "/home/wildbill/vault_secure_backups"
SORTED_STORE_DIR = "/home/wildbill/adult_clipart_factory/fully_sorted_store"
TEMP_EXTRACT_DIR = "/home/wildbill/adult_clipart_factory/temp_decipher_ground"
# ------------------------------------------------- #

def clean_theme_name(filename):
    name = filename.lower().replace(".zip", "").replace("-mega-vault-vol1", "")
    name = re.sub(r'^(bundle_\d+_|adult_creator_)', '', name)
    return name.strip()

def decipher_and_sort():
    print("🔓 Initializing Vault Decipher Sequence...")
    
    if not os.path.exists(BACKUP_DIR):
        print(f"❌ Error: Backup folder '{BACKUP_DIR}' not found.")
        return

    # Create directories and clear old temp grounds
    os.makedirs(SORTED_STORE_DIR, exist_ok=True)
    if os.path.exists(TEMP_EXTRACT_DIR):
        shutil.rmtree(TEMP_EXTRACT_DIR)
    os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)

    outer_zips = [f for f in os.listdir(BACKUP_DIR) if f.lower().endswith('.zip')]
    print(f"📦 Found {len(outer_zips)} outer vault archives to unpack.")

    for idx, outer_zip in enumerate(sorted(outer_zips), start=1):
        outer_zip_path = os.path.join(BACKUP_DIR, outer_zip)
        theme_key = clean_theme_name(outer_zip)
        
        print(f"\n⚡ [{idx}/{len(outer_zips)}] Deciphering outer archive: '{outer_zip}'")
        
        current_temp_dir = os.path.join(TEMP_EXTRACT_DIR, f"temp_{idx}")
        os.makedirs(current_temp_dir, exist_ok=True)

        try:
            # STEP 1: Open the outer vault wrapper
            with zipfile.ZipFile(outer_zip_path, 'r') as outer_z:
                inner_names = [n for n in outer_z.namelist() if n.lower().endswith('.zip')]
                
                if not inner_names:
                    print("   ℹ️ No inner zip found. Checking for loose nested structures...")
                    outer_z.extractall(current_temp_dir)
                else:
                    # STEP 2: Extract the true embedded inner theme zip file
                    for inner_name in inner_names:
                        print(f"   🔓 Extracting inner asset container: '{inner_name}'")
                        outer_z.extract(inner_name, current_temp_dir)
                        inner_zip_path = os.path.join(current_temp_dir, inner_name)
                        
                        # STEP 3: Fully unpack the inner asset files into the work ground
                        with zipfile.ZipFile(inner_zip_path, 'r') as inner_z:
                            inner_z.extractall(current_temp_dir)
                        
                        # Remove the temporary inner zip to prevent archiving it again
                        os.remove(inner_zip_path)

            # STEP 4: Sort and restructure files dynamically by unified theme keywords
            # Scan everything we just extracted (images, cliparts, files)
            all_extracted_items = []
            for root, dirs, files in os.walk(current_temp_dir):
                for f in files:
                    if not f.startswith('.') and '__macosx' not in root.lower():
                        all_extracted_items.append(os.path.join(root, f))

            if not all_extracted_items:
                print("   ⚠️ Warning: No loose media found inside this archive branch.")
                continue

            # Establish a clean directory ground for this unique bundle theme
            final_bundle_folder_name = outer_zip.replace(".zip", "").replace("-mega-vault-vol1", "")
            final_bundle_path = os.path.join(SORTED_STORE_DIR, final_bundle_folder_name)
            os.makedirs(final_bundle_path, exist_ok=True)

            print(f"   📁 Sorting and bundling {len(all_extracted_items)} files strictly under theme profile...")
            
            image_extensions = ('.png', '.jpg', '.jpeg', '.webp')
            has_preview = False

            for item_path in all_extracted_items:
                file_name = os.path.basename(item_path)
                destination_file_path = os.path.join(final_bundle_path, file_name)
                
                # Copy loose assets directly into their clean home folder
                shutil.copy2(item_path, destination_file_path)

                # Ensure the first image found gets copied as a thumbnail master preview file
                if not has_preview and file_name.lower().endswith(image_extensions):
                    master_preview_dir = "/home/wildbill/wildbill_secure_vault/static/previews"
                    os.makedirs(master_preview_dir, exist_ok=True)
                    
                    img_ext = os.path.splitext(file_name)[1]
                    site_preview_path = os.path.join(master_preview_dir, f"{final_bundle_folder_name}{img_ext}")
                    shutil.copy2(item_path, site_preview_path)
                    has_preview = True

            # STEP 5: Zip up the newly sorted, clean folder for your customers
            final_zip_destination = os.path.join(SORTED_STORE_DIR, f"{final_bundle_folder_name}.zip")
            shutil.make_archive(os.path.join(SORTED_STORE_DIR, final_bundle_folder_name), 'zip', SORTED_STORE_DIR, final_bundle_folder_name)
            
            # Clean up the loose bundle folder, leaving only the pristine customer ZIP file behind
            shutil.rmtree(final_bundle_path)
            print(f"   ✅ Complete! Cleaned, unnested customer package built at: {final_bundle_folder_name}.zip")

        except Exception as e:
            print(f"   ❌ Critical error processing branch: {e}")
            continue

    # Wipe the temp processing folder clean to save hard drive space
    shutil.rmtree(TEMP_EXTRACT_DIR)
    print("\n🏁 Master Decipher complete! All files organized, unnested, and archived beautifully.")

if __name__ == "__main__":
    decipher_and_sort()
