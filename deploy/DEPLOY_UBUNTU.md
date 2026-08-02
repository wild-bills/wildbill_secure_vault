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
- Optional for Gumroad webhook: set GUMROAD_WEBHOOK_SECRET and use the same secret in Gumroad webhook settings
- Set STRIPE_CURRENCY (default: usd)
- If not using Stripe native mode, set PAY_SERVICE_CHECKOUT_URL to your payment provider endpoint (example: https://pay.example.com/checkout?sku={sku})
- Optional tuning: DOWNLOAD_TOKEN_TTL_HOURS, DOWNLOAD_URL_EXPIRES_SECONDS, PURCHASE_MATCH_WINDOW_MINUTES
- Optional strict deploy guard after SKU permalink migration: set STRICT_GUMROAD_PERMALINKS=1 before running build_pages.sh

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

11) Gumroad permalink migration workflow
- Generate migration CSV: /home/wildbill/wildbill_secure_vault/factory-env/bin/python generate_gumroad_permalink_migration_csv.py --only-updates
- Review output CSV: gumroad_permalink_migration.csv
- Preview API operations without changes: /home/wildbill/wildbill_secure_vault/factory-env/bin/python migrate_gumroad_permalinks.py --limit 10
- Execute live permalink updates (requires GUMROAD_ACCESS_TOKEN): /home/wildbill/wildbill_secure_vault/factory-env/bin/python migrate_gumroad_permalinks.py --execute
- Review migration report: gumroad_permalink_migration_report.csv
- Update Gumroad product permalinks using the CSV mapping (current_permalink -> target_sku_permalink)
- Verify strict mode passes: /home/wildbill/wildbill_secure_vault/factory-env/bin/python validate_gumroad_permalinks.py --strict-sku
- Enforce in deploy builds: STRICT_GUMROAD_PERMALINKS=1 bash build_pages.sh
