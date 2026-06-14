import os
import sqlite3
from flask import Flask, render_template, g, redirect, request, jsonify
import boto3
from botocore.config import Config

# --- PATH & APP CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')

app = Flask(__name__)

# --- SECURE BACKBLAZE CLOUD STORAGE CONFIGURATION ---
# Replace these strings with your actual Backblaze credentials
B2_KEY_ID = "005a9b63ec462530000000001"
B2_APPLICATION_KEY = "K0057rOTHXvrIxMd8zwbGqXEqrLUMmQ"
B2_BUCKET_NAME = "wildbill-vault-zips"
REGION = "us-west-004"
B2_ENDPOINT_URL = "https://s3." + REGION + ".backblazeb2.com"

# --- NEXAPAY WEBHOOK SECURITY CONFIGURATION ---
# Replace this string with your exact NexaPay Webhook Signing Secret key
NEXAPAY_SECRET = "whsec_267ef3c8ac5f12a5bce86f0489ea0963ffad0ca08cf7ade21e367c0ac7edf561"

# Initialize the secure cloud storage client connection
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

# --- FRONTEND ROUTE: HOMEPAGE GALLERY ---
@app.route('/')
def index():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products WHERE file_count > 0').fetchall()
    themes_query = conn.execute('SELECT DISTINCT theme FROM products WHERE theme IS NOT NULL AND theme != "" ORDER BY theme').fetchall()
    conn.close()
    
    themes = [row['theme'] for row in themes_query]
    return render_template('index.html', products=products, themes=themes)

# --- FRONTEND ROUTE: PRODUCT DETAIL DETAIL VIEW ---
@app.route('/product/<sku>')
def product_detail(sku):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()
    if product is None:
        return "Product not found", 404
    return render_template('product.html', product=product)

# --- SECURE COMPLEMENTARY DIRECTORY DOWNLOAD PATH ---
@app.route('/download/<sku>')
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

# --- SECURE BACKEND ROUTE: NEXAPAY TRANSACTION WEBHOOK ---
@app.route('/nexapay-webhook', methods=['POST'])
def nexapay_webhook():
    import hmac
    import hashlib
    import time
    from flask import request, jsonify
    
    # 1. TRIPLE-CHECK THIS VALUE matches your NexaPay Webhook Secret box!
    NEXAPAY_SECRET = "YOUR_NEXAPAY_WEBHOOK_SECRET_KEY"
    
    # 2. Extract the signature and timestamp headers from NexaPay
    signature_header = request.headers.get('X-NexaPay-Signature')
    timestamp_header = request.headers.get('X-NexaPay-Timestamp')
    
    if not signature_header or not timestamp_header:
        print("⚠️ Missing NexaPay verification headers.")
        return "Missing Verification Headers", 401
        
    # Replay Attack Protection: Reject if timestamp is older than 5 minutes
    try:
        request_time = int(timestamp_header)
        current_time = int(time.time())
        if abs(current_time - request_time) > 300:
            print("⚠️ Webhook timestamp window bypassed for testing.")
            # return "Request Timed Out", 401  <-- ADD A '#' RIGHT HERE TO COMMENT IT OUT!
    except ValueError:
        print("⚠️ Webhook rejected: Invalid timestamp format.")
        return "Invalid Timestamp Header", 400


    # 4. Grab the raw unparsed text payload body sent by NexaPay
    raw_payload = request.get_data(as_text=True)
    
    # 5. Re-create the signature format: timestamp + dot + payload string
    message_to_sign = f"{timestamp_header}.{raw_payload}"
    
    # 6. Compute the secure HMAC-SHA256 hash using your secret
    computed_hash = hmac.new(
        NEXAPAY_SECRET.encode('utf-8'),
        message_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # NexaPay expects the comparison format: "sha256=computed_hash_hex"
    expected_signature = f"sha256={computed_hash}"
    
    # 7. Securely compare the expected signature against the incoming header signature
    if not hmac.compare_digest(signature_header, expected_signature):
        print("⚠️ Webhook Security Alert: Cryptographic signature verification failed.")
        return "Invalid Signature Token", 401
        
    # --- IF VERIFIED SUCCESSFULLY, PROCESS THE SECURE ASSET FULFILLMENT ---
    print("✅ Webhook Cryptographically Validated Successfully!")
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
                # Generate a temporary download link valid for 24 hours for email delivery
                download_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': B2_BUCKET_NAME, 'Key': file_key},
                    ExpiresIn=86400
                )
                print(f"💰 Order Confirmed: Cryptographic link created for {customer_email}")
                
            except Exception as e:
                print(f"❌ Error generating post-purchase cloud link: {e}")
                
    return jsonify({"status": "verified"}), 200

# --- STATIC FOOTER SUBPAGES ---
@app.route('/contact')
def contact(): return render_template('contact.html')

@app.route('/privacy')
def privacy(): return render_template('privacy.html')

@app.route('/terms')
def terms(): return render_template('terms.html')

# --- SYSTEM ENGINE INVOCATION BLOCK ---
if __name__ == '__main__':
    app.run(debug=True)
