"""Draw Jarvis's shortcut icon: dark tile, cyan ring, voice-wave bars.

    uv run --with pillow python assets/make_icon.py assets/jarvis.ico [preview.png]
"""
import sys

from PIL import Image, ImageDraw, ImageFilter

S = 1024                      # draw big, scale down for smooth edges
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([40, 40, S - 40, S - 40], radius=220, fill=(12, 20, 36, 255))

# soft glow behind the ring
glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
g = ImageDraw.Draw(glow)
g.ellipse([170, 170, S - 170, S - 170], outline=(40, 210, 255, 150), width=70)
glow = glow.filter(ImageFilter.GaussianBlur(40))
img = Image.alpha_composite(img, glow)
d = ImageDraw.Draw(img)
d.ellipse([190, 190, S - 190, S - 190], outline=(70, 220, 255, 255), width=46)

# five rounded bars, tallest in the middle
heights = [150, 270, 380, 270, 150]
bar_w, gap = 62, 34
total = len(heights) * bar_w + (len(heights) - 1) * gap
x = (S - total) // 2
for i, h in enumerate(heights):
    top, bottom = S // 2 - h // 2, S // 2 + h // 2
    shade = (150, 240, 255, 255) if i == 2 else (90, 225, 255, 255)
    d.rounded_rectangle([x, top, x + bar_w, bottom], radius=bar_w // 2, fill=shade)
    x += bar_w + gap

out = sys.argv[1]
icon = img.resize((256, 256), Image.LANCZOS)
icon.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
if len(sys.argv) > 2:
    icon.save(sys.argv[2])
