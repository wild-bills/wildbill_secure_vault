import csv
import subprocess
import os

# Change this to match your actual CSV filename
csv_filename = 'products.csv' 

if not os.path.exists(csv_filename):
    print(f"Error: Could not find {csv_filename} in the current directory.")
    exit(1)

with open(csv_filename, mode='r', encoding='utf-8-sig') as file:
    # DictReader automatically maps rows based on the headers in row 1
    reader = csv.DictReader(file)
    
    # Strip whitespace from headers just in case
    reader.fieldnames = [name.strip() for name in reader.fieldnames] if reader.fieldnames else []
    
    print(f"Detected columns: {reader.fieldnames}")
    
    for row_num, row in enumerate(reader, start=2):
        name = row.get('name', '').strip()
        price = row.get('price', '').strip()
        file_path = row.get('file_path', '').strip()
        cover_path = row.get('cover_path', '').strip()
        
        # Skip empty rows
        if not name and not file_path:
            continue
            
        print(f"\n--- Processing Row {row_num}: {name[:30]}... ---")
        
        # Build the command dynamically
        command = ["gumroad", "products", "create", "--name", name, "--no-input"]
        
        if price:
            command.extend(["--price", price])
        if file_path:
            command.extend(["--file", file_path])
        if cover_path:
            command.extend(["--cover-image", cover_path])
            
        # Execute command safely without string splitting bugs
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Success!")
        else:
            print(f"❌ Failed!")
            print(f"Error Output:\n{result.stderr.strip()}")
