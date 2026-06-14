import sqlite3
import os

DB_PATH = "database/store.db"

if not os.path.exists(DB_PATH):
    print("Database file not found!")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Tiny Packs (1-5 items) -> $4.99
cursor.execute("UPDATE products SET price = 4.99 WHERE file_count >= 1 AND file_count <= 5;")

# 2. Small Collections (6-20 items) -> $9.99
cursor.execute("UPDATE products SET price = 9.99 WHERE file_count >= 6 AND file_count <= 20;")

# 3. Medium Kits (21-50 items) -> $14.99
cursor.execute("UPDATE products SET price = 14.99 WHERE file_count >= 21 AND file_count <= 50;")

# 4. Large Bundles (51-99 items) -> $19.99
cursor.execute("UPDATE products SET price = 19.99 WHERE file_count >= 51 AND file_count <= 99;")

# 5. Mega Vaults (100+ items) -> $39.99
cursor.execute("UPDATE products SET price = 39.99 WHERE file_count >= 100;")
# Fallback price for any items that haven't been successfully scanned yet
cursor.execute("UPDATE products SET price = 14.99 WHERE file_count = 0;")

conn.commit()
print(f"Done! Updated prices for {conn.total_changes} products based on file counts.")
conn.close()
