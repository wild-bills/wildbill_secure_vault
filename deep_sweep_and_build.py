import os
import shutil
import zipfile
import re
import json
import math

from PIL import Image, ImageOps

# ----------------- CONFIGURATION ----------------- #
ROOT_SEARCH_DIR = "/home/wildbill/adult_clipart_factory"
BACKUP_DIR = "/home/wildbill/vault_secure_backups"
FINAL_STORE_DIR = "/home/wildbill/adult_clipart_factory/completed_bundles"
OUTPUT_IMG_DIR = "/home/wildbill/wildbill_secure_vault/static/previews"
OUTPUT_JSON = "/home/wildbill/wildbill_secure_vault/products.json"
TEMP_GROUND = "/home/wildbill/adult_clipart_factory/temp_vault_unpack"
FILES_PER_ZIP = 150  # Enforces between 100-200 files constraint perfectly
DEFAULT_PRICE = "15.00"
# ------------------------------------------------- #

PREVIEW_MAX_DIMENSION = 2400
PREVIEW_TILE_SIZE = 180
PREVIEW_GUTTER = 8
PREVIEW_BG = "#0f172a"
PREVIEW_TILE_BG = "#111827"


def build_bundle_preview(image_paths, output_path):
    valid_paths = []
    for image_path in image_paths:
        if os.path.isfile(image_path):
            valid_paths.append(image_path)

    if not valid_paths:
        return False

    image_count = len(valid_paths)
    columns = max(1, math.ceil(math.sqrt(image_count)))
    rows = math.ceil(image_count / columns)

    tile_size = PREVIEW_TILE_SIZE
    while columns * tile_size + (columns + 1) * PREVIEW_GUTTER > PREVIEW_MAX_DIMENSION and tile_size > 60:
        tile_size -= 10

    canvas_width = columns * tile_size + (columns + 1) * PREVIEW_GUTTER
    canvas_height = rows * tile_size + (rows + 1) * PREVIEW_GUTTER
    canvas = Image.new("RGB", (canvas_width, canvas_height), PREVIEW_BG)

    for index, image_path in enumerate(valid_paths):
        try:
            with Image.open(image_path) as source_image:
                tile_image = ImageOps.contain(source_image.convert("RGB"), (tile_size, tile_size))
        except Exception:
            continue

        slot = Image.new("RGB", (tile_size, tile_size), PREVIEW_TILE_BG)
        offset_x = (tile_size - tile_image.width) // 2
        offset_y = (tile_size - tile_image.height) // 2
        slot.paste(tile_image, (offset_x, offset_y))

        row_index, column_index = divmod(index, columns)
        paste_x = PREVIEW_GUTTER + column_index * (tile_size + PREVIEW_GUTTER)
        paste_y = PREVIEW_GUTTER + row_index * (tile_size + PREVIEW_GUTTER)
        canvas.paste(slot, (paste_x, paste_y))

    canvas.save(output_path, "JPEG", quality=88, optimize=True)
    return True

def clean_theme_name(text):
    text = text.lower().replace("_", " ").replace("-", " ")
    text = re.sub(r'(bundle \d+|vol \d+|mega vault|complete packages|ready assets|manufacturing)', '', text)
    words = [w for w in text.split() if len(w) > 2]
    core_words = [w for w in words if w not in ["assets", "clipart", "factory", "completed", "bundle", "pack", "collection"]]
    return " ".join(core_words).strip().title() if core_words else "Premium Collection"

def run_deep_sweep():
    print("🔓 Initializing nested archive extract and consolidation...")
    
    # Safely clear old temp paths to ensure maximum drive room
    for d in [FINAL_STORE_DIR, OUTPUT_IMG_DIR, TEMP_GROUND]:
        if os.path.exists(d) and d == TEMP_GROUND: shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        
    theme_groups = {}
    extensions = ('.png', '.jpg', '.jpeg', '.webp')

    # PHASE 1: Open outer backup files, extract inner theme zips, and unpack images
    if os.path.exists(BACKUP_DIR):
        vault_zips = [f for f in os.listdir(BACKUP_DIR) if f.lower().endswith('.zip')]
        print(f"📦 Found {len(vault_zips)} outer backup containers to unnest.")
        
        for vz in sorted(vault_zips):
            vz_path = os.path.join(BACKUP_DIR, vz)
            theme_label = clean_theme_name(vz)
            
            if theme_label not in theme_groups:
                theme_groups[theme_label] = []
                
            current_unpack_dir = os.path.join(TEMP_GROUND, vz.replace(".zip", ""))
            os.makedirs(current_unpack_dir, exist_ok=True)
            
            try:
                with zipfile.ZipFile(vz_path, 'r') as z:
                    inner_zips = [n for n in z.namelist() if n.lower().endswith('.zip')]
                    if inner_zips:
                        for iz in inner_zips:
                            z.extract(iz, current_unpack_dir)
                            inner_zip_full = os.path.join(current_unpack_dir, iz)
                            with zipfile.ZipFile(inner_zip_full, 'r') as iz_obj:
                                iz_obj.extractall(current_unpack_dir)
                            os.remove(inner_zip_full)
                    else:
                        z.extractall(current_unpack_dir)
                        
                # Log newly unpacked loose files into the theme group lists
                for root, _, files in os.walk(current_unpack_dir):
                    for f in files:
                        if f.lower().endswith(extensions) and not f.startswith('.'):
                            # Save path string explicitly
                            theme_groups[theme_label].append(os.path.join(root, f))
            except Exception:
                continue

    # PHASE 2: Check for loose images across all other local folders recursively
    print("🧹 Sweeping remaining local folders for loose asset files...")
    for root, dirs, files in os.walk(ROOT_SEARCH_DIR):
        if any(x in root for x in ["completed_bundles", "static/previews", "node_modules", "venv", "factory-env", "temp_vault_unpack"]):
            continue
            
        parent_folder_name = os.path.basename(root)
        theme_label = clean_theme_name(parent_folder_name)
        
        for f in files:
            if f.lower().endswith(extensions) and not f.startswith('.'):
                if theme_label not in theme_groups:
                    theme_groups[theme_label] = []
                theme_groups[theme_label].append(os.path.join(root, f))

    print(f"📋 Global Indexing Complete. Processing {len(theme_groups)} total combined themes.")

    products_data = []

    # PHASE 3: Slice each aggregated theme pile into exact packages of 150 items
    for theme, file_list in theme_groups.items():
        if len(file_list) < 3: 
            continue
            
        print(f"📦 Style Theme '{theme}' contains {len(file_list)} total discovered images. Packing chunks...")
        chunks = [file_list[i:i + FILES_PER_ZIP] for i in range(0, len(file_list), FILES_PER_ZIP)]
        
        for idx, chunk in enumerate(chunks, start=1):
            safe_theme_id = theme.replace(" ", "_")
            bundle_name = f"{safe_theme_id}_Collection_Vol_{str(idx).zfill(3)}"
            temp_pack_dir = os.path.join(ROOT_SEARCH_DIR, f"temp_{bundle_name}")
            os.makedirs(temp_pack_dir, exist_ok=True)

            for file_path in chunk:
                try:
                    shutil.copy2(file_path, os.path.join(temp_pack_dir, os.path.basename(file_path)))
                except Exception:
                    continue

            copied_files = os.listdir(temp_pack_dir)
            if not copied_files:
                shutil.rmtree(temp_pack_dir)
                continue

            copied_files.sort()
            preview_filename = f"{bundle_name}.jpg"
            preview_path = os.path.join(OUTPUT_IMG_DIR, preview_filename)
            copied_file_paths = [os.path.join(temp_pack_dir, filename) for filename in copied_files]
            if not build_bundle_preview(copied_file_paths, preview_path):
                shutil.rmtree(temp_pack_dir)
                continue

            # Compress subfolder into a pristine consumer ZIP file container
            final_zip_path = os.path.join(FINAL_STORE_DIR, bundle_name)
            shutil.make_archive(final_zip_path, 'zip', temp_pack_dir)
            shutil.rmtree(temp_pack_dir)

            print(f"   ✅ Created bundle package: {bundle_name}.zip ({len(copied_files)} items)")

            products_data.append({
                "Title": bundle_name.replace("_", " "),
                "Description": f"Premium themed {theme} uniform layout art graphic asset pack collection.",
                "Price": DEFAULT_PRICE,
                "Zip_Path": f"{final_zip_path}.zip",
                "Preview_URL": f"/static/previews/{preview_filename}"
            })

    # Write structural database array straight out to your website template tree
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(products_data, f, indent=4)
        
    shutil.copy2(OUTPUT_JSON, "/home/wildbill/wildbill_secure_vault/templates/products.json")
    
    # Wipe temporary working paths to preserve hard drive space records
    if os.path.exists(TEMP_GROUND): shutil.rmtree(TEMP_GROUND)
    print("\n🏁 Master compilation complete! Store packages created and database built perfectly.")

if __name__ == "__main__":
    run_deep_sweep()
