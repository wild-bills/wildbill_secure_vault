import json
import os
import tempfile
import zipfile
from pathlib import Path

from deep_sweep_and_build import build_bundle_preview


BASE_DIR = Path(__file__).resolve().parent
PRODUCTS_JSON = BASE_DIR / "products.json"
PREVIEW_DIR = BASE_DIR / "static" / "previews"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def collect_preview_sources(zip_path: Path, temp_dir: Path) -> list[str]:
    extracted_paths = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        image_members = [
            member for member in archive.namelist()
            if Path(member).suffix.lower() in IMAGE_EXTENSIONS and not member.endswith("/")
        ]

        for index, member in enumerate(sorted(image_members), start=1):
            suffix = Path(member).suffix.lower()
            target_path = temp_dir / f"{index:04d}{suffix}"
            with archive.open(member) as source, open(target_path, "wb") as destination:
                destination.write(source.read())
            extracted_paths.append(str(target_path))

    return extracted_paths


def build_all_previews() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    with open(PRODUCTS_JSON, "r", encoding="utf-8") as handle:
        products = json.load(handle)

    built = 0
    skipped = 0

    for product in products:
        zip_path = Path(product.get("Zip_Path", ""))
        preview_url = product.get("Preview_URL", "")
        preview_name = Path(preview_url).name

        if not zip_path.is_file() or not preview_name:
            skipped += 1
            continue

        preview_path = PREVIEW_DIR / preview_name
        with tempfile.TemporaryDirectory(prefix="preview-build-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            image_paths = collect_preview_sources(zip_path, temp_dir)
            if not image_paths:
                skipped += 1
                continue

            if build_bundle_preview(image_paths, str(preview_path)):
                built += 1
                print(f"Built {preview_path.name} from {zip_path.name} ({len(image_paths)} images)")
            else:
                skipped += 1

    print(f"Finished preview rebuild. Built {built}, skipped {skipped}.")


if __name__ == "__main__":
    build_all_previews()
