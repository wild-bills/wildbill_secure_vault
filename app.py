import os
import sqlite3
from flask import Flask, render_template, g, redirect, request, jsonify
import boto3
from botocore.config import Config
import hmac
import hashlib
import time

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
    conn = get_db_connection()
    # FIX: Selects all records directly to ignore the unpopulated file_count cells
    products = conn.execute('SELECT * FROM products ORDER BY id DESC').fetchall()
    themes_query = conn.execute('SELECT DISTINCT theme FROM products WHERE theme IS NOT NULL AND theme != "" ORDER BY theme').fetchall()
    conn.close()
    
    themes = [row['theme'] for row in themes_query]
    return render_template('index.html', products=products, themes=themes)


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

    try:
        request_time = int(timestamp_header)
        current_time = int(time.time())
        if abs(current_time - request_time) > 300:
            print("⚠️ Webhook timestamp window bypassed for testing.")
    except ValueError:
        return "Invalid Timestamp Header", 400

    raw_payload = request.get_data(as_text=True)
    message_to_sign = f"{timestamp_header}.{raw_payload}"
    
    computed_hash = hmac.new(
        NEXAPAY_SECRET.encode('utf-8'),
        message_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    expected_signature = f"sha256={computed_hash}"
    
    if not hmac.compare_digest(signature_header, expected_signature):
        print("⚠️ Webhook Security Alert: Cryptographic signature verification failed.")
        return "Invalid Signature Token", 401
        
    data = request.get_json()
    
    if data and data.get('status') == 'success':
        customer_email = data.get('customer_email')
        sku = data.get('sku')
        
        conn = get_db_connection()
        product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
        conn.close()
        
        if product:
            file_key = product['name'] + ".zip"
            try:
                download_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': B2_BUCKET_NAME, 'Key': file_key},
                    ExpiresIn=86400
                )
                print(f"💰 Order Confirmed: Link created for {customer_email}")
            except Exception as e:
                print(f"❌ Error: {e}")
                
    return jsonify({"status": "verified"}), 200

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

@app.route('/pricing.html', methods=['GET'])
def pricing(): return render_template('pricing.html')

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
from flask import send_from_directory
import os

@app.route('/static/js/<path:filename>')
def serve_paddle_js(filename):
    js_dir = os.path.join(app.root_path, 'static', 'js')
    return send_from_directory(js_dir, filename, mimetype='application/javascript')


if __name__ == '__main__':
    app.run(debug=True)
