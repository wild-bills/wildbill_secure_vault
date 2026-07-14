import os
import re
from urllib.parse import urlparse

DEFAULT_GUMROAD_STORE_URL = os.environ.get("GUMROAD_STORE_URL", "https://wildbill.gumroad.com/l")


def slugify_permalink(value: str) -> str:
    """Convert a title or SKU into a Gumroad-safe permalink slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    return slug.strip("-") or "item"


def normalize_gumroad_store_url(store_url: str | None = None) -> str:
    """Return the base Gumroad store URL without a trailing slash."""
    raw_url = (store_url or DEFAULT_GUMROAD_STORE_URL).strip()
    if not raw_url:
        raw_url = DEFAULT_GUMROAD_STORE_URL

    parsed = urlparse(raw_url)
    if parsed.scheme and parsed.netloc:
        normalized = raw_url.rstrip("/")
        return normalized

    return DEFAULT_GUMROAD_STORE_URL.rstrip("/")


def build_gumroad_permalink(value: str, prefix: str = "wildbill") -> str:
    """Build the custom permalink used for Gumroad bulk imports and checkout links."""
    slug = slugify_permalink(value)
    safe_prefix = slugify_permalink(prefix)
    return f"{safe_prefix}-{slug}" if safe_prefix else slug


def build_gumroad_url(value: str, store_url: str | None = None, prefix: str = "wildbill") -> str:
    """Build a full Gumroad product URL from a title, SKU, or bundle name."""
    base_url = normalize_gumroad_store_url(store_url)
    permalink = build_gumroad_permalink(value, prefix=prefix)
    return f"{base_url}/{permalink}"
