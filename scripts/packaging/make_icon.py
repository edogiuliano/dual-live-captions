from pathlib import Path
from PIL import Image, ImageDraw
root = Path(__file__).resolve().parents[2]
image = Image.new("RGBA", (256, 256))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((0, 0, 255, 255), 60, fill="#23354f")
draw.rounded_rectangle((48, 68, 208, 108), 16, fill="#b4d3ff")
draw.rounded_rectangle((48, 144, 164, 184), 16, fill="#76d5bd")
image.save(root / "assets/app.png")
image.save(root / "assets/app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
