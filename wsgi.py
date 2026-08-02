import os
os.environ['PAY_PROVIDER'] = 'gumroad'
os.environ['PAY_SERVICE_CHECKOUT_URL'] = 'https://api-clipart.wildbillsproplans.com'

from app import app as application
