"""Generate the TextGenius app icon using Pillow."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# Colors
PRIMARY = "#4A6FA5"
PRIMARY_DARK = "#3B5998"
WHITE = "#FFFFFF"
ACCENT = "#48BF84"

SIZES = [256, 128, 64, 48, 32, 16]
OUTPUT_DIR = Path(__file__).parent.parent / "assets"


def draw_rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rectangle."""
    x1, y1, x2, y2 = xy
    r = radius

    # Four corner circles
    draw.ellipse([x1, y1, x1 + 2*r, y1 + 2*r], fill=fill)
    draw.ellipse([x2 - 2*r, y1, x2, y1 + 2*r], fill=fill)
    draw.ellipse([x1, y2 - 2*r, x1 + 2*r, y2], fill=fill)
    draw.ellipse([x2 - 2*r, y2 - 2*r, x2, y2], fill=fill)

    # Rectangles to fill the gaps
    draw.rectangle([x1 + r, y1, x2 - r, y2], fill=fill)
    draw.rectangle([x1, y1 + r, x2, y2 - r], fill=fill)


def create_icon(size):
    """Create a single icon at the given size."""
    # Work at 4x for anti-aliasing
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background: rounded square
    margin = int(s * 0.06)
    corner_radius = int(s * 0.2)
    draw_rounded_rect(draw, (margin, margin, s - margin, s - margin), corner_radius, PRIMARY)

    # Subtle gradient overlay (darker at bottom)
    overlay = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(s):
        alpha = int(40 * (y / s))
        overlay_draw.line([(margin, y), (s - margin, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Draw a stylized "T" with a checkmark
    center_x = s // 2
    center_y = s // 2

    # Letter "T"
    t_width = int(s * 0.42)
    t_height = int(s * 0.45)
    t_stroke = int(s * 0.08)
    t_top = center_y - int(t_height * 0.5)

    # T horizontal bar
    draw.rounded_rectangle(
        [center_x - t_width // 2, t_top,
         center_x + t_width // 2, t_top + t_stroke],
        radius=t_stroke // 2,
        fill=WHITE,
    )

    # T vertical bar
    draw.rounded_rectangle(
        [center_x - t_stroke // 2, t_top,
         center_x + t_stroke // 2, t_top + t_height],
        radius=t_stroke // 2,
        fill=WHITE,
    )

    # Small checkmark in bottom-right
    check_size = int(s * 0.22)
    check_x = center_x + int(s * 0.15)
    check_y = center_y + int(s * 0.18)
    check_stroke = max(int(s * 0.04), 2)

    # Draw checkmark circle background
    circle_r = int(check_size * 0.6)
    draw.ellipse(
        [check_x - circle_r, check_y - circle_r,
         check_x + circle_r, check_y + circle_r],
        fill=ACCENT,
    )

    # Draw checkmark lines
    p1 = (check_x - int(circle_r * 0.4), check_y)
    p2 = (check_x - int(circle_r * 0.05), check_y + int(circle_r * 0.35))
    p3 = (check_x + int(circle_r * 0.45), check_y - int(circle_r * 0.3))

    draw.line([p1, p2], fill=WHITE, width=check_stroke)
    draw.line([p2, p3], fill=WHITE, width=check_stroke)

    # Downscale with anti-aliasing
    img = img.resize((size, size), Image.LANCZOS)
    return img


def main():
    """Generate all icon files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate PNG at 256px
    icon_256 = create_icon(256)
    png_path = OUTPUT_DIR / "icon.png"
    icon_256.save(png_path, "PNG")
    print(f"Created {png_path}")

    # Generate ICO with multiple sizes
    icons = [create_icon(s) for s in SIZES]
    ico_path = OUTPUT_DIR / "icon.ico"
    icons[0].save(ico_path, "ICO", sizes=[(s, s) for s in SIZES], append_images=icons[1:])
    print(f"Created {ico_path}")


if __name__ == "__main__":
    main()
