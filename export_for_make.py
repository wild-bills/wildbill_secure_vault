import sqlite3
import os

DB_PATH = "database/store.db"
CSV_PATH = "make_vault_import.csv"

if not os.path.exists(DB_PATH):
    print(f"❌ Error: Database not found at {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT sku, name, theme, file_count FROM products WHERE file_count > 0")
rows = cursor.fetchall()
conn.close()

print(f"📦 Packaging {len(rows)} database rows for spreadsheet export...")

with open(CSV_PATH, 'w', encoding='utf-8') as f:
    f.write("Title,Price,Description,SKU\n")
    
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

        description_text = f"Premium {clean_name} asset pack. Category: {clean_theme}. Includes {file_qty} high-definition graphic assets with full commercial usage rights."
        
        desc_clean = description_text.replace('"', '""').replace(',', '')
        title_clean = clean_name.replace(',', '')

        f.write(f'"{title_clean}","{price_text}","{desc_clean}","{item["sku"]}"\n')

print(f"✅ Success! Spreadsheet saved to: {os.path.abspath(CSV_PATH)}")
