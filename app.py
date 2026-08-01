import os
import re
import csv
import json
import hmac
import secrets
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import Flask, render_template, redirect, request, jsonify, send_from_directory, url_for
import boto3
from botocore.config import Config


# --- PATH & APP CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')
THEME_IMPORT_CSV = os.path.join(BASE_DIR, 'make_vault_import.csv')

app = Flask(__name__)

ALLOWED_CORS_ORIGINS = {
    'https://clipart.wildbillsproplans.com',
    'https://www.clipart.wildbillsproplans.com',
}

DOWNLOAD_TOKEN_TTL_HOURS = int(os.environ.get('DOWNLOAD_TOKEN_TTL_HOURS', '48'))
DOWNLOAD_URL_EXPIRES_SECONDS = int(os.environ.get('DOWNLOAD_URL_EXPIRES_SECONDS', '900'))
PURCHASE_MATCH_WINDOW_MINUTES = int(os.environ.get('PURCHASE_MATCH_WINDOW_MINUTES', '180'))
PAY_PROVIDER = (os.environ.get('PAY_PROVIDER') or '').strip().lower()
STRIPE_CURRENCY = (os.environ.get('STRIPE_CURRENCY') or 'usd').strip().lower()


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


def utcnow():
    return datetime.now(timezone.utc)


def iso_utc(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_iso_utc(value):
    text = str(value or '').strip()
    if not text:
        return None
    try:
        if text.endswith('Z'):
            return datetime.fromisoformat(text.replace('Z', '+00:00'))
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def ensure_checkout_tables():
    conn = get_db_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS completed_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            provider_transaction_id TEXT UNIQUE NOT NULL,
            customer_email TEXT,
            sku TEXT,
            price_id TEXT,
            product_id TEXT,
            raw_payload TEXT,
            created_at TEXT NOT NULL
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS download_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            sku TEXT NOT NULL,
            customer_email TEXT,
            purchase_id INTEGER,
            expires_at TEXT NOT NULL,
            used_count INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (purchase_id) REFERENCES completed_purchases(id)
        )
        '''
    )
    conn.commit()
    conn.close()


ensure_checkout_tables()


def verify_stripe_signature(payload_bytes, sig_header, webhook_secret, tolerance=300):
    if not sig_header or not webhook_secret:
        return False

    timestamp = None
    signatures = []
    for part in sig_header.split(','):
        key, _, value = part.strip().partition('=')
        if key == 't':
            timestamp = value
        elif key == 'v1':
            signatures.append(value)

    if not timestamp or not signatures:
        return False

    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False

    if abs(int(utcnow().timestamp()) - ts) > tolerance:
        return False

    signed_payload = (timestamp + '.').encode('utf-8') + payload_bytes
    expected = hmac.new(webhook_secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


def stripe_post_form(path, form_data):
    secret = (os.environ.get('STRIPE_SECRET_KEY') or '').strip()
    if not secret:
        raise ValueError('Missing STRIPE_SECRET_KEY')

    body = urlencode(form_data).encode('utf-8')
    req = Request(
        'https://api.stripe.com' + path,
        data=body,
        method='POST',
        headers={
            'Authorization': f'Bearer {secret}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw)
    except HTTPError as exc:
        error_body = ''
        try:
            error_body = exc.read().decode('utf-8')
        except Exception:
            error_body = str(exc)
        raise RuntimeError(f'Stripe HTTP error {exc.code}: {error_body}')
    except URLError as exc:
        raise RuntimeError(f'Stripe request failed: {exc}')


def create_stripe_checkout_session(
    sku,
    price_id,
    product_id,
    success_url,
    cancel_url,
    mode='payment',
    unit_amount_cents=None,
    product_name='',
):
    clean_sku = str(sku or '').strip()
    clean_price_id = str(price_id or '').strip()
    clean_product_id = normalize_product_id(product_id)
    clean_mode = str(mode or 'payment').strip() or 'payment'
    clean_product_name = str(product_name or clean_sku or 'Wild Bill Bundle').strip()

    payload = [
        ('mode', clean_mode),
        ('success_url', success_url),
        ('cancel_url', cancel_url),
        ('line_items[0][quantity]', '1'),
        ('metadata[sku]', clean_sku),
        ('metadata[product_id]', clean_product_id),
        ('client_reference_id', clean_sku),
    ]

    if clean_price_id:
        payload.extend([
            ('line_items[0][price]', clean_price_id),
            ('metadata[price_id]', clean_price_id),
        ])
    else:
        if unit_amount_cents is None:
            raise ValueError('Missing Stripe price_id and unable to derive dynamic unit amount')
        payload.extend([
            ('line_items[0][price_data][currency]', STRIPE_CURRENCY),
            ('line_items[0][price_data][unit_amount]', str(int(unit_amount_cents))),
            ('line_items[0][price_data][product_data][name]', clean_product_name),
            ('line_items[0][price_data][product_data][metadata][sku]', clean_sku),
            ('line_items[0][price_data][product_data][metadata][product_id]', clean_product_id),
            ('metadata[price_id]', ''),
        ])

    return stripe_post_form('/v1/checkout/sessions', payload)


def load_bundle_theme_lookup():
    lookup = {}
    max_bundle_num = 0

    if not os.path.exists(THEME_IMPORT_CSV):
        return lookup, max_bundle_num

    with open(THEME_IMPORT_CSV, mode='r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_sku = str(row.get('SKU') or '').strip().lower()
            if not raw_sku:
                continue

            # Example import SKU: bundle_24_crimson_cyberpunk_fetish
            match = re.match(r'bundle_(\d+)_(.+)$', raw_sku)
            if not match:
                continue

            bundle_num = int(match.group(1))
            raw_theme = match.group(2).replace('_', ' ').strip()
            if not raw_theme:
                continue

            lookup[bundle_num] = raw_theme
            if bundle_num > max_bundle_num:
                max_bundle_num = bundle_num

    return lookup, max_bundle_num


BUNDLE_THEME_LOOKUP, MAX_BUNDLE_THEME_NUMBER = load_bundle_theme_lookup()


def infer_theme_from_sku(sku_value):
    raw_sku = str(sku_value or '').strip().upper()
    match = re.search(r'(\d+)$', raw_sku)
    if not match:
        return ''

    sku_num = int(match.group(1))
    if sku_num in BUNDLE_THEME_LOOKUP:
        return BUNDLE_THEME_LOOKUP[sku_num]

    if MAX_BUNDLE_THEME_NUMBER > 0:
        wrapped_num = ((sku_num - 1) % MAX_BUNDLE_THEME_NUMBER) + 1
        return BUNDLE_THEME_LOOKUP.get(wrapped_num, '')

    return ''


def normalize_theme(product):
    theme = (product['theme'] or '').strip()
    if theme and theme.lower() != 'gothic':
        return theme.title()

    inferred = infer_theme_from_sku(product['sku'])
    if inferred:
        return inferred.title()

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


def normalize_product_id(value):
    product_id = str(value or '').strip()
    if product_id.lower().endswith('.zip'):
        product_id = product_id[:-4]
    return product_id


def resolve_product_from_identifiers(conn, sku='', price_id='', product_id=''):
    clean_sku = str(sku or '').strip()
    clean_price_id = str(price_id or '').strip()
    clean_product_id = normalize_product_id(product_id)

    if clean_sku:
        row = conn.execute('SELECT * FROM products WHERE sku = ?', (clean_sku,)).fetchone()
        if row:
            return row

    if clean_price_id:
        row = conn.execute('SELECT * FROM products WHERE paddle_price_id = ?', (clean_price_id,)).fetchone()
        if row:
            return row

    if clean_product_id:
        row = conn.execute(
            """
            SELECT *
            FROM products
            WHERE lower(replace(zip_filename, '.zip', '')) = lower(?)
            """,
            (clean_product_id,),
        ).fetchone()
        if row:
            return row

    return None


def zip_key_for_product(product):
    zip_filename = str(product['zip_filename'] or '').strip()
    if zip_filename:
        return zip_filename
    return str(product['name'] or '').strip() + '.zip'


def generate_b2_download_url(product):
    file_key = zip_key_for_product(product)
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': B2_BUCKET_NAME, 'Key': file_key},
        ExpiresIn=DOWNLOAD_URL_EXPIRES_SECONDS,
    )


def create_download_token(conn, sku, customer_email='', purchase_id=None):
    token = secrets.token_urlsafe(24)
    now = utcnow()
    expires_at = iso_utc(now + timedelta(hours=DOWNLOAD_TOKEN_TTL_HOURS))
    conn.execute(
        '''
        INSERT INTO download_tokens (token, sku, customer_email, purchase_id, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            token,
            str(sku or '').strip(),
            str(customer_email or '').strip(),
            purchase_id,
            expires_at,
            iso_utc(now),
        ),
    )
    return token


def extract_completed_purchase(payload_json):
    details = payload_json.get('data', {})
    items = details.get('items', [])
    first_item = items[0] if items else {}
    custom_data = details.get('custom_data') or first_item.get('custom_data') or {}

    return {
        'provider': 'paddle',
        'provider_transaction_id': str(details.get('id') or payload_json.get('id') or '').strip(),
        'customer_email': str(details.get('customer', {}).get('email') or '').strip(),
        'price_id': str(first_item.get('price_id') or '').strip(),
        'sku': str(custom_data.get('sku') or details.get('sku') or '').strip(),
        'product_id': normalize_product_id(custom_data.get('product_id') or ''),
    }


def upsert_completed_purchase(payload_json):
    purchase = extract_completed_purchase(payload_json)
    txn_id = purchase['provider_transaction_id']
    if not txn_id:
        return None

    conn = get_db_connection()
    product = resolve_product_from_identifiers(
        conn,
        sku=purchase['sku'],
        price_id=purchase['price_id'],
        product_id=purchase['product_id'],
    )
    resolved_sku = str(product['sku']) if product else str(purchase['sku'] or '').strip()

    now_iso = iso_utc(utcnow())
    conn.execute(
        '''
        INSERT INTO completed_purchases (
            provider,
            provider_transaction_id,
            customer_email,
            sku,
            price_id,
            product_id,
            raw_payload,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_transaction_id) DO UPDATE SET
            customer_email=excluded.customer_email,
            sku=excluded.sku,
            price_id=excluded.price_id,
            product_id=excluded.product_id,
            raw_payload=excluded.raw_payload,
            created_at=excluded.created_at
        ''',
        (
            purchase['provider'],
            txn_id,
            purchase['customer_email'],
            resolved_sku,
            purchase['price_id'],
            purchase['product_id'],
            json.dumps(payload_json),
            now_iso,
        ),
    )
    conn.commit()

    row = conn.execute('SELECT * FROM completed_purchases WHERE provider_transaction_id = ?', (txn_id,)).fetchone()
    conn.close()
    return row


def upsert_completed_purchase_record(provider, provider_transaction_id, customer_email='', sku='', price_id='', product_id='', raw_payload=None):
    txn_id = str(provider_transaction_id or '').strip()
    if not txn_id:
        return None

    conn = get_db_connection()
    product = resolve_product_from_identifiers(
        conn,
        sku=sku,
        price_id=price_id,
        product_id=product_id,
    )
    resolved_sku = str(product['sku']) if product else str(sku or '').strip()

    now_iso = iso_utc(utcnow())
    conn.execute(
        '''
        INSERT INTO completed_purchases (
            provider,
            provider_transaction_id,
            customer_email,
            sku,
            price_id,
            product_id,
            raw_payload,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_transaction_id) DO UPDATE SET
            customer_email=excluded.customer_email,
            sku=excluded.sku,
            price_id=excluded.price_id,
            product_id=excluded.product_id,
            raw_payload=excluded.raw_payload,
            created_at=excluded.created_at
        ''',
        (
            str(provider or 'unknown').strip(),
            txn_id,
            str(customer_email or '').strip(),
            resolved_sku,
            str(price_id or '').strip(),
            normalize_product_id(product_id),
            json.dumps(raw_payload or {}),
            now_iso,
        ),
    )
    conn.commit()
    row = conn.execute('SELECT * FROM completed_purchases WHERE provider_transaction_id = ?', (txn_id,)).fetchone()
    conn.close()
    return row


def create_download_token_for_purchase(sku, customer_email, purchase_id):
    conn = get_db_connection()
    token = create_download_token(conn, sku=sku, customer_email=customer_email, purchase_id=purchase_id)
    conn.commit()
    conn.close()
    return token


def claim_latest_purchase_by_email(sku, customer_email):
    clean_sku = str(sku or '').strip()
    clean_email = str(customer_email or '').strip().lower()
    if not clean_sku or not clean_email:
        return None

    cutoff = iso_utc(utcnow() - timedelta(minutes=PURCHASE_MATCH_WINDOW_MINUTES))

    conn = get_db_connection()
    purchase = conn.execute(
        '''
        SELECT *
        FROM completed_purchases
        WHERE sku = ?
          AND lower(customer_email) = ?
          AND created_at >= ?
        ORDER BY id DESC
        LIMIT 1
        ''',
        (clean_sku, clean_email, cutoff),
    ).fetchone()

    if not purchase:
        conn.close()
        return None

    token = create_download_token(
        conn,
        sku=clean_sku,
        customer_email=str(purchase['customer_email'] or '').strip(),
        purchase_id=purchase['id'],
    )
    conn.commit()
    conn.close()
    return token


def render_checkout_success_page(sku, message='', token=''):
    safe_sku = escape(str(sku or '').strip())
    safe_message = escape(str(message or '').strip())
    download_url = url_for('download_with_token', token=token, _external=True) if token else ''

    if token:
        return f"""
        <html><body style=\"font-family:Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;\">
        <h1>Payment Confirmed</h1>
        <p>Your download is ready for SKU <strong>{safe_sku}</strong>.</p>
        <p><a href=\"{download_url}\">Download Your ZIP Now</a></p>
        <p style=\"color:#555;\">This secure link expires automatically.</p>
        </body></html>
        """

    return f"""
    <html><body style=\"font-family:Arial,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;\">
    <h1>Complete Your Download</h1>
    <p>{safe_message or 'We found your checkout return. Enter the same email used at payment to fetch your secure download link.'}</p>
    <form method=\"post\" action=\"{url_for('checkout_success')}\" style=\"margin-top:16px;\">
        <input type=\"hidden\" name=\"sku\" value=\"{safe_sku}\" />
        <label>Email used at checkout</label><br />
        <input type=\"email\" name=\"email\" required style=\"width:100%;max-width:420px;padding:10px;margin-top:6px;\" />
        <div style=\"margin-top:14px;\">
            <button type=\"submit\" style=\"padding:10px 14px;\">Get Secure Download Link</button>
        </div>
    </form>
    </body></html>
    """


def build_checkout_url(sku, metadata_product_id='', price_id='', success_url='', cancel_url='', mode='payment'):
    """Build external checkout URL for the configured payment provider."""
    checkout_base = (os.environ.get('PAY_SERVICE_CHECKOUT_URL') or '').strip()
    if not checkout_base:
        return None

    passthrough = {
        'sku': str(sku or '').strip(),
        'product_id': (metadata_product_id or '').strip(),
        'price_id': (price_id or '').strip(),
        'success_url': (success_url or '').strip(),
        'cancel_url': (cancel_url or '').strip(),
        'mode': (mode or '').strip(),
    }
    passthrough = {k: v for k, v in passthrough.items() if v}

    if '{sku}' in checkout_base:
        checkout_url = checkout_base.replace('{sku}', sku)
    else:
        separator = '&' if '?' in checkout_base else '?'
        checkout_url = f"{checkout_base}{separator}{urlencode({'sku': sku})}"

    if not passthrough:
        return checkout_url

    separator = '&' if '?' in checkout_url else '?'
    return f"{checkout_url}{separator}{urlencode(passthrough)}"


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
        zip_filename = (product['zip_filename'] or '').strip()
        metadata_product_id = zip_filename
        if metadata_product_id.lower().endswith('.zip'):
            metadata_product_id = metadata_product_id[:-4]

        grouped.setdefault(theme_slug, {
            'slug': theme_slug,
            'theme': theme_name,
            'items': [],
        })
        grouped[theme_slug]['items'].append({
            'sku': product['sku'],
            'name': product_name,
            'price': product['price'],
            'price_id': product['paddle_price_id'],
            'theme': theme_name,
            'file_count': product['file_count'],
            'zip_filename': zip_filename,
            'product_id': metadata_product_id,
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
        purchase = upsert_completed_purchase(payload_json)
        if purchase is None:
            print("⚠️ Warning: transaction.completed event missing transaction id.")
        else:
            print(
                "💰 Order verified:",
                f"txn={purchase['provider_transaction_id']}",
                f"email={purchase['customer_email']}",
                f"sku={purchase['sku']}",
            )
            
    return cors_json_response({"status": "success"}, 200)


@app.route('/stripe-webhook', methods=['POST', 'OPTIONS'])
def stripe_webhook():
    if request.method == 'OPTIONS':
        return cors_json_response({'status': 'preflight-ok'})

    webhook_secret = (os.environ.get('STRIPE_WEBHOOK_SECRET') or '').strip()
    payload_bytes = request.get_data() or b''
    signature = request.headers.get('Stripe-Signature', '')

    if webhook_secret and not verify_stripe_signature(payload_bytes, signature, webhook_secret):
        return cors_json_response({'status': 'error', 'message': 'invalid signature'}, 400)

    try:
        event = json.loads(payload_bytes.decode('utf-8'))
    except Exception:
        return cors_json_response({'status': 'error', 'message': 'invalid payload'}, 400)

    event_type = str(event.get('type') or '').strip()
    obj = (event.get('data') or {}).get('object') or {}

    if event_type == 'checkout.session.completed':
        payment_status = str(obj.get('payment_status') or '').strip()
        if payment_status in ('paid', 'no_payment_required'):
            metadata = obj.get('metadata') or {}
            purchase = upsert_completed_purchase_record(
                provider='stripe',
                provider_transaction_id=str(obj.get('id') or ''),
                customer_email=str((obj.get('customer_details') or {}).get('email') or obj.get('customer_email') or ''),
                sku=str(metadata.get('sku') or obj.get('client_reference_id') or ''),
                price_id=str(metadata.get('price_id') or ''),
                product_id=str(metadata.get('product_id') or ''),
                raw_payload=event,
            )
            if purchase is None:
                print('⚠️ Warning: Stripe checkout.session.completed missing session id.')
            else:
                print(
                    '💰 Stripe order verified:',
                    f"txn={purchase['provider_transaction_id']}",
                    f"email={purchase['customer_email']}",
                    f"sku={purchase['sku']}",
                )

    return cors_json_response({'status': 'success'}, 200)


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
    previews = product_previews(product)
    product_dict['checkout_url'] = build_checkout_url(product_dict.get('sku') or '')
    return render_template('product.html', product=product_dict, previews=previews)


@app.route('/checkout/<sku>', methods=['GET'])
def checkout_redirect(sku):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()

    if product is None:
        return "Product not found", 404

    query_product_id = request.args.get('product_id', '').strip()
    query_price_id = request.args.get('price_id', '').strip()
    query_success_url = request.args.get('success_url', '').strip()
    query_cancel_url = request.args.get('cancel_url', '').strip()
    mode = request.args.get('mode', 'payment').strip() or 'payment'

    fallback_product_id = normalize_product_id(query_product_id or product['zip_filename'] or sku)
    fallback_price_id = query_price_id or str(product['paddle_price_id'] or '').strip()
    if fallback_price_id == 'YOUR_STRIPE_PRICE_ID':
        fallback_price_id = ''

    product_price_raw = product['price']
    try:
        product_price_cents = int(round(float(product_price_raw) * 100))
    except (TypeError, ValueError):
        product_price_cents = None

    success_url = query_success_url or url_for('checkout_success', sku=sku, _external=True)
    cancel_url = query_cancel_url or url_for('checkout_cancel', sku=sku, _external=True)

    if PAY_PROVIDER == 'stripe' and (os.environ.get('STRIPE_SECRET_KEY') or '').strip():
        try:
            stripe_session = create_stripe_checkout_session(
                sku=sku,
                price_id=fallback_price_id,
                product_id=fallback_product_id,
                success_url=success_url,
                cancel_url=cancel_url,
                mode=mode,
                unit_amount_cents=product_price_cents,
                product_name=str(product['name'] or sku),
            )
        except ValueError as exc:
            return str(exc), 400
        except Exception as exc:
            return f"Stripe checkout session error: {exc}", 502

        stripe_url = str(stripe_session.get('url') or '').strip()
        if not stripe_url:
            return "Stripe checkout did not return a redirect URL.", 502

        return redirect(stripe_url)

    checkout_url = build_checkout_url(
        sku,
        metadata_product_id=fallback_product_id,
        price_id=fallback_price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        mode=mode,
    )
    if not checkout_url:
        return (
            "Checkout is not configured yet. Set PAY_PROVIDER/Stripe values or PAY_SERVICE_CHECKOUT_URL and try again.",
            503,
        )

    return redirect(checkout_url)


@app.route('/checkout/success', methods=['GET', 'POST'])
def checkout_success():
    sku = (request.values.get('sku') or '').strip()
    email = (request.values.get('email') or '').strip()

    if not sku:
        return "Missing SKU on checkout success callback.", 400

    if request.method == 'POST' and email:
        token = claim_latest_purchase_by_email(sku=sku, customer_email=email)
        if token:
            return render_checkout_success_page(sku=sku, token=token)
        return render_checkout_success_page(
            sku=sku,
            message=(
                "No completed payment matched this SKU and email yet. "
                "Please wait 30-60 seconds and try again."
            ),
        )

    if email:
        token = claim_latest_purchase_by_email(sku=sku, customer_email=email)
        if token:
            return render_checkout_success_page(sku=sku, token=token)

    return render_checkout_success_page(
        sku=sku,
        message=(
            "Payment return received. Enter the same email used at checkout "
            "to fetch your secure Backblaze download link."
        ),
    )


@app.route('/checkout/cancel', methods=['GET'])
def checkout_cancel():
    sku = (request.args.get('sku') or '').strip()
    if sku:
        return redirect(f"/product.html?sku={sku}")
    return redirect('/')


@app.route('/download/token/<token>', methods=['GET'])
def download_with_token(token):
    clean_token = str(token or '').strip()
    if not clean_token:
        return "Invalid download token.", 400

    conn = get_db_connection()
    token_row = conn.execute('SELECT * FROM download_tokens WHERE token = ?', (clean_token,)).fetchone()
    if token_row is None:
        conn.close()
        return "Download token not found.", 404

    expires_at = parse_iso_utc(token_row['expires_at'])
    if expires_at is None or expires_at < utcnow():
        conn.close()
        return "Download token expired.", 410

    product = conn.execute('SELECT * FROM products WHERE sku = ?', (token_row['sku'],)).fetchone()
    if product is None:
        conn.close()
        return "Product for this download token was not found.", 404

    conn.execute(
        'UPDATE download_tokens SET used_count = used_count + 1, last_used_at = ? WHERE id = ?',
        (iso_utc(utcnow()), token_row['id']),
    )
    conn.commit()
    conn.close()

    try:
        presigned_url = generate_b2_download_url(product)
    except Exception:
        return "Secure Delivery Error", 500

    return redirect(presigned_url)

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
        
    file_key = zip_key_for_product(product)
    
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': B2_BUCKET_NAME, 'Key': file_key},
            ExpiresIn=DOWNLOAD_URL_EXPIRES_SECONDS
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
