#!/usr/bin/env python3
"""Собирает АНИМИРОВАННЫЙ кликабельный баннер для GitHub README.

Запуск:  python3 build.py banner.png
Нужен: pip install pillow
Результат: assets/top.svg, assets/row_0..6.svg, assets/bottom.png и README.md

Каждый кусок баннера — SVG со встроенной картинкой (PNG в base64) и анимацией поверх.
GitHub показывает такие SVG в README вместе с CSS-анимацией.
Координаты заданы для эталонного баннера 953x552, поэтому подходит любое разрешение.
"""
import base64
import io
import sys
from pathlib import Path

from PIL import Image

REF_W, REF_H = 953, 552
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
    im = Image.open(src).convert("RGBA")
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
