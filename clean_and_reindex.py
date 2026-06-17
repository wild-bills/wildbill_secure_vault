import os
import zipfile
import hashlib
import sqlite3

VAULT_DIR = os.path.expanduser('~/vault_secure_backups')
DB_PATH = os.path.expanduser('~/wildbill_secure_vault/database/store.db')

def remove_dupes_and_reindex():
    if not os.path.exists(VAULT_DIR):
        print(f"❌ Error: Folder '{VAULT_DIR}' does not exist.")
        return

    all_files = os.listdir(VAULT_DIR)
    zip_files = sorted([f for f in all_files if f.lower().endswith('.zip')])

    print(f"🔍 Starting clean reindex on {len(zip_files)} source archives...")

    fingerprints = {}
    unique_zip_paths = []

    # 1. Identify true unique files based on contents
    for z_name in zip_files:
        z_path = os.path.join(VAULT_DIR, z_name)
        file_hashes = []
        
        try:
            with zipfile.ZipFile(z_path, 'r') as archive:
                for internal_file in sorted(archive.namelist()):
                    if internal_file.startswith('__MACOSX') or internal_file.endswith('/'):
                        continue
                    try:
                        with archive.open(internal_file) as f:
                            file_hashes.append(hashlib.md5(f.read()).hexdigest())
                    except:
                        pass
        except:
            continue

        if not file_hashes:
            continue

        master_hash = hashlib.md5(",".join(file_hashes).encode('utf-8')).hexdigest()

        if master_hash not in fingerprints:
            fingerprints[master_hash] = z_name
            unique_zip_paths.append(z_path)
        else:
            # Delete duplicate copy immediately to clear storage space safely
            print(f"🗑️ Deleting duplicate copy: {z_name} (Matches contents of {fingerprints[master_hash]})")
            os.remove(z_path)

    print(f"\n✨ Remaining unique archives: {len(unique_zip_paths)}")
    print("🔢 Re-indexing file names to sequential wb-art-### format...")

    # 2. Rename unique files sequentially to eliminate gaps
    final_zip_registry = []
    for index, old_path in enumerate(unique_zip_paths):
        new_sku = f"WB-ART-{index + 1:03d}"
        new_filename = f"{new_sku.lower()}.zip"
        new_path = os.path.join(VAULT_DIR, new_filename)
        
        # Temporary rename handle avoids file collision locks
        temp_path = old_path + ".tmp"
        os.rename(old_path, temp_path)
        final_zip_registry.append((temp_path, new_path, new_sku, new_filename))

    for temp_path, new_path, sku, filename in final_zip_registry:
        os.rename(temp_path, new_path)
        print(f"   Mapped to -> {filename}")

    print("\n🏁 File system re-indexed successfully. Ready to run your database extraction tools!")

if __name__ == '__main__':
    remove_dupes_and_reindex()
