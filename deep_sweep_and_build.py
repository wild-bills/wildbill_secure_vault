import json
import math
import os
import re
import shutil
import zipfile

from PIL import Image, ImageOps

# ----------------- CONFIGURATION ----------------- #
ROOT_SEARCH_DIR = "/home/wildbill/adult_clipart_factory"
BACKUP_DIR = "/home/wildbill/vault_secure_backups"
FINAL_STORE_DIR = os.environ.get("VAULT_FINAL_STORE_DIR", "/run/media/wildbill/storage/completed_bundles")
OUTPUT_IMG_DIR = "/home/wildbill/wildbill_secure_vault/static/previews"
OUTPUT_JSON = "/home/wildbill/wildbill_secure_vault/products.json"
TEMP_GROUND = os.environ.get("VAULT_TEMP_GROUND", "/run/media/wildbill/storage/temp_vault_unpack")
PACK_STAGING_DIR = os.environ.get("VAULT_PACK_STAGING_DIR", "/run/media/wildbill/storage/bundle_pack_staging")
FILES_PER_ZIP = 150
MIN_FILES_PER_ZIP = 100
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
    text = re.sub(r"(bundle \d+|vol \d+|mega vault|complete packages|ready assets|manufacturing)", "", text)
    words = [word for word in text.split() if len(word) > 2]
    core_words = [
        word for word in words
        if word not in ["assets", "clipart", "factory", "completed", "bundle", "pack", "collection"]
    ]
    return " ".join(core_words).strip().title() if core_words else "Premium Collection"


def resolve_local_theme_label(root_path):
    relative_root = os.path.relpath(root_path, ROOT_SEARCH_DIR)
    if relative_root in (".", ""):
        return None

    top_level_folder = relative_root.split(os.sep, 1)[0]
    normalized_name = re.sub(r"[_.\-]+", " ", top_level_folder).strip()
    return normalized_name.title() if normalized_name else None


def split_theme_files(file_list):
    total_files = len(file_list)
    if total_files < MIN_FILES_PER_ZIP:
        return []

    chunk_count = max(1, math.ceil(total_files / FILES_PER_ZIP))
    while chunk_count > 1 and total_files / chunk_count < MIN_FILES_PER_ZIP:
        chunk_count -= 1

    base_size = total_files // chunk_count
    remainder = total_files % chunk_count
    chunks = []
    start_index = 0

    for chunk_index in range(chunk_count):
        chunk_size = base_size + (1 if chunk_index < remainder else 0)
        end_index = start_index + chunk_size
        chunks.append(file_list[start_index:end_index])
        start_index = end_index

    return chunks


def reset_generated_directories():
    for directory_path in [FINAL_STORE_DIR, OUTPUT_IMG_DIR, TEMP_GROUND, PACK_STAGING_DIR]:
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
        os.makedirs(directory_path, exist_ok=True)


def collect_backup_theme_groups(theme_groups, extensions):
    if not os.path.exists(BACKUP_DIR):
        return

    vault_zips = [filename for filename in os.listdir(BACKUP_DIR) if filename.lower().endswith(".zip")]
    print(f"📦 Found {len(vault_zips)} outer backup containers to unnest.")

    for vault_zip in sorted(vault_zips):
        vault_zip_path = os.path.join(BACKUP_DIR, vault_zip)
        theme_label = clean_theme_name(vault_zip)
        theme_groups.setdefault(theme_label, [])

        current_unpack_dir = os.path.join(TEMP_GROUND, vault_zip.replace(".zip", ""))
        os.makedirs(current_unpack_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(vault_zip_path, "r") as archive:
                inner_zips = [name for name in archive.namelist() if name.lower().endswith(".zip")]
                if inner_zips:
                    for inner_zip_name in inner_zips:
                        archive.extract(inner_zip_name, current_unpack_dir)
                        inner_zip_full = os.path.join(current_unpack_dir, inner_zip_name)
                        with zipfile.ZipFile(inner_zip_full, "r") as inner_archive:
                            inner_archive.extractall(current_unpack_dir)
                        os.remove(inner_zip_full)
                else:
                    archive.extractall(current_unpack_dir)

            for root, _, files in os.walk(current_unpack_dir):
                for filename in files:
                    if filename.lower().endswith(extensions) and not filename.startswith("."):
                        theme_groups[theme_label].append(os.path.join(root, filename))
        except Exception:
            continue


def collect_local_theme_groups(theme_groups, extensions):
    print("🧹 Sweeping remaining local folders for loose asset files...")
    excluded_root_fragments = [
        "completed_bundles",
        "static/previews",
        "node_modules",
        "venv",
        "factory-env",
        "temp_vault_unpack",
        "bundle_pack_staging",
    ]

    for root, _, files in os.walk(ROOT_SEARCH_DIR):
        if any(fragment in root for fragment in excluded_root_fragments):
            continue

        theme_label = resolve_local_theme_label(root)
        if not theme_label:
            continue

        for filename in files:
            if filename.lower().endswith(extensions) and not filename.startswith("."):
                theme_groups.setdefault(theme_label, []).append(os.path.join(root, filename))


def package_theme_chunks(theme_groups):
    products_data = []

    for theme, file_list in theme_groups.items():
        unique_files = sorted(dict.fromkeys(file_list))
        if len(unique_files) < MIN_FILES_PER_ZIP:
            print(f"⏭️ Skipping theme '{theme}' because it only has {len(unique_files)} files.")
            continue

        print(f"📦 Style Theme '{theme}' contains {len(unique_files)} total discovered images. Packing chunks...")
        chunks = split_theme_files(unique_files)

        for index, chunk in enumerate(chunks, start=1):
            safe_theme_id = theme.replace(" ", "_")
            bundle_name = f"{safe_theme_id}_Collection_Vol_{str(index).zfill(3)}"
            temp_pack_dir = os.path.join(PACK_STAGING_DIR, f"temp_{bundle_name}")
            os.makedirs(temp_pack_dir, exist_ok=True)

            for file_path in chunk:
                try:
                    shutil.copy2(file_path, os.path.join(temp_pack_dir, os.path.basename(file_path)))
                except Exception:
                    continue

            copied_files = sorted(os.listdir(temp_pack_dir))
            if not copied_files:
                shutil.rmtree(temp_pack_dir)
                continue

            preview_filename = f"{bundle_name}.jpg"
            preview_path = os.path.join(OUTPUT_IMG_DIR, preview_filename)
            copied_file_paths = [os.path.join(temp_pack_dir, filename) for filename in copied_files]
            if not build_bundle_preview(copied_file_paths, preview_path):
                shutil.rmtree(temp_pack_dir)
                continue

            final_zip_path = os.path.join(FINAL_STORE_DIR, bundle_name)
            shutil.make_archive(final_zip_path, "zip", temp_pack_dir)
            shutil.rmtree(temp_pack_dir)

            print(f"   ✅ Created bundle package: {bundle_name}.zip ({len(copied_files)} items)")
            products_data.append({
                "Title": bundle_name.replace("_", " "),
                "Description": f"Premium themed {theme} uniform layout art graphic asset pack collection.",
                "Price": DEFAULT_PRICE,
                "Zip_Path": f"{final_zip_path}.zip",
                "Preview_URL": f"/static/previews/{preview_filename}",
            })

    return products_data


def run_deep_sweep():
    print("🔓 Initializing nested archive extract and consolidation...")
    reset_generated_directories()

    theme_groups = {}
    extensions = (".png", ".jpg", ".jpeg", ".webp")

    collect_backup_theme_groups(theme_groups, extensions)
    collect_local_theme_groups(theme_groups, extensions)

    print(f"📋 Global Indexing Complete. Processing {len(theme_groups)} total combined themes.")
    products_data = package_theme_chunks(theme_groups)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as output_handle:
        json.dump(products_data, output_handle, indent=4)

    shutil.copy2(OUTPUT_JSON, "/home/wildbill/wildbill_secure_vault/templates/products.json")

    if os.path.exists(TEMP_GROUND):
        shutil.rmtree(TEMP_GROUND)
    if os.path.exists(PACK_STAGING_DIR):
        shutil.rmtree(PACK_STAGING_DIR)

    print("\n🏁 Master compilation complete! Store packages created and database built perfectly.")


if __name__ == "__main__":
    run_deep_sweep()
