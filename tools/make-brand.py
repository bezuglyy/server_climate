#!/usr/bin/env python3
"""Генерация brand-изображений интеграции server_climate (Pillow).

Рисуем в 4x и уменьшаем — так края гладкие.
Файлы (как в brands HA): icon.png 256, icon@2x.png 512, logo.png 512x160, logo@2x.png 1024x320
и dark-варианты.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "ha-source" / "server_climate" / "brand"
SS = 4  # суперсэмплинг

SKY = (14, 165, 233)
TEAL = (13, 148, 136)
SKY_DARK = (2, 132, 199)
TEAL_DARK = (17, 94, 89)
INK = (15, 23, 42)
INK_SOFT = (100, 116, 139)
INK_DARK = (241, 245, 249)
INK_SOFT_DARK = (148, 163, 184)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def gradient(
    size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]
) -> Image.Image:
    img = Image.new("RGB", (1, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return img.resize((size, size), Image.BILINEAR)


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size * SS, size * SS), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        (0, 0, size * SS - 1, size * SS - 1), radius=radius * SS, fill=255
    )
    return m.resize((size, size), Image.LANCZOS)


def draw_snowflake(
    d: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    r: float,
    width: float,
    color,
    ticks: bool = True,
) -> None:
    """Классическая снежинка: 6 лучей + по две веточки на луч."""
    for i in range(6):
        a = math.radians(60 * i - 90)
        x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
        d.line((cx, cy, x2, y2), fill=color, width=int(width))
        d.ellipse(
            (x2 - width / 2, y2 - width / 2, x2 + width / 2, y2 + width / 2), fill=color
        )
        if not ticks:
            continue
        for frac, length in ((0.55, 0.30), (0.80, 0.20)):
            bx, by = cx + r * frac * math.cos(a), cy + r * frac * math.sin(a)
            for sign in (-1, 1):
                b = a + math.radians(45 * sign)
                ex, ey = bx + r * length * math.cos(b), by + r * length * math.sin(b)
                d.line((bx, by, ex, ey), fill=color, width=max(2, int(width * 0.72)))


def rack(d: ImageDraw.ImageDraw, size: int, color) -> None:
    """Три юнита стойки — намёк на серверную, тихо на фоне."""
    w = size * 0.44
    h = size * 0.042
    x0 = (size - w) / 2
    gap = size * 0.032
    y0 = size * 0.705
    rad = h / 2
    for i in range(3):
        y = y0 + i * (h + gap)
        d.rounded_rectangle((x0, y, x0 + w, y + h), radius=rad, fill=color)
        for j in range(3):
            cx = x0 + w * (0.16 + 0.12 * j)
            d.ellipse(
                (cx - h * 0.18, y + h * 0.32, cx + h * 0.18, y + h * 0.68), fill=color
            )


def badge(size: int, dark: bool = False) -> Image.Image:
    S = size * SS
    top, bottom = (SKY_DARK, TEAL_DARK) if dark else (SKY, TEAL)
    img = gradient(S, top, bottom).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle(
        (0, 0, S - 1, S - 1),
        radius=0.22 * S,
        fill=None,
        outline=(255, 255, 255, 26),
        width=int(S * 0.008),
    )
    rack(d, S, (255, 255, 255, 40))
    draw_snowflake(d, S / 2, S * 0.405, S * 0.255, S * 0.024, (255, 255, 255, 245))
    img = img.resize((size, size), Image.LANCZOS)
    img.putalpha(rounded_mask(size, round(size * 0.22)))
    return img


def _fit(path: str, text: str, max_w: int, start: int, draw: ImageDraw.ImageDraw):
    size = start
    while size > 8:
        f = ImageFont.truetype(path, size)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f
        size -= 1
    return ImageFont.truetype(path, 8)


def logo(width: int, height: int, dark: bool = False) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bh = int(height * 0.82)
    img.alpha_composite(badge(bh, dark), (0, (height - bh) // 2))

    x = bh + int(height * 0.16)
    avail = width - x - int(height * 0.06)
    t1 = "Server Climate"
    t2 = "серверная · techlan.su"
    f1 = _fit(FONT_BOLD, t1, avail, int(height * 0.34), d)
    f2 = _fit(FONT_REG, t2, avail, int(height * 0.16), d)
    b1 = d.textbbox((0, 0), t1, font=f1)
    b2 = d.textbbox((0, 0), t2, font=f2)
    gap = int(height * 0.07)
    total = (b1[3] - b1[1]) + gap + (b2[3] - b2[1])
    y = (height - total) / 2
    d.text((x, y - b1[1]), t1, font=f1, fill=INK_DARK if dark else INK)
    d.text((x, y + (b1[3] - b1[1]) + gap - b2[1]), t2, font=f2,
           fill=INK_SOFT_DARK if dark else INK_SOFT)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "icon.png": badge(256),
        "icon@2x.png": badge(512),
        "dark_icon.png": badge(256, dark=True),
        "dark_icon@2x.png": badge(512, dark=True),
        "logo.png": logo(512, 160),
        "logo@2x.png": logo(1024, 320),
        "dark_logo.png": logo(512, 160, dark=True),
        "dark_logo@2x.png": logo(1024, 320, dark=True),
    }
    for name, im in files.items():
        im.save(OUT / name, "PNG", optimize=True)
        print(
            f"  {name:<20} {im.size[0]}x{im.size[1]}  {(OUT / name).stat().st_size // 1024} КБ"
        )
    print("готово:", OUT)


if __name__ == "__main__":
    main()
