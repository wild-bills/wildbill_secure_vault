import csv
import time
import requests

# ----------------- CONFIGURATION -----------------
# Paste your token from Gumroad Advanced Settings here
GUMROAD_TOKEN = "7UAA_2Bu6PLFQslkhCAHCrwmdh16XHh3HE17HNdLoTg"

# The CSV file containing your product information
CSV_FILE_NAME = "products.csv"

BASE_URL = "https://api.gumroad.com/v2"
# -------------------------------------------------


def upload_catalog():
    print("🚀 Initializing bulk upload sequence to Gumroad...")

    try:
        with open(CSV_FILE_NAME, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            # Safety check for correct headers
            required_headers = [
                "Title",
                "Description",
                "Price",
                "Zip_URL",
                "Preview_URL",
            ]
            if not all(h in reader.fieldnames for h in required_headers):
                print(
                    f"❌ Error: Your CSV columns must match exactly: {required_headers}"
                )
                return

            success_count = 0

            for index, row in enumerate(reader, start=1):
                title = row["Title"]
                description = row["Description"]
                # Gumroad API prices are integers in cents (e.g., $10.00 is 1000)
                price_cents = int(float(row["Price"]) * 100)
                zip_url = row["Zip_URL"]
                preview_url = row["Preview_URL"]

                print(
                    f"\n📦 Processing [{index}]: Processing '{title}'..."
                )

                # STEP 1: Create the baseline digital product draft listing
                create_payload = {
                    "access_token": GUMROAD_TOKEN,
                    "name": title,
                    "description": description,
                    "price": price_cents,
                    "file_url": zip_url,  # Clones ZIP straight from Backblaze
                }

                prod_response = requests.post(
                    f"{BASE_URL}/products", data=create_payload
                )

                if prod_response.status_code != 200:
                    print(
                        f"❌ Failed to create '{title}'. Status: {prod_response.status_code}"
                    )
                    print(f"Details: {prod_response.text}")
                    continue

                # Extract product data and the unique product ID
                product_data = prod_response.json().get("product", {})
                product_id = product_data.get("id")

                if not product_id:
                    print(
                        f"❌ Could not retrieve unique product ID for '{title}'."
                    )
                    continue

                # STEP 2: Attach the Backblaze preview thumbnail via the specific cover endpoint
                # Gumroad downloads the remote link server-side instantly
                thumb_payload = {
                    "access_token": GUMROAD_TOKEN,
                    "url": preview_url,
                }

                thumb_response = requests.post(
                    f"{BASE_URL}/products/{product_id}/thumbnail",
                    data=thumb_payload,
                )

                if thumb_response.status_code in [200, 201]:
                    print(
                        f"✅ Success! '{title}' created with preview attached."
                    )
                    success_count += 1
                else:
                    print(
                        f"⚠️ Base listing created for '{title}', but thumbnail upload failed."
                    )
                    print(f"Details: {thumb_response.text}")

                # STEP 3: API rate limiting defense cushion
                # Keeps the loops steady so Gumroad doesn't block the network request
                time.sleep(2)

            print(
                f"\n🎉 Sequence complete. Successfully uploaded {success_count} listings out of {index} items as Drafts."
            )

    except FileNotFoundError:
        print(
            f"❌ Script Error: Could not find the file '{CSV_FILE_NAME}' in this directory."
        )


if __name__ == "__main__":
    upload_catalog()
