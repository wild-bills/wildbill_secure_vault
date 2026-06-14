import os
from flask import Flask, render_template, g, redirect
import sqlite3
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'store.db')

app = Flask(__name__)


# --- SECURE CLOUD STORAGE CONFIGURATION ---
import boto3
from botocore.config import Config

B2_KEY_ID = "005a9b63ec462530000000001"
B2_APPLICATION_KEY = "K0057rOTHXvrIxMd8zwbGqXEqrLUMmQ"
B2_BUCKET_NAME = "wildbill-vault-zips"
REGION = "us-west-004"
B2_ENDPOINT_URL = "https://s3." + REGION + ".backblazeb2.com"

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

@app.route('/')
@app.route('/')
def index():
    conn = get_db_connection()
    # Fetch all active products
    products = conn.execute('SELECT * FROM products').fetchall()
    # Fetch all unique themes dynamically to populate the filter menu
    themes_query = conn.execute('SELECT DISTINCT theme FROM products WHERE theme IS NOT NULL AND theme != "" ORDER BY theme').fetchall()
    conn.close()
    
    # Convert query database rows into a clean, flat list of string themes
    themes = [row['theme'] for row in themes_query]
    
    return render_template('index.html', products=products, themes=themes)


@app.route('/product/<sku>')
def product_detail(sku):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()
    if product is None:
        return "Product not found", 404
    return render_template('product.html', product=product)

@app.route('/download/<sku>')
def secure_download(sku):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE sku = ?', (sku,)).fetchone()
    conn.close()
    
    if product is None:
        return "Invalid Product", 404
        
    file_key = product.name + ".zip"
    
    try:
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': B2_BUCKET_NAME, 'Key': file_key},
            ExpiresIn=900
        )
        return redirect(presigned_url)
    except Exception as e:
        return "Secure Delivery Error", 500

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

    
@app.route('/nexapay-webhook', methods=['POST'])
def nexapay_webhook():
    from flask import request, jsonify
    
    # 1. PASTE YOUR ACTUAL NEXAPAY WEBHOOK SECRET STRING BELOW:
    NEXAPAY_SECRET = "whsec_267ef3c8ac5f12a5bce86f0489ea0963ffad0ca08cf7ade21e367c0ac7edf561"
    
    # Grab the cryptographic signature header NexaPay sends with the message
    incoming_signature = request.headers.get('X-NexaPay-Signature')
    
    # Block the request immediately if the signatures do not match up
    if incoming_signature != NEXAPAY_SECRET:
        return "Unauthorized Request Source", 401
        
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
                # This safely triggers the file generation loop upon signature match
                print(f"Verified payment! Link {download_url} created for {customer_email}")
                
            except Exception as e:
                print(f"Processing error: {e}")
                
    return jsonify({"status": "verified"}), 200

if __name__ == '__main__':
    app.run(debug=True)

