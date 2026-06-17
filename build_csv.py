import csv

# ----------------- CONFIGURATION -----------------
# 1. Replace with your exact Backblaze Bucket URL prefix
# Crucial: Do not include a trailing slash at the end
BACKBLAZE_BASE_URL = "https://backblazeb2.com"

# 2. Define the output CSV name (Must match your upload script)
OUTPUT_CSV_NAME = "products.csv"

# 3. Total number of products to generate rows for
TOTAL_PRODUCTS = 250

# 4. Set a default price for your items (e.g., 10.00 for $10.00)
# You can change these values manually in Excel/Google Sheets later
DEFAULT_PRICE = "10.00"
# -------------------------------------------------


def generate_gumroad_csv():
    print(f"📁 Generating CSV grid layout for {TOTAL_PRODUCTS} items...")

    headers = ["Title", "Description", "Price", "Zip_URL", "Preview_URL"]

    try:
        with open(
            OUTPUT_CSV_NAME, mode="w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.writer(file)

            # Write the column headers first
            writer.writerow(headers)

            for i in range(1, TOTAL_PRODUCTS + 1):
                # Create 3-digit padded numbers (001, 002, ... 250)
                padded_number = f"{i:03d}"

                # Generate titles and generic descriptions
                # Modify these placeholder text strings as needed
                title = f"Digital Asset Pack #{padded_number}"
                description = (
                    f"Premium creative asset bundle #{padded_number}. "
                    "Includes high-resolution assets and multi-format support."
                )

                # Construct your Backblaze URLs dynamically based on your naming convention
                zip_url = (
                    f"{BACKBLAZE_BASE_URL}/{padded_number}_product.zip"
                )
                preview_url = (
                    f"{BACKBLAZE_BASE_URL}/{padded_number}_preview.jpg"
                )

                # Assemble the row data
                row = [title, description, DEFAULT_PRICE, zip_url, preview_url]
                writer.writerow(row)

        print(f"🎉 Success! '{OUTPUT_CSV_NAME}' has been built successfully.")
        print("💡 Tip: You can now open this file in Excel or Google Sheets to:")
        print("   - Customize unique titles/prices for individual rows.")
        print("   - Check that the Backblaze links load properly.")

    except Exception as e:
        print(f"❌ Error building the CSV sheet: {e}")


if __name__ == "__main__":
    generate_gumroad_csv()
