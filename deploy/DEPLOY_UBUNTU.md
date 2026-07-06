Deploy design.wildbillsproplans.com and clipart.wildbillsproplans.com on Ubuntu + Porkbun

1) DNS in Porkbun
- Type: A
- Host: design
- Answer: your server public IP
- TTL: 600
- Type: A
- Host: clipart
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

5) Systemd service
- sudo cp deploy/wildbill-vault.service /etc/systemd/system/wildbill-vault.service
- sudo systemctl daemon-reload
- sudo systemctl enable wildbill-vault
- sudo systemctl start wildbill-vault
- sudo systemctl status wildbill-vault

6) Nginx site
- sudo cp deploy/nginx.design.wildbillsproplans.com.conf /etc/nginx/sites-available/design.wildbillsproplans.com
- sudo ln -s /etc/nginx/sites-available/design.wildbillsproplans.com /etc/nginx/sites-enabled/design.wildbillsproplans.com
- sudo nginx -t
- sudo systemctl reload nginx

7) SSL certificate
- Wait until DNS resolves to this server IP
- sudo certbot --nginx -d design.wildbillsproplans.com -d clipart.wildbillsproplans.com

8) Verify
- curl -I http://design.wildbillsproplans.com
- curl -I https://design.wildbillsproplans.com
- curl -I http://clipart.wildbillsproplans.com
- curl -I https://clipart.wildbillsproplans.com
- journalctl -u wildbill-vault -n 100 --no-pager

9) Useful operations
- sudo systemctl restart wildbill-vault
- sudo systemctl restart nginx
- sudo journalctl -u wildbill-vault -f
