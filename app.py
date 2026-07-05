import os
import re
import sqlite3
from flask import Flask, render_template, redirect, request, jsonify, send_from_directory
import boto3
from botocore.config import Config

# --- PATH & APP CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')

app = Flask(__name__)

# --- SECURE BACKBLAZE CLOUD STORAGE CONFIGURATION ---
B2_KEY_ID = "005a9b63ec462530000000002"
B2_APPLICATION_KEY = "K005l0PuojaZ6sv1IiHJgJAoJkxiDp8"
B2_BUCKET_NAME = "wildbill-vault-zips"
REGION = "us-west-004"
B2_ENDPOINT_URL = "https://s3." + REGION + ".backblazeb2.com"


# Initialize secure storage client
s3_client = boto3.client(
    's3',
    aws_access_key_id=B2_KEY_ID,
    aws_secret_access_key=B2_APPLICATION_KEY,
    endpoint_url=B2_ENDPOINT_URL,
    config=Config(signature_version='s3v4')
)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_theme(product):
    theme = (product['theme'] or '').strip()
    if theme:
        return theme.title()

    name = (product['name'] or '').strip()
    if name:
        return name.split()[0].title()

    return 'Other'


def slugify_theme(theme_name):
    slug = re.sub(r'[^a-z0-9]+', '-', theme_name.lower()).strip('-')
    return slug or 'other'


def product_previews(product):
    previews = []
    for field in ('preview_1', 'preview_2', 'preview_3', 'preview_4'):
        value = product[field]
        if value:
            previews.append(value)

    if not previews and product['image_url']:
        previews.append(product['image_url'])

    return previews[:4]


def build_catalog_sections():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
    conn.close()

    grouped = {}
    for product in products:
        theme_name = normalize_theme(product)
        theme_slug = slugify_theme(theme_name)
        grouped.setdefault(theme_slug, {
            'slug': theme_slug,
            'theme': theme_name,
            'items': [],
        })
        grouped[theme_slug]['items'].append({
            'sku': product['sku'],
            'name': product['name'],
            'price': product['price'],
            'theme': theme_name,
            'previews': product_previews(product),
        })

    sections = sorted(grouped.values(), key=lambda section: (-len(section['items']), section['theme'].lower()))

    for section in sections:
        first_item = section['items'][0] if section['items'] else None
        section['count'] = len(section['items'])
        section['preview'] = first_item['previews'][0] if first_item and first_item['previews'] else ''

    return sections

@app.route('/paddle-webhook', methods=['POST'])
def paddle_webhook():
    payload_json = request.get_json()
    event_type = payload_json.get('event_type')
    
    if event_type == "transaction.completed":
        details = payload_json.get('data', {})
        customer_email = details.get('customer', {}).get('email')
        items = details.get('items', [])
        
        if items:
            # Safely grab the first purchased checkout plan ID
            completed_price_id = items[0].get('price_id')             
            # Query using your newly migrated column field name
            conn = get_db_connection()
            product = conn.execute('SELECT * FROM products WHERE paddle_price_id = ?', (completed_price_id,)).fetchone()
            
            if product:
                file_key = product['name'] + ".zip"
                download_link = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': B2_BUCKET_NAME, 'Key': file_key},
                    ExpiresIn=86400
                )
                print(f"💰 Order verified for {customer_email}. Generated bucket download: {download_link}")
            else:
                print(f"⚠️ Warning: Received Paddle price ID {completed_price_id} but found no matching database entry.")
            conn.close()
            
    return jsonify({"status": "success"}), 200


# --- FRONTEND ROUTE: HOMEPAGE GALLERY ---
# --- FIXED FRONTEND ROUTE: HOMEPAGE GALLERY ---
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', categories=build_catalog_sections())


@app.route('/category/<theme_slug>', methods=['GET'])
def category_view(theme_slug):
    sections = build_catalog_sections()
    category = next((section for section in sections if section['slug'] == theme_slug), None)
    if category is None:
        return "Category not found", 404

    return render_template('category.html', category=category)


@app.route('/category', methods=['GET'])
def category_query_view():
    return render_template('category.html')


@app.route('/category.html', methods=['GET'])
def category_page():
    return render_template('category.html')


@app.route('/previews/<path:filename>', methods=['GET'])
def serve_preview_image(filename):
    previews_dir = os.path.join(BASE_DIR, 'static', 'previews')
    return send_from_directory(previews_dir, filename)


@app.route('/products.json', methods=['GET'])
def products_json():
    return send_from_directory(BASE_DIR, 'products.json', mimetype='application/json')


# --- FRONTEND ROUTE: PRODUCT DETAIL VIEW ---
@app.route('/product/<sku>', methods=['GET'])
def product_detail(sku):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()
    if product is None:
        return "Product not found", 404
    return render_template('product.html', product=product)

# --- SECURE COMPLEMENTARY DOWNLOAD PATH ---
@app.route('/download/<sku>', methods=['GET', 'POST'])
def secure_download(sku):
    user_key = request.args.get('key')
    MASTER_SECRET = "VaultPaid680"
    
    if user_key != MASTER_SECRET:
        return "Access Denied: Valid Payment Verification Required", 403
        
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()
    
    if product is None:
        return "Invalid Product", 404
        
    file_key = product['name'] + ".zip"
    
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': B2_BUCKET_NAME, 'Key': file_key},
            ExpiresIn=900
        )
        return redirect(presigned_url)
    except Exception as e:
        return "Secure Delivery Error", 500

# --- STATIC FOOTER SUBPAGES ---
import smtplib
from email.mime.text import MIMEText

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        user_name = request.form.get('name')
        user_email = request.form.get('email')
        user_message = request.form.get('message')
        
        # Format the email body
        email_body = f"""New Website Support Ticket

From: {user_name}
Reply-To Email: {user_email}

Message:
{user_message}
"""
        
        msg = MIMEText(email_body)
        msg['Subject'] = f"[Vault Support] New Message from {user_name}"
        msg['From'] = 'wildbills1977@gmail.com'
        msg['To'] = 'wildbills1977@gmail.com'
        msg['Reply-To'] = user_email
        
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                # Fetches password securely from Render Environment configuration
                server.login('wildbills1977@gmail.com', os.environ.get('EMAIL_PASSWORD', ''))
                server.send_message(msg)
            return "Message sent successfully! We will get back to you shortly."
        except Exception as e:
            print(f"Email sending failure: {e}")
            return f"Mail Delivery Error: {str(e)}", 500

    return render_template('contact.html')

@app.route('/privacy.html', methods=['GET'])
def privacy(): return render_template('privacy.html')

@app.route('/terms.html', methods=['GET'])
def terms(): return render_template('terms.html')

@app.route('/refund.html', methods=['GET'])
def refund_page():
    return render_template('refund.html')

# --- DYNAMIC PRICING PAGE ROUTE ---
@app.route('/pricing.html', methods=['GET'])
def pricing_page():
    conn = get_db_connection()
    # Fetches all bundles from your product table to display as pricing tiers
    bundles = conn.execute('SELECT * FROM products ORDER BY sku ASC').fetchall()
    conn.close()
    return render_template('pricing.html', bundles=bundles)

@app.route('/static/js/<path:filename>')
def serve_paddle_js(filename):
    js_dir = os.path.join(app.root_path, 'static', 'js')
    return send_from_directory(js_dir, filename, mimetype='application/javascript')


if __name__ == '__main__':
    app.run(debug=True)
