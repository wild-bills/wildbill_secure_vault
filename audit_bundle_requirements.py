#!/usr/bin/env python3
"""Audit bundle rules: file count must be between 150 and 200, and category must be present."""

import os
import sqlite3
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "store.db")
MIN_FILES = 150
MAX_FILES = 200


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT sku, name, theme, file_count FROM products ORDER BY id DESC"
    ).fetchall()
    conn.close()

    total = len(rows)
    missing_theme = []
    bad_file_count = []
    theme_counter = Counter()

    for row in rows:
        theme = (row["theme"] or "").strip()
        count = row["file_count"]

        if theme:
            theme_counter[theme.lower()] += 1
        else:
            missing_theme.append(row["sku"])

        if count is None or count < MIN_FILES or count > MAX_FILES:
            bad_file_count.append((row["sku"], count))

    print(f"Total bundles: {total}")
    print(f"Distinct themes: {len(theme_counter)}")
    print(f"Missing theme: {len(missing_theme)}")
    print(f"Outside {MIN_FILES}-{MAX_FILES} files: {len(bad_file_count)}")

    if theme_counter:
        print("Top theme distribution:")
        for theme, qty in theme_counter.most_common(15):
            print(f"  - {theme}: {qty}")

    if bad_file_count:
        print("Sample bundles outside file-count range:")
        for sku, count in bad_file_count[:30]:
            print(f"  - {sku}: {count}")

    # Non-zero exit if requirements are not met.
    return 1 if missing_theme or bad_file_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
