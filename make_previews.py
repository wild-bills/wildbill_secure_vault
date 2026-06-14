import os
import random
from PIL import Image, ImageDraw

os.makedirs('static/images', exist_ok=True)

if not os.path.exists('collage.jpg'):
    print("Error: Please make sure 'collage.jpg' is placed inside this folder!")
    exit(1)

collage = Image.open('collage.jpg').convert('RGB')
c_width, c_height = collage.size

items = [
    "Seductive_Reds_Feed_Collection",
    "Spicy_Sensual_Post_Kit",
    "Adult_Creator_60_Mega_Bundle",
    "Brat_Aesthetic_Pink_Feed_Kit",
    "Power_Dynamics_Smooth_Kit",
    "Adult_Creator_Smooth_600_Vault_Vol2",
    "Edgy_Sassy_Creator_Kit",
    "Adult_Creator_600_Ultimate_Master_Vault"
]

# Create a unique layout background from your collage for each item
for i, name in enumerate(items):
    # Slice out a unique 600x450 section of your stitched graphics grid
    random.seed(i + 42) # Keeps cuts predictable but distinct
    x = random.randint(0, max(0, c_width - 600))
    y = random.randint(0, max(0, c_height - 450))
    
    # Crop the background section
    card_img = collage.crop((x, y, x + 600, y + 450))
    
    # Apply a dark sleek tint overlay layer so text stays readable
    overlay = Image.new('RGB', (600, 450), color='#000000')
    card_img = Image.blend(card_img, overlay, alpha=0.75)
    
    draw = ImageDraw.Draw(card_img)
    
    # Premium subtle border highlight accent lines
    draw.rectangle([(2, 2), (597, 447)], outline='#222222', width=2)
    draw.rectangle([(4, 4), (595, 445)], outline='#a61c1c', width=1)
    
    clean_title = name.replace('_', ' ').upper()
    
    # Dynamic title layouts
    draw.text((40, 180), "PREMIUM VAULT", fill='#888888')
    draw.text((40, 210), clean_title, fill='#ffffff')
    draw.text((40, 380), "ADULT GRAPHICS FACTORY", fill='#ffaa00')
    
    # Save matching your template engine format
    filename = f"static/images/{name}_preview.jpg"
    card_img.save(filename, "JPEG", quality=95)
    print(f"Successfully processed: {filename}")

print("All 8 graphics-backed banners successfully built!")
