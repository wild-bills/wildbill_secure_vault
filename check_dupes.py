import os
import zipfile
import hashlib
from collections import defaultdict

VAULT_DIR = os.path.expanduser('~/vault_secure_backups')

def scan_for_internal_duplicates():
    if not os.path.exists(VAULT_DIR):
        print(f"❌ Error: The folder '{VAULT_DIR}' does not exist.")
        return

    all_files = os.listdir(VAULT_DIR)
    zip_files = sorted([f for f in all_files if f.lower().endswith('.zip')])

    if not zip_files:
        print(f"❌ Error: No ZIP files found inside {VAULT_DIR}")
        return

    print(f"🔍 Deep scanning {len(zip_files)} archives for internal file content duplicates...\n")

    # Tracking storage configurations
    # Maps file hashes to lists of (zip_filename, internal_filename)
    content_tracker = defaultdict(list)
    
    for z_name in zip_files:
        z_path = os.path.join(VAULT_DIR, z_name)
        
        try:
            with zipfile.ZipFile(z_path, 'r') as archive:
                for internal_file in archive.namelist():
                    # Skip system files and folder descriptors
                    if internal_file.startswith('__MACOSX') or internal_file.endswith('/'):
                        continue
                        
                    try:
                        with archive.open(internal_file) as f:
                            # Read data file block to parse cryptographic fingerprints
                            file_data = f.read()
                            file_hash = hashlib.md5(file_data).hexdigest()
                            
                            # Track where this specific content piece lives
                            content_tracker[file_hash].append((z_name, internal_file))
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ Could not read archive {z_name}: {e}")

    # Process and print out duplicate findings report
    duplicate_groups = {h: paths for h, paths in content_tracker.items() if len(paths) > 1}
    
    if not duplicate_groups:
        print("🎉 Excellent! No duplicate files or asset overlaps found across your ZIP bundles.")
        return

    print(f"⚠️ Detected {len(duplicate_groups)} instances of duplicated contents cross-linked inside your packages:\n")
    
    group_num = 0
    for file_hash, locations in duplicate_groups.items():
        group_num += 1
        print(f"--- Duplicate Group #{group_num} (Hash: {file_hash}) ---")
        for zip_parent, file_item in locations:
            print(f" 📦 Inside: {zip_parent} -> Path: {file_item}")
        print()

if __name__ == '__main__':
    scan_for_internal_duplicates()
