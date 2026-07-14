import sqlite3
import os

from gumroad_utils import build_gumroad_permalink

DB_PATH = "database/store.db"
CSV_PATH = "gumroad_bulk_import.csv"

def export_vault_to_csv():
    if not os.path.exists(DB_PATH):
        print(f"❌ Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT sku, name, theme, file_count FROM products WHERE file_count > 0")
    rows = cursor.fetchall()
    conn.close()

    print(f"📦 Compiling spreadsheet rows for {len(rows)} vault packages...")

    with open(CSV_PATH, 'w', encoding='utf-8') as f:
        # These are the exact headers Gumroad's bulk tool looks for
        f.write("Name,Price,Description,Custom Permalink\n")
        
        for item in rows:
            clean_name = item['name'].replace('_', ' ')
            clean_theme = item['theme'].replace('_', ' ')
            
            file_qty = item['file_count']
            if file_qty <= 50:
                price_text = "4.99"
            elif file_qty > 50 and file_qty < 600:
                price_text = "14.99"
            else:
                price_text = "39.99"

            desc = (
                f"Unlock premium access to the {clean_name} collection! "
                f"• Total assets: {file_qty} files "
                f"• Category: {clean_theme} "
                f"• Complete licensing usage rights included."
            )
            desc_clean = desc.replace('"', '""').replace('\n', ' ')

            permalink = build_gumroad_permalink(item["sku"])
            f.write(f'"{clean_name}","{price_text}","{desc_clean}","{permalink}"\n')

    print(f"🎉 Success! Spreadsheet saved to: {os.path.abspath(CSV_PATH)}")

if __name__ == "__main__":
    export_vault_to_csv()
