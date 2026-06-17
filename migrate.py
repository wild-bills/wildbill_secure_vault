import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. Add the new Paddle Price ID column to the products table
        cursor.execute("ALTER TABLE products ADD COLUMN paddle_price_id TEXT;")
        conn.commit()
        print("✅ Database column 'paddle_price_id' added successfully!")
        
        # 2. Let's look up your 10 existing bundle items from your CSV data
        cursor.execute("SELECT sku, name FROM products;")
        rows = cursor.fetchall()
        print(f"\nFound {len(rows)} products in database. Ready for Paddle mapping.")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️ Column 'paddle_price_id' already exists in the schema.")
        else:
            print(f"❌ Database error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    update_schema()
