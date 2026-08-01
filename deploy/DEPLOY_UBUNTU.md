Deploy clipart.wildbillsproplans.com and api-clipart.wildbillsproplans.com on Ubuntu + Porkbun

1) DNS in Porkbun
- Type: A
- Host: clipart
- Answer: your server public IP
- TTL: 600
- Type: A
- Host: api-clipart
- Answer: your server public IP
- TTL: 600

2) Server packages
- sudo apt update
- sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx

3) Project setup
- cd /home/wildbill/wildbill_secure_vault
- python3 -m venv venv
- source venv/bin/activate
- pip install --upgrade pip
- pip install -r requirements.txt

4) Environment file
- cp deploy/.env.example deploy/.env
- nano deploy/.env
- Set FLASK_SECRET_KEY to a long random value
- Set PAY_PROVIDER=stripe when using Stripe native checkout sessions
- Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET
- Set STRIPE_CURRENCY (default: usd)
- If not using Stripe native mode, set PAY_SERVICE_CHECKOUT_URL to your payment provider endpoint (example: https://pay.example.com/checkout?sku={sku})
- Optional tuning: DOWNLOAD_TOKEN_TTL_HOURS, DOWNLOAD_URL_EXPIRES_SECONDS, PURCHASE_MATCH_WINDOW_MINUTES

5) Systemd service
- sudo cp deploy/wildbill-vault.service /etc/systemd/system/wildbill-vault.service
- sudo systemctl daemon-reload
- sudo systemctl enable wildbill-vault
- sudo systemctl start wildbill-vault
- sudo systemctl status wildbill-vault

6) Nginx site
- sudo cp deploy/nginx.clipart.wildbillsproplans.com.conf /etc/nginx/sites-available/clipart.wildbillsproplans.com
- sudo ln -s /etc/nginx/sites-available/clipart.wildbillsproplans.com /etc/nginx/sites-enabled/clipart.wildbillsproplans.com
- sudo nginx -t
- sudo systemctl reload nginx

7) SSL certificate
- Wait until DNS resolves to this server IP
- sudo certbot --nginx -d clipart.wildbillsproplans.com -d api-clipart.wildbillsproplans.com

8) Verify
- curl -I http://clipart.wildbillsproplans.com
- curl -I https://clipart.wildbillsproplans.com
- curl -I http://api-clipart.wildbillsproplans.com
- curl -I https://api-clipart.wildbillsproplans.com
- curl -I "https://api-clipart.wildbillsproplans.com/checkout/WB-BND-143?product_id=WB_BND_143&success_url=https%3A%2F%2Fwildbillsproplans.com&cancel_url=https%3A%2F%2Fwildbillsproplans.com&mode=payment"
- curl -I https://api-clipart.wildbillsproplans.com/stripe-webhook
- journalctl -u wildbill-vault -n 100 --no-pager

10) Stripe dashboard wiring (required in Stripe mode)
- Configure webhook endpoint: https://api-clipart.wildbillsproplans.com/stripe-webhook
- Subscribe at minimum to event: checkout.session.completed
- Price IDs are optional now: if a SKU has no Stripe Price ID in your dataset, checkout auto-creates dynamic price_data from your local product price

9) Useful operations
- sudo systemctl restart wildbill-vault
- sudo systemctl restart nginx
- sudo journalctl -u wildbill-vault -f
