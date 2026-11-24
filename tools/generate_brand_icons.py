"""Generate professional brand icons for TKS Engine 2.0.

Produces:
- assets/tks_engine.png (512x512 high-res master icon)
- assets/tks_engine.ico (Windows multi-resolution ICO containing 16, 24, 32, 48, 64, 128, 256)
- assets/icon.ico (for existing application references)
"""
from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def create_tks_icon(size: int = 512) -> Image.Image:
    # Canvas with transparency
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    scale = size / 512.0
    margin = int(24 * scale)
    corner = int(100 * scale)

    # 1. Subtle drop shadow behind the card
    shadow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow_img)
    sdraw.rounded_rectangle(
        [margin, margin + int(14 * scale), size - margin, size - margin + int(14 * scale)],
        radius=corner,
        fill=(0, 0, 0, 110),
    )
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(18 * scale)))
    img.alpha_composite(shadow_img)

    # 2. Main rounded card base (Dark Sleek Titanium / TikTok Studio Dark background)
    card_box = [margin, margin, size - margin, size - margin]
    draw.rounded_rectangle(card_box, radius=corner, fill=(22, 24, 35, 255))

    # Inner subtle gradient / border ring in TikTok Red and Cyan
    for i in range(int(3 * scale)):
        inset = margin + i
        draw.rounded_rectangle(
            [inset, inset, size - inset, size - inset],
            radius=max(1, corner - i),
            outline=(45, 48, 64, 255),
            width=1,
        )

    # 3. Dynamic Video Automation Geometry
    # Two intersecting dynamic arcs / rings representing scheduling & automation
    cx, cy = size / 2, size / 2

    # Cyan automation orbital arc (TikTok Cyan: #25F4EE)
    cyan = (37, 244, 238, 240)
    arc_rad = int(155 * scale)
    arc_box = [cx - arc_rad, cy - arc_rad, cx + arc_rad, cy + arc_rad]
    draw.arc(arc_box, start=-40, end=130, fill=cyan, width=int(14 * scale))

    # Red/Pink automation orbital arc (TikTok Red: #FE2C55)
    red = (254, 44, 85, 245)
    draw.arc(arc_box, start=140, end=310, fill=red, width=int(14 * scale))

    # Small circular indicator nodes on the orbit (automation clock nodes)
    def draw_node(angle_deg: float, fill_color: tuple[int, int, int, int], r_node: float):
        rad = math.radians(angle_deg)
        nx = cx + arc_rad * math.cos(rad)
        ny = cy + arc_rad * math.sin(rad)
        draw.ellipse([nx - r_node, ny - r_node, nx + r_node, ny + r_node], fill=fill_color)

    draw_node(-40, (255, 255, 255, 255), 8 * scale)
    draw_node(130, (255, 255, 255, 255), 8 * scale)
    draw_node(140, (255, 255, 255, 255), 8 * scale)
    draw_node(310, (255, 255, 255, 255), 8 * scale)

    # 4. Center Play / Rocket Badge (Glowing play triangle with layered neon)
    # Background circular pill for the play button
    pill_r = int(90 * scale)
    draw.ellipse(
        [cx - pill_r, cy - pill_r, cx + pill_r, cy + pill_r],
        fill=(30, 33, 46, 255),
        outline=(254, 44, 85, 200),
        width=int(2 * scale),
    )

    # TikTok Chromatic Offset Play Triangle
    # Left: Cyan offset
    c_offset = int(4 * scale)
    play_h = int(60 * scale)
    play_w = int(68 * scale)
    p_left = cx - play_w / 2 + int(6 * scale)

    cyan_pts = [
        (p_left - c_offset, cy - play_h),
        (p_left - c_offset, cy + play_h),
        (p_left + play_w - c_offset, cy),
    ]
    draw.polygon(cyan_pts, fill=(37, 244, 238, 220))

    # Right: Red offset
    red_pts = [
        (p_left + c_offset, cy - play_h),
        (p_left + c_offset, cy + play_h),
        (p_left + play_w + c_offset, cy),
    ]
    draw.polygon(red_pts, fill=(254, 44, 85, 220))

    # Center: Crisp Pure White Play Button
    white_pts = [
        (p_left, cy - play_h),
        (p_left, cy + play_h),
        (p_left + play_w, cy),
    ]
    draw.polygon(white_pts, fill=(255, 255, 255, 255))

    # 5. Badge Label: "TKS" at the bottom center
    badge_w = int(120 * scale)
    badge_h = int(32 * scale)
    badge_top = cy + arc_rad + int(14 * scale)
    draw.rounded_rectangle(
        [cx - badge_w / 2, badge_top, cx + badge_w / 2, badge_top + badge_h],
        radius=int(10 * scale),
        fill=(254, 44, 85, 255),
    )

    # Draw "TKS 2.0" text inside the badge if font available, else simple block letters
    try:
        font = ImageFont.truetype("segoeuib.ttf", int(18 * scale))
        draw.text((cx, badge_top + badge_h / 2), "TKS 2.0", fill=(255, 255, 255, 255), font=font, anchor="mm")
    except Exception:
        pass

    return img


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    master_png = assets_dir / "tks_engine.png"
    master_ico = assets_dir / "tks_engine.ico"
    legacy_ico = assets_dir / "icon.ico"

    print("Generating 512x512 master high-resolution icon...")
    img512 = create_tks_icon(512)
    img512.save(master_png, format="PNG")
    print(f"Saved: {master_png}")

    print("Generating Windows multi-resolution ICO file...")
    # Standard Windows icon sizes
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_images = []
    for w, h in sizes:
        icon_images.append(img512.resize((w, h), Image.Resampling.LANCZOS))

    img512.resize((256, 256), Image.Resampling.LANCZOS).save(
        master_ico,
        format="ICO",
        sizes=sizes,
        append_images=icon_images,
    )
    print(f"Saved: {master_ico}")

    # Also overwrite assets/icon.ico so the entire Qt app uses it immediately
    img512.resize((256, 256), Image.Resampling.LANCZOS).save(
        legacy_ico,
        format="ICO",
        sizes=sizes,
        append_images=icon_images,
    )
    print(f"Saved: {legacy_ico}")


if __name__ == "__main__":
    main()
