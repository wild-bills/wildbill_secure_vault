import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from gumroad_utils import build_gumroad_permalink

# ----------------- CONFIGURATION ----------------- #
GUMROAD_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "7UAA_2Bu6PLFQslkhCAHCrwmdh16XHh3HE17HNdLoTg")
BASE_URL = "https://api.gumroad.com/v2"
CATALOG_FILE = Path("products.json")
RESUME_STATE_FILE = Path("upload_local_zips.resume.json")
LOCAL_BUNDLE_DIR = Path("/run/media/wildbill/storage/completed_bundles")
LOCAL_PREVIEW_DIR = Path(__file__).resolve().parent / "static" / "previews"
# ------------------------------------------------- #


def load_catalog_rows():
    if not CATALOG_FILE.exists():
        raise FileNotFoundError(f"Missing catalog file: {CATALOG_FILE}")

    with CATALOG_FILE.open("r", encoding="utf-8") as file_handle:
        rows = json.load(file_handle)

    if not isinstance(rows, list):
        raise ValueError("products.json must contain a top-level list")

    return rows


def load_resume_state():
    if not RESUME_STATE_FILE.exists():
        return {}

    try:
        with RESUME_STATE_FILE.open("r", encoding="utf-8") as file_handle:
            state = json.load(file_handle)
    except Exception:
        return {}

    return state if isinstance(state, dict) else {}


def save_resume_state(state):
    temp_file = RESUME_STATE_FILE.with_suffix(".resume.tmp")
    with temp_file.open("w", encoding="utf-8") as file_handle:
        json.dump(state, file_handle, indent=2)
        file_handle.write("\n")
    temp_file.replace(RESUME_STATE_FILE)


def clear_resume_state():
    if RESUME_STATE_FILE.exists():
        RESUME_STATE_FILE.unlink()


def get_all_gumroad_products():
    print("🔍 Fetching your current Gumroad products...")

    response = requests.get(f"{BASE_URL}/products", params={"access_token": GUMROAD_TOKEN})
    if response.status_code != 200:
        print(f"❌ Failed to contact Gumroad API. Code: {response.status_code}")
        return []

    try:
        return response.json().get("products", [])
    except Exception:
        print("❌ Server returned non-JSON data. Please double-check your API token permissions.")
        return []


def create_gumroad_product(title, description, price):
    payload = {
        "access_token": GUMROAD_TOKEN,
        "name": title,
        "description": description,
        "price": str(int(float(price) * 100)),
        "product_type": "digital",
        "published": "true",
    }

    response = requests.post(f"{BASE_URL}/products", data=payload)
    if response.status_code == 429:
        print(f"   ⏸️ Gumroad rate-limited listing creation for '{title}'.")
        return None, True

    if response.status_code not in (200, 201):
        print(f"   ❌ Failed to create listing '{title}'. Code: {response.status_code}")
        print(f"   Details: {response.text[:250]}")
        return None, False

    try:
        response_json = response.json()
    except Exception:
        print(f"   ❌ Gumroad returned invalid JSON while creating '{title}'.")
        return None, False

    product_data = response_json.get("product", response_json)
    return product_data.get("id"), False


def get_gumroad_product(product_id):
    response = requests.get(f"{BASE_URL}/products/{product_id}", params={"access_token": GUMROAD_TOKEN})
    if response.status_code != 200:
        return {}

    try:
        return response.json().get("product", {})
    except Exception:
        return {}


def product_has_matching_file(product_data, zip_filename):
    for file_item in product_data.get("files", []) or []:
        file_name = str(file_item.get("name") or file_item.get("display_name") or "")
        if file_name == zip_filename:
            return True
    return False


def extract_permalink(row):
    gumroad_url = str(row.get("Gumroad_URL") or "").strip()
    if gumroad_url:
        parsed = urlparse(gumroad_url)
        permalink = parsed.path.rstrip("/").split("/")[-1]
        if permalink:
            return permalink

    return build_gumroad_permalink(str(row.get("Title") or row.get("name") or "item"))


def upload_zip_to_gumroad_storage(zip_path):
    presign_response = requests.post(
        f"{BASE_URL}/files/presign",
        data={
            "access_token": GUMROAD_TOKEN,
            "filename": zip_path.name,
            "file_size": str(zip_path.stat().st_size),
        },
    )

    if presign_response.status_code == 429:
        print(f"   ⏸️ Gumroad rate-limited file upload for {zip_path.name}.")
        return None, True

    if presign_response.status_code != 200:
        print(f"   ❌ Presign failed for {zip_path.name}. Code: {presign_response.status_code}")
        print(f"   Details: {presign_response.text[:250]}")
        return None, False

    try:
        presign_json = presign_response.json()
    except Exception:
        print(f"   ❌ Gumroad returned invalid presign JSON for {zip_path.name}.")
        return None, False

    upload_id = presign_json.get("upload_id")
    key = presign_json.get("key")
    parts = presign_json.get("parts") or []
    if not upload_id or not key or not parts:
        print(f"   ❌ Gumroad presign response was incomplete for {zip_path.name}.")
        return None, False

    first_part = parts[0]
    presigned_url = first_part.get("presigned_url")
    part_number = first_part.get("part_number", 1)
    if not presigned_url:
        print(f"   ❌ Missing presigned upload URL for {zip_path.name}.")
        return None, False

    with zip_path.open("rb") as file_handle:
        upload_response = requests.put(presigned_url, data=file_handle.read())

    if upload_response.status_code not in (200, 201):
        print(f"   ❌ File upload failed for {zip_path.name}. Code: {upload_response.status_code}")
        print(f"   Details: {upload_response.text[:250]}")
        return None, False

    etag = upload_response.headers.get("ETag", "").strip('"')
    if not etag:
        print(f"   ❌ Gumroad upload finished without an ETag for {zip_path.name}.")
        return None, False

    complete_response = requests.post(
        f"{BASE_URL}/files/complete",
        data={
            "access_token": GUMROAD_TOKEN,
            "upload_id": upload_id,
            "key": key,
            "parts[][part_number]": str(part_number),
            "parts[][etag]": etag,
        },
    )

    if complete_response.status_code == 429:
        print(f"   ⏸️ Gumroad rate-limited file completion for {zip_path.name}.")
        return None, True

    if complete_response.status_code != 200:
        print(f"   ❌ File completion failed for {zip_path.name}. Code: {complete_response.status_code}")
        print(f"   Details: {complete_response.text[:250]}")
        return None, False

    try:
        complete_json = complete_response.json()
    except Exception:
        print(f"   ❌ Gumroad returned invalid completion JSON for {zip_path.name}.")
        return None, False

    file_url = complete_json.get("file_url")
    if not file_url:
        print(f"   ❌ Gumroad did not return a file_url for {zip_path.name}.")
        return None, False

    return file_url, False


def build_file_payload(existing_files, file_url):
    payload = []
    for file_item in existing_files or []:
        existing_id = file_item.get("id")
        existing_url = file_item.get("url")
        if existing_id and existing_url:
            payload.append(("files[][id]", str(existing_id)))
            payload.append(("files[][url]", str(existing_url)))

    payload.append(("files[][url]", file_url))
    return payload


def resolve_local_zip_path(row):
    zip_path = Path(str(row.get("Zip_Path") or "")).expanduser()
    if zip_path.is_absolute() and zip_path.exists():
        return zip_path

    zip_name = zip_path.name or Path(str(row.get("Zip_URL") or "")).name
    candidates = [
        LOCAL_BUNDLE_DIR / zip_name,
        Path("/home/wildbill/adult_clipart_factory/completed_bundles") / zip_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resolve_local_preview_path(row):
    preview_value = str(row.get("Preview_URL") or "")
    preview_name = Path(preview_value).name
    candidates = []

    if preview_value.startswith("/static/previews/"):
        candidates.append(Path(__file__).resolve().parent / preview_value.lstrip("/"))

    candidates.extend([
        LOCAL_PREVIEW_DIR / preview_name,
        LOCAL_BUNDLE_DIR / preview_name,
        Path(preview_value).expanduser(),
    ])

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def upload_physical_files():
    live_products = get_all_gumroad_products()
    product_map = {p.get("name", "").strip().lower(): p.get("id") for p in live_products if p.get("name") and p.get("id")}

    rows = load_catalog_rows()
    print(f"📋 Loaded {len(rows)} catalog rows from {CATALOG_FILE}.")

    resume_state = load_resume_state()
    start_index = 0
    if resume_state:
        resume_title = str(resume_state.get("title") or "").strip().lower()
        resume_zip = str(resume_state.get("zip_filename") or "").strip()
        resume_index = int(resume_state.get("last_completed_index") or 0)
        for row_index, row in enumerate(rows, start=1):
            row_title = str(row.get("Title") or "").strip().lower()
            row_zip_name = Path(str(row.get("Zip_Path") or "")).name or Path(str(row.get("Zip_URL") or "")).name
            if row_title == resume_title and row_zip_name == resume_zip:
                start_index = row_index
                break
        else:
            if 0 < resume_index < len(rows):
                start_index = resume_index

    if start_index:
        print(f"🔁 Resuming after row {start_index} from {RESUME_STATE_FILE}.")

    success_count = 0
    created_count = 0
    stop_requested = False

    for index, row in enumerate(rows, start=1):
        if start_index and index <= start_index:
            continue

        title = str(row.get("Title") or "").strip()
        description = str(row.get("Description") or "Premium digital asset bundle collection.")
        price = str(row.get("Price") or "15.00")
        title_key = title.lower()
        zip_path = resolve_local_zip_path(row)
        preview_path = resolve_local_preview_path(row)

        if not title:
            print(f"⚠️ Row [{index}]: skipped because the title is empty.")
            continue

        if title_key not in product_map:
            print(f"\n➕ Row [{index}]: creating missing Gumroad listing for '{title}'...")
            product_id, should_stop = create_gumroad_product(title, description, price)
            if should_stop:
                stop_requested = True
                break
            if not product_id:
                continue
            product_map[title_key] = product_id
            created_count += 1
        else:
            product_id = product_map[title_key]

        if not zip_path.exists():
            print(f"⚠️ Row [{index}]: skipped '{title}'. ZIP not found at {zip_path}")
            continue

        existing_product = get_gumroad_product(product_id)
        zip_filename = zip_path.name
        permalink = extract_permalink(row)

        if existing_product and product_has_matching_file(existing_product, zip_filename):
            print(f"\n📦 Processing [{index}]: '{title}' already has {zip_filename}, skipping file upload.")
            save_resume_state({
                "last_completed_index": index,
                "title": title,
                "zip_filename": zip_filename,
                "updated_at": int(time.time()),
            })
            continue

        print(f"\n📦 Processing [{index}]: '{title}'")

        file_url, should_stop = upload_zip_to_gumroad_storage(zip_path)
        if should_stop:
            stop_requested = True
            break
        if not file_url:
            continue

        update_payload = [
            ("access_token", GUMROAD_TOKEN),
            ("name", title),
            ("description", description),
            ("price", str(int(float(price) * 100))),
            ("custom_permalink", permalink),
            ("published", "true"),
        ]

        if existing_product.get("files"):
            update_payload.extend(build_file_payload(existing_product.get("files"), file_url))
            response = requests.put(f"{BASE_URL}/products/{product_id}", data=update_payload)
        else:
            update_payload.append(("files[][url]", file_url))
            response = requests.put(f"{BASE_URL}/products/{product_id}", data=update_payload)

        if response.status_code == 429:
            print(f"   ⏸️ Gumroad rate-limited product update for '{title}'.")
            stop_requested = True
            break

        if response.status_code in (200, 201):
            print(f"   ✅ Attached ZIP to '{title}'.")
            success_count += 1
            save_resume_state({
                "last_completed_index": index,
                "title": title,
                "zip_filename": zip_filename,
                "updated_at": int(time.time()),
            })
        else:
            print(f"   ❌ Upload failed for '{title}'. Code: {response.status_code}")
            print(f"   Details: {response.text[:250]}")

        time.sleep(2)

    if not stop_requested:
        clear_resume_state()

    print(f"\n🏁 Complete! Created {created_count} missing listings and uploaded {success_count} ZIP files.")


if __name__ == "__main__":
    upload_physical_files()
