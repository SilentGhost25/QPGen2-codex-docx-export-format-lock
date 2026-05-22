import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_seals():
    assets_dir = Path("app/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate DSATM Seal (Yellow/Blue circular logo)
    size = 400
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Outer circle
    draw.ellipse([10, 10, size-10, size-10], fill="#fff8cc", outline="#0057b8", width=12)
    # Inner circle
    draw.ellipse([50, 50, size-50, size-50], fill="#f7d21a", outline="#0057b8", width=8)
    
    # Center crest (Crest triangle + base rectangle)
    # Scale from SVG: viewBox 120
    # Tri: (35, 72) -> (85, 72) -> (60, 38)
    # Tri scaled (x * 400/120): (116, 240) -> (283, 240) -> (200, 126)
    draw.polygon([(116, 240), (283, 240), (200, 126)], fill="#0057b8")
    # Rect: x=41, y=74, w=38, h=10 -> x=136, y=246, w=126, h=33
    draw.rectangle([136, 246, 262, 280], fill="#0057b8")
    
    # Add little decorative dots inside the crest
    # Yellow stars/dots in the blue triangle
    draw.ellipse([194, 150, 206, 162], fill="#f7d21a")
    draw.ellipse([174, 180, 186, 192], fill="#f7d21a")
    draw.ellipse([214, 180, 226, 192], fill="#f7d21a")
    draw.ellipse([154, 210, 166, 222], fill="#f7d21a")
    draw.ellipse([194, 210, 206, 222], fill="#f7d21a")
    draw.ellipse([234, 210, 246, 222], fill="#f7d21a")
    
    # Text drawing
    try:
        font = ImageFont.truetype("arial.ttf", 26)
        font_sm = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
        font_sm = ImageFont.load_default()
        
    # Draw DSATM text arced or straight
    # Let's draw arced characters or standard centered texts
    # Top text: "DAYANANDA SAGAR" or "DSATM"
    # To keep it looking professional and aligned, we can draw the arced text.
    # But since drawing curved text in standard PIL can be hard without complex trigonometric arcing,
    # let's write a simple loop to draw arced characters!
    def draw_arced_text(draw_obj, text, cx, cy, r, start_angle, end_angle, font_obj, fill_color, is_top=True):
        import math
        chars = list(text)
        num_chars = len(chars)
        if num_chars == 0: return
        
        angle_step = (end_angle - start_angle) / (num_chars - 1) if num_chars > 1 else 0
        for i, char in enumerate(chars):
            angle = start_angle + i * angle_step
            # Calculate position
            rad = math.radians(angle)
            x = cx + r * math.cos(rad)
            y = cy + r * math.sin(rad)
            
            # Create a separate transparent image for each char to rotate it
            char_img = Image.new("RGBA", (80, 80), (0,0,0,0))
            char_draw = ImageDraw.Draw(char_img)
            char_draw.text((40, 40), char, fill=fill_color, font=font_obj, anchor="mm")
            
            # Rotate
            # Rotation angle in degrees:
            # For top text: character is upright at angle = 270 (top), so we rotate by (angle - 90) or (angle + 90)
            rot_deg = angle + 90 if is_top else angle - 90
            rotated_char = char_img.rotate(-rot_deg, resample=Image.Resampling.BICUBIC)
            
            # Paste onto main image
            img.paste(rotated_char, (int(x - 40), int(y - 40)), rotated_char)

    # Top text: "DSATM"
    draw_arced_text(draw, "DSATM", size/2, size/2, 125, 220, 320, font, "#0057b8", is_top=True)
    # Bottom text: "BENGALURU"
    draw_arced_text(draw, "BENGALURU", size/2, size/2, 125, 40, 140, font_sm, "#0057b8", is_top=False)
    
    img.save(assets_dir / "dsatm-seal.png", "PNG")
    
    # 2. Generate IQAC Seal (Blue circular logo)
    img_iqac = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    draw_iqac = ImageDraw.Draw(img_iqac)
    
    # Outer circle
    draw_iqac.ellipse([10, 10, size-10, size-10], fill="#eef3ff", outline="#304ffe", width=12)
    # Middle circle
    draw_iqac.ellipse([60, 60, size-60, size-60], fill="#ffffff", outline="#304ffe", width=6)
    # Inner circle
    draw_iqac.ellipse([100, 100, size-100, size-100], fill="#eef3ff", outline="#304ffe", width=4)
    
    # Center text: "IQAC" and "DSATM"
    try:
        font_iqac = ImageFont.truetype("arialbd.ttf", 36)
        font_dsatm = ImageFont.truetype("arialbd.ttf", 26)
        font_labels = ImageFont.truetype("arialbd.ttf", 22)
    except IOError:
        font_iqac = ImageFont.load_default()
        font_dsatm = ImageFont.load_default()
        font_labels = ImageFont.load_default()
        
    draw_iqac.text((size/2, size/2 - 25), "IQAC", fill="#304ffe", font=font_iqac, anchor="mm")
    draw_iqac.text((size/2, size/2 + 25), "DSATM", fill="#304ffe", font=font_dsatm, anchor="mm")
    
    # Top curved label: "QUALITY"
    draw_arced_text(draw_iqac, "QUALITY", size/2, size/2, 115, 210, 330, font_labels, "#304ffe", is_top=True)
    # Bottom curved label: "ASSURANCE"
    draw_arced_text(draw_iqac, "ASSURANCE", size/2, size/2, 115, 30, 150, font_labels, "#304ffe", is_top=False)
    
    img_iqac.save(assets_dir / "iqac-seal.png", "PNG")
    print("Seals generated successfully!")

if __name__ == "__main__":
    generate_seals()
