#!/usr/bin/env python3
"""Собирает АНИМИРОВАННЫЙ кликабельный баннер для GitHub README.

Запуск:  python3 build.py banner.png
Нужен: pip install pillow numpy
Результат: assets/top.svg, assets/row_0..6.svg, assets/bottom.png и README.md

Каждый кусок баннера — SVG со встроенной картинкой (PNG в base64) и анимацией поверх.
GitHub показывает такие SVG в README вместе с CSS-анимацией.
Координаты заданы для эталонного баннера 953x552, поэтому подходит любое разрешение.
"""
import base64
import io
import sys
from pathlib import Path

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REF_W, REF_H = 953, 552
FONT_DIR = Path(__file__).parent / "fonts"  # Inter (лицензия OFL), лежит рядом со скриптом

# Подписи в ряду контактов (координаты эталонного баннера 953x552):
# (текст, центр пилюли по x, рамка иконки, рамка старого текста)
CONTACTS = [
    ("Telegram", 298.5, (237, 434, 260, 454), (275, 439, 359, 451)),
    ("LinkedIn", 538.5, (446, 432, 471, 455), (485, 439, 631, 451)),
    ("Gmail", 808.0, (716, 434, 742, 455), (757, 439, 899, 451)),
]
PILL_TEXT_SIZE = 14.5          # размер подписи в пилюле
PILL_TEXT_COLOR = (236, 240, 246)
LABEL_TEXT = "Contacts"        # вместо "Say Hi"
LABEL_BOX = (91, 432, 154, 459)  # стираемая область старой надписи
LABEL_X, LABEL_BASELINE, LABEL_SIZE = 95, 451, 18
LABEL_COLOR = (242, 244, 247)
# область слова «Niyazaly» (в координатах эталонного баннера) и цвет слова «Dias»
NAME_BOX = (318, 86, 500, 138)
NAME_WHITE = (248, 247, 247)
Y_CUTS = [0, 398, 490, 552]
X_CUTS = [0, 211, 385, 421, 656, 690, 924, 953]
SCALE = 99.6  # ширина всего баннера в % (чуть меньше 100, чтобы ряд не переносился)

LINKS = {
    1: ("https://t.me/dniyazaly", "Telegram — t.me/dniyazaly"),
    3: ("https://www.linkedin.com/in/dias-niyazaly-5a2b6b433", "LinkedIn — Dias Niyazaly"),
    5: (
        "https://mail.google.com/mail/?view=cm&fs=1&to=dias.niyazaly@jihc.edu.kz",
        "Gmail — dias.niyazaly@jihc.edu.kz",
    ),
}

CSS = """
.fx{pointer-events:none}
.tw{animation:tw 3s ease-in-out infinite}
@keyframes tw{0%,100%{opacity:.05}50%{opacity:1}}
.pulse{animation:pulse 3.2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.08}50%{opacity:.85}}
.pulse-soft{animation:pulse2 3.6s ease-in-out infinite}
@keyframes pulse2{0%,100%{opacity:0}50%{opacity:.4}}
.run{stroke-dasharray:16 84;animation:run 3.6s linear infinite}
@keyframes run{from{stroke-dashoffset:0}to{stroke-dashoffset:-100}}
.sheen{animation:sheen 7s ease-in-out infinite}
@keyframes sheen{0%{transform:translateX(-160px)}45%,100%{transform:translateX(1100px)}}
@media (prefers-reduced-motion:reduce){.fx{display:none}}
"""

DEFS = """
<filter id="b2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>
<filter id="b8" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
<linearGradient id="sh" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#9ec5ff" stop-opacity="0"/>
  <stop offset=".5" stop-color="#9ec5ff" stop-opacity=".26"/>
  <stop offset="1" stop-color="#9ec5ff" stop-opacity="0"/>
</linearGradient>
<clipPath id="panel"><rect x="21" y="241" width="914" height="144" rx="18"/></clipPath>
"""


def whiten_name(im: Image.Image) -> Image.Image:
    """Перекрашивает градиентное слово «Niyazaly» в белый, сохраняя сглаживание краёв."""
    W, H = im.size
    x0, x1 = round(NAME_BOX[0] / REF_W * W), round(NAME_BOX[2] / REF_W * W)
    y0, y1 = round(NAME_BOX[1] / REF_H * H), round(NAME_BOX[3] / REF_H * H)
    arr = np.array(im.convert("RGBA")).astype(float)
    reg = arr[y0:y1, x0:x1, :3]
    h = reg.shape[0]
    # фон: плавный переход между верхними и нижними строками области (вокруг текста чистое тёмное небо)
    top, bot = reg[:2].mean(0), reg[-2:].mean(0)
    t = np.linspace(0, 1, h)[:, None, None]
    bg = top[None] * (1 - t) + bot[None] * t
    mx, bgmx = reg.max(2), bg.max(2)
    a = np.clip((mx - bgmx) / (250.0 - bgmx), 0, 1)       # «сколько текста» в пикселе
    a = np.clip((a - 0.04) / 0.96, 0, 1)                   # отсекаем шум фона
    a = a[..., None]
    white = np.array(NAME_WHITE, float)
    new = np.where(a > 0, bg * (1 - a) + white * a, reg)
    arr[y0:y1, x0:x1, :3] = new
    return Image.fromarray(arr.round().clip(0, 255).astype("uint8"), "RGBA")


def _font(weight: str, px: float) -> ImageFont.FreeTypeFont:
    for p in (FONT_DIR / f"Inter-{weight}.otf", Path("/usr/share/fonts/opentype/inter") / f"Inter-{weight}.otf"):
        if p.exists():
            return ImageFont.truetype(str(p), max(1, round(px)))
    raise SystemExit(f"Не найден шрифт Inter-{weight}.otf (положи его в папку fonts/)")


def _fill_bg(arr, x0, y0, x1, y1):
    """Фон прямоугольника: плавный переход по горизонтали между соседними колонками слева и справа."""
    left = arr[y0:y1, x0 - 3 : x0, :3].mean(1)
    right = arr[y0:y1, x1 : x1 + 3, :3].mean(1)
    t = np.linspace(0, 1, x1 - x0)[None, :, None]
    return left[:, None, :] * (1 - t) + right[:, None, :] * t


def _draw_text(arr, text, weight, size, color, x, baseline, gamma=0.85, ss=4):
    """Рисует текст со сглаживанием (рисуем в 4x и уменьшаем). x/baseline — в пикселях картинки."""
    f = _font(weight, size * ss)
    tw = f.getlength(text) / ss
    px0, py0 = math.floor(x) - 3, math.floor(baseline - size * 1.1) - 3
    lw, lh = math.ceil(tw) + 8, math.ceil(size * 1.6) + 8
    layer = Image.new("L", (lw * ss, lh * ss), 0)
    ImageDraw.Draw(layer).text(((x - px0) * ss, (baseline - py0) * ss), text, font=f, fill=255, anchor="ls")
    a = np.asarray(layer.resize((lw, lh), Image.BOX), float)[..., None] / 255.0
    a = a**gamma
    H, W = arr.shape[:2]
    ys0, xs0 = max(py0, 0), max(px0, 0)
    ys1, xs1 = min(py0 + lh, H), min(px0 + lw, W)
    a = a[ys0 - py0 : ys1 - py0, xs0 - px0 : xs1 - px0]
    reg = arr[ys0:ys1, xs0:xs1, :3]
    arr[ys0:ys1, xs0:xs1, :3] = reg * (1 - a) + np.array(color, float) * a


def retext(im: Image.Image) -> Image.Image:
    """«Say Hi» -> «Contacts»; в пилюлях вместо ссылок — логотип + название (по центру)."""
    W, H = im.size
    s = W / REF_W
    arr = np.array(im.convert("RGBA")).astype(float)
    orig = arr.copy()
    S = lambda v: int(round(v * s))  # noqa: E731

    def erase(x0, y0, x1, y1):
        """Стирает прямоугольник фоном; края смягчены, чтобы не было видно границы."""
        bg = _fill_bg(orig, x0, y0, x1, y1)
        r = max(2, S(3))
        ramp = lambda n: np.clip(np.minimum(np.arange(n) + 1, np.arange(n)[::-1] + 1) / r, 0, 1)  # noqa: E731
        w = (ramp(y1 - y0)[:, None] * ramp(x1 - x0)[None, :])[..., None]
        arr[y0:y1, x0:x1, :3] = orig[y0:y1, x0:x1, :3] * (1 - w) + bg * w
        return bg

    # 1) пилюли: стираем иконку+текст, ставим иконку и название по центру
    for text, cx, (ix0, iy0, ix1, iy1), (tx0, ty0, tx1, ty1) in CONTACTS:
        x0, x1, y0, y1 = S(ix0 - 5), S(tx1 + 6), S(428), S(460)
        bg = erase(x0, y0, x1, y1)
        # иконка: вырезаем из оригинала (с запасом 2px) и ставим на новое место;
        # переносится только сама иконка (по маске), фон вокруг остаётся чистым
        m = 2
        ox0, ox1, oy0, oy1 = S(ix0) - m, S(ix1 + 1) + m, S(iy0) - m, S(iy1 + 1) + m
        icon = orig[oy0:oy1, ox0:ox1, :3]
        bg_old = bg[oy0 - y0 : oy1 - y0, ox0 - x0 : ox1 - x0]
        mask = np.clip((np.abs(icon - bg_old).max(2) - 5) / 25, 0, 1)[..., None]
        font = _font("Medium", PILL_TEXT_SIZE * s * 4)
        text_w = font.getlength(text) / 4
        icon_w, gap = S(ix1 + 1 - ix0), S(10)
        left = cx * s - (icon_w + gap + text_w) / 2
        nx0 = int(round(left)) - m
        target = arr[oy0:oy1, nx0 : nx0 + (ox1 - ox0), :3]
        arr[oy0:oy1, nx0 : nx0 + (ox1 - ox0), :3] = np.clip(target + mask * (icon - bg_old), 0, 255)
        base = 445.0 * s + 0.727 * PILL_TEXT_SIZE * s / 2  # центр заглавных букв на центре пилюли
        _draw_text(arr, text, "Medium", PILL_TEXT_SIZE * s, PILL_TEXT_COLOR, left + icon_w + gap, base)

    # 2) «Say Hi» -> «Contacts»
    lx0, ly0, lx1, ly1 = (S(v) for v in LABEL_BOX)
    erase(lx0, ly0, lx1, ly1)
    _draw_text(arr, LABEL_TEXT, "SemiBold", LABEL_SIZE * s, LABEL_COLOR, LABEL_X * s, LABEL_BASELINE * s)

    return Image.fromarray(arr.round().clip(0, 255).astype("uint8"), "RGBA")


def b64_png(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def svg(w, h, im, overlay):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<defs><style>{CSS}</style>{DEFS}</defs>"
        f'<image width="{w}" height="{h}" preserveAspectRatio="none" '
        f'href="data:image/png;base64,{b64_png(im)}"/>'
        f'<g class="fx">{overlay}</g></svg>'
    )


def stars(ox=0, oy=0):
    pts = [(265, 22), (320, 48), (372, 16), (420, 60), (470, 28), (520, 12), (560, 50),
           (610, 24), (640, 66), (690, 18), (745, 34), (800, 12), (835, 52), (300, 72)]
    out = []
    for i, (x, y) in enumerate(pts):
        r = 1.1 + (i % 3) * 0.45
        out.append(
            f'<circle class="tw" cx="{x-ox}" cy="{y-oy}" r="{r}" fill="#ffffff" '
            f'style="animation-delay:{(i*0.37)%3:.2f}s;animation-duration:{2.4+(i%4)*0.5:.1f}s"/>'
        )
        if i % 3 == 0:
            out.append(
                f'<circle class="tw" cx="{x-ox}" cy="{y-oy}" r="{r*2.6}" fill="#9ec5ff" filter="url(#b2)" '
                f'style="animation-delay:{(i*0.37)%3:.2f}s;animation-duration:{2.4+(i%4)*0.5:.1f}s"/>'
            )
    return "".join(out)


def top_overlay():
    return (
        stars()
        # пульс кольца логотипа
        + '<circle class="pulse" cx="104" cy="130" r="61" fill="none" stroke="#4da3ff" stroke-width="5" filter="url(#b2)"/>'
        + '<circle class="pulse" cx="104" cy="130" r="61" fill="none" stroke="#7cc0ff" stroke-width="1.5"/>'
        # свечение иконки </>
        + '<ellipse class="pulse-soft" cx="890" cy="62" rx="44" ry="26" fill="#3b82f6" filter="url(#b8)" style="animation-delay:1s"/>'
        # бегущий блик по панели Tech Stack
        + '<g clip-path="url(#panel)"><g class="sheen"><rect x="0" y="240" width="110" height="146" fill="url(#sh)" transform="skewX(-20)"/></g></g>'
        # пульс плашки Learning
        + '<rect class="pulse" x="730" y="253" width="183" height="30" rx="15" fill="none" stroke="#fbbf24" stroke-width="1.6" filter="url(#b2)" style="animation-delay:.6s"/>'
    )


PILLS = {  # индекс куска -> (x, y, w, h, цвет, задержка)  в координатах всего баннера
    1: (218, 424, 162, 42, "#38bdf8", 0.0),
    3: (427, 424, 224, 42, "#3b82f6", 1.2),
    5: (698, 424, 220, 42, "#e879f9", 2.4),
}


def row_overlay(i, ox, oy):
    out = ""
    if i == 0:  # пульс иконки самолётика рядом с "Say Hi"
        out += (
            f'<circle class="pulse-soft" cx="{62-ox}" cy="{445-oy}" r="20" fill="#3b82f6" filter="url(#b8)"/>'
        )
    if i in PILLS:
        x, y, w, h, color, delay = PILLS[i]
        x, y = x - ox, y - oy
        common = f'x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" pathLength="100" fill="none"'
        out += (
            f'<rect {common} class="run" stroke="{color}" stroke-width="5" filter="url(#b2)" '
            f'style="animation-delay:{delay}s"/>'
            f'<rect {common} class="run" stroke="#ffffff" stroke-width="1.6" stroke-linecap="round" '
            f'style="animation-delay:{delay}s"/>'
        )
    return out


def main(src: str, out: str = "assets") -> None:
    im = retext(whiten_name(Image.open(src).convert("RGBA")))
    W, H = im.size
    ys = [round(v / REF_H * H) for v in Y_CUTS]
    xs = [round(v / REF_W * W) for v in X_CUTS]
    out_dir = Path(out)
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*"):
        old.unlink()

    # верх
    top = im.crop((0, ys[0], W, ys[1]))
    (out_dir / "top.svg").write_text(svg(REF_W, Y_CUTS[1], top, top_overlay()), encoding="utf-8")
    # ряд Say Hi
    for i in range(len(xs) - 1):
        piece = im.crop((xs[i], ys[1], xs[i + 1], ys[2]))
        w, h = X_CUTS[i + 1] - X_CUTS[i], Y_CUTS[2] - Y_CUTS[1]
        (out_dir / f"row_{i}.svg").write_text(
            svg(w, h, piece, row_overlay(i, X_CUTS[i], Y_CUTS[1])), encoding="utf-8"
        )
    # низ (статичный)
    im.crop((0, ys[2], W, ys[3])).save(out_dir / "bottom.png", optimize=True)

    # README
    widths = [round((X_CUTS[i + 1] - X_CUTS[i]) / REF_W * SCALE, 3) for i in range(7)]
    row = ""
    for i in range(7):
        alt = LINKS[i][1] if i in LINKS else ""
        img = f'<img align="top" src="./assets/row_{i}.svg" width="{widths[i]}%" alt="{alt}" />'
        if i in LINKS:
            row += f'<a href="{LINKS[i][0]}" title="{LINKS[i][1]}">{img}</a>'
        else:
            row += img
    md = (
        '<div align="center">\n'
        f'<img align="top" src="./assets/top.svg" width="{SCALE}%" alt="Dias Niyazaly — Student &amp; Mobile Developer, '
        'Taraz, Kazakhstan. Tech stack: Flutter, Dart, Python, HTML, CSS, JavaScript, C, C++, React JS" /><br>\n'
        f"{row}<br>\n"
        f'<img align="top" src="./assets/bottom.png" width="{SCALE}%" alt="" />\n'
        "</div>\n"
    )
    Path("README.md").write_text(md, encoding="utf-8")
    print("готово:", sorted(p.name for p in out_dir.iterdir()))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "banner.png")
