import os
import re
import sqlite3
from urllib.parse import urlencode
from flask import Flask, render_template, redirect, request, jsonify, send_from_directory, url_for
import boto3
from botocore.config import Config


# --- PATH & APP CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')

app = Flask(__name__)

ALLOWED_CORS_ORIGINS = {
    'https://clipart.wildbillsproplans.com',
    'https://www.clipart.wildbillsproplans.com',
}


def cors_json_response(payload, status_code=200):
    response = jsonify(payload)
    response.status_code = status_code

    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_CORS_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin

    response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response


def allow_origin_for_get(response):
    origin = request.headers.get('Origin', '')
    if origin in ALLOWED_CORS_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    return response

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


def build_checkout_url(sku):
    """Build external checkout URL for the configured payment provider."""
    checkout_base = (os.environ.get('PAY_SERVICE_CHECKOUT_URL') or '').strip()
    if not checkout_base:
        return None

    if '{sku}' in checkout_base:
        return checkout_base.replace('{sku}', sku)

    separator = '&' if '?' in checkout_base else '?'
    return f"{checkout_base}{separator}{urlencode({'sku': sku})}"


def build_catalog_sections():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
    conn.close()

    grouped = {}
    for product in products:
        theme_name = normalize_theme(product)
        theme_slug = slugify_theme(theme_name)
        product_name = (product['name'] or '').strip()
        if not product_name or product_name.startswith('==='):
            product_name = product['sku'] or 'Untitled Bundle'

        checkout_sku = product['sku'] or ''
        grouped.setdefault(theme_slug, {
            'slug': theme_slug,
            'theme': theme_name,
            'items': [],
        })
        grouped[theme_slug]['items'].append({
            'sku': product['sku'],
            'name': product_name,
            'price': product['price'],
            'theme': theme_name,
            'previews': product_previews(product),
            'checkout_url': build_checkout_url(checkout_sku),
        })

    sections = sorted(grouped.values(), key=lambda section: (-len(section['items']), section['theme'].lower()))

    for section in sections:
        first_item = section['items'][0] if section['items'] else None
        section['count'] = len(section['items'])
        section['preview'] = first_item['previews'][0] if first_item and first_item['previews'] else ''

    return sections

@app.route('/paddle-webhook', methods=['POST', 'OPTIONS'])
def paddle_webhook():
    if request.method == 'OPTIONS':
        return cors_json_response({'status': 'preflight-ok'})

    payload_json = request.get_json(silent=True) or {}
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
            
    return cors_json_response({"status": "success"}, 200)


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
    return redirect(url_for('index'))


@app.route('/category.html', methods=['GET'])
def category_page():
    return redirect(url_for('index'))


@app.route('/previews/<path:filename>', methods=['GET'])
def serve_preview_image(filename):
    previews_dir = os.path.join(BASE_DIR, 'static', 'previews')
    return send_from_directory(previews_dir, filename)


@app.route('/products.json', methods=['GET'])
def products_json():
    return send_from_directory(BASE_DIR, 'products.json', mimetype='application/json')


@app.route('/catalog.json', methods=['GET'])
def catalog_json():
    sections = build_catalog_sections()
    payload = {
        'status': 'success',
        'categories': {
            section['theme']: section['items']
            for section in sections
        },
    }
    return allow_origin_for_get(jsonify(payload))


# --- FRONTEND ROUTE: PRODUCT DETAIL VIEW ---
@app.route('/product/<sku>', methods=['GET'])
def product_detail(sku):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()
    if product is None:
        return "Product not found", 404

    product_dict = dict(product)
    product_dict['checkout_url'] = build_checkout_url(product_dict.get('sku') or '')
    return render_template('product.html', product=product_dict)


@app.route('/checkout/<sku>', methods=['GET'])
def checkout_redirect(sku):
    conn = get_db_connection()
    product = conn.execute('SELECT sku FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()

    if product is None:
        return "Product not found", 404

    checkout_url = build_checkout_url(sku)
    if not checkout_url:
        return (
            "Checkout is not configured yet. Set PAY_SERVICE_CHECKOUT_URL "
            "(example: https://pay.example.com/checkout?sku={sku}) and try again.",
            503,
        )

    return redirect(checkout_url)

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
    bundles = [dict(row) for row in conn.execute('SELECT * FROM products ORDER BY sku ASC').fetchall()]
    conn.close()

    for bundle in bundles:
        bundle['checkout_url'] = build_checkout_url(bundle.get('sku') or '')

    return render_template('pricing.html', bundles=bundles)


if __name__ == '__main__':
    app.run(debug=True)
