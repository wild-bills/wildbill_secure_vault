import os
import zipfile
from datetime import datetime

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# The local directory where your actual website files are stored
WEBSITE_SOURCE_DIR = "/home/wildbill/wildbill_secure_vault"

# Where to save the clean, compressed website package
OUTPUT_ZIP_FILE = "/home/wildbill/wildbill_secure_vault/core_website_upload.zip"

# Directories you want to completely skip to avoid huge file sizes/timeouts
FOLDERS_TO_IGNORE = [
    "adult_graphics_factory",
    "adult_clipart_factory",
    "contenttosell",
    ".git",
    "cache"
]

# ==============================================================================
# ZIP ARCHIVE ENGINE
# ==============================================================================
def bundle_website_core():
    # Convert path notation back to system paths
    src_dir = WEBSITE_SOURCE_DIR.replace("slash ", "/").strip()
    dest_zip = OUTPUT_ZIP_FILE.replace("slash ", "/").strip()
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bundling core website files...")
    print(f"Source folder: {src_dir}")
    
    if not os.path.exists(src_dir):
        print(f"ERROR: Source path {src_dir} not found.")
        return

    # Initialize zip archive writer
    with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zip_engine:
        file_count = 0
        
        for root, dirs, files in os.walk(src_dir):
            # Modify dirs in-place to prune excluded folders from the walk tree
            dirs[:] = [d for d in dirs if d not in FOLDERS_TO_IGNORE]
            
            for file in files:
                # Do not accidentally package existing zip files
                if file.endswith(".zip") or file.endswith(".tar.gz"):
                    continue
                    
                full_file_path = os.path.join(root, file)
                
                # Maintain exact relative positioning for server path matrix
                relative_path = os.path.relpath(full_file_path, src_dir)
                
                zip_engine.write(full_file_path, relative_path)
                file_count += 1

    print("=" * 60)
    print(f"SUCCESS: Packaged {file_count} core system files.")
    print(f"Clean archive ready: {dest_zip}")
    print("=" * 60)

if __name__ == "__main__":
    bundle_website_core()
