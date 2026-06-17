import csv
import os

input_path = "/home/wildbill/gumroad_ready_assets/products.csv"
output_path = "/home/wildbill/gumroad_ready_assets/products_fixed.csv"

print("Starting a smart structural parse of the spreadsheet data...")

fixed_rows = []
headers = ["name", "price", "description", "file_name"]

# Sniff out whether your spreadsheet rows use standard commas or tabs
try:
    with open(input_path, 'r', encoding='utf-8') as f:
        sample = f.read(4096)
        dialect = csv.Sniffer().sniff(sample)
        dialect.skipinitialspace = True
except Exception:
    dialect = csv.excel # fallback to regular excel defaults if sniffing fails

with open(input_path, 'r', encoding='utf-8') as f:
    # Read the data dynamically regardless of commas embedded inside quoted sentences
    reader = csv.reader(f, dialect)
    
    for line_num, row in enumerate(reader, 1):
        if not row or len(row) < 2:
            continue
            
        # Ignore structural header keywords if they're present anywhere in the row
        if any(h in str(row[0]).lower() for h in headers):
            continue

        name = row[0].strip()
        raw_price = row[1].strip()
        
        # Pull description and filenames based on length
        description = row[2].strip() if len(row) > 2 else ""
        file_name = row[3].strip() if len(row) > 3 else ""

        # Intelligently convert decimal notation strings to integer cents
        try:
            if '.' in raw_price:
                price_cents = int(float(raw_price) * 100)
            else:
                price_cents = int(raw_price) * 100
        except ValueError:
            print(f"Line {line_num}: Skipping invalid row due to price calculation formatting issues: {raw_price}")
            continue

        fixed_rows.append([name, price_cents, description, file_name])

# Build clean output CSV file
with open(output_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    writer.writerows(fixed_rows)

print(f"Success! Corrected {len(fixed_rows)} structural dataset rows and exported to {output_path}")
