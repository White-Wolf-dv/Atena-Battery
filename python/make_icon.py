from PIL import Image, ImageDraw

def create_icon(filename="app_icon.ico"):
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []
    
    for w, h in sizes:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw dark circle background
        pad = max(1, w // 16)
        draw.ellipse([pad, pad, w - pad, h - pad], fill=(18, 22, 32, 255))
        
        # Draw green battery progress arc
        thick = max(2, w // 9)
        ring_pad = pad + thick // 2
        draw.arc(
            [ring_pad, ring_pad, w - ring_pad, h - ring_pad],
            start=-90, end=170,
            fill=(38, 208, 124, 255),
            width=thick
        )
        
        # Draw center lightning bolt / battery dot
        cx, cy = w // 2, h // 2
        r = max(2, w // 8)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 240))
        
        images.append(img)
        
    images[0].save(filename, format="ICO", sizes=sizes)
    print(f"Icon created successfully: {filename}")

if __name__ == "__main__":
    create_icon(r"C:\Users\White Wolf\.gemini\antigravity\scratch\bluetooth_battery_py\app_icon.ico")
