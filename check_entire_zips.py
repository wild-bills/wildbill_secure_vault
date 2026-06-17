import os
import zipfile
import hashlib

VAULT_DIR = os.path.expanduser('~/vault_secure_backups')

def scan_for_clone_zips():
    if not os.path.exists(VAULT_DIR):
        print(f"❌ Error: The directory '{VAULT_DIR}' does not exist.")
        return

    all_files = os.listdir(VAULT_DIR)
    zip_files = sorted([f for f in all_files if f.lower().endswith('.zip')])

    if not zip_files:
        print(f"❌ Error: No ZIP files found inside {VAULT_DIR}")
        return

    print(f"🔍 Analyzing {len(zip_files)} packages to identify identical bundle clones...\n")

    # Maps a unique structural fingerprint string to a list of matching zip filenames
    zip_fingerprints = {}

    for z_name in zip_files:
        z_path = os.path.join(VAULT_DIR, z_name)
        file_hashes = []
        
        try:
            with zipfile.ZipFile(z_path, 'r') as archive:
                # Sort filenames to ensure order differences don't mask matching data content
                for internal_file in sorted(archive.namelist()):
                    if internal_file.startswith('__MACOSX') or internal_file.endswith('/'):
                        continue
                    try:
                        with archive.open(internal_file) as f:
                            # Generate a fingerprinted state hash for the specific data piece
                            file_hash = hashlib.md5(f.read()).hexdigest()
                            file_hashes.append(file_hash)
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ Could not process archive {z_name}: {e}")
            continue

        if not file_hashes:
            continue

        # Combine all internal fingerprints sequentially to generate a master fingerprint string for the package
        master_string = ",".join(file_hashes)
        zip_master_hash = hashlib.md5(master_string.encode('utf-8')).hexdigest()

        if zip_master_hash not in zip_fingerprints:
            zip_fingerprints[zip_master_hash] = []
        zip_fingerprints[zip_master_hash].append(z_name)

    # Filter out combinations that map out to multiple matching filenames
    clones = {h: names for h, names in zip_fingerprints.items() if len(names) > 1}

    if not clones:
        print("🎉 Clean Bill of Health: No two ZIP archives contain the exact same contents.")
        return

    print(f"⚠️ Warning: Found {len(clones)} identical duplicate ZIP file pairs. These packages contain the exact same contents:\n")
    
    match_id = 0
    for master_hash, matching_zips in clones.items():
        match_id += 1
        print(f"🔄 Identical Bundle Matching Group #{match_id}:")
        for filename in matching_zips:
            print(f"   📦 {filename}")
        print("   💡 Action: You can delete or ignore the extra copy strings safely.\n")

if __name__ == '__main__':
    scan_for_clone_zips()
