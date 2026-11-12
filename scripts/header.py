"""Generate assets/header-{light,dark}.svg for the GitHub profile README.

Text is converted to outlines so the SVG is self-contained (GitHub renders
README images in a sandbox: no external fonts). Fonts are the portfolio's:
Fraunces (display), Instrument Sans (body), Geist Mono (labels). All OFL.

To change the text or colours, edit this file and regenerate:

    pip install uharfbuzz fonttools
    mkdir -p /tmp/fonts && cd /tmp/fonts
    B=https://raw.githubusercontent.com/google/fonts/main/ofl
    curl -fLo fraunces.ttf   "$B/fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf"
    curl -fLo instrument.ttf "$B/instrumentsans/InstrumentSans%5Bwdth,wght%5D.ttf"
    curl -fLo geistmono.ttf  "$B/geistmono/GeistMono%5Bwght%5D.ttf"
    cd - && python scripts/header.py /tmp/fonts assets
"""
import io
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

FONTS = Path(sys.argv[1])
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "assets")


class Face:
    def __init__(self, file, axes):
        tt = TTFont(FONTS / file)
        tt = instancer.instantiateVariableFont(tt, axes)
        buf = io.BytesIO()
        tt.save(buf)
        self.tt = TTFont(io.BytesIO(buf.getvalue()))
        self.upem = self.tt["head"].unitsPerEm
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.hb = hb.Font(hb.Face(hb.Blob(buf.getvalue())))

    def shape(self, text, size, tracking=0.0):
        b = hb.Buffer()
        b.add_str(text)
        b.guess_segment_properties()
        hb.shape(self.hb, b, {"kern": True, "liga": True})
        s = size / self.upem
        glyphs, x = [], 0.0
        for info, pos in zip(b.glyph_infos, b.glyph_positions):
            glyphs.append((self.order[info.codepoint], x + pos.x_offset * s, pos.y_offset * s))
            x += pos.x_advance * s + tracking
        return glyphs, x - tracking, s

    def width(self, text, size, tracking=0.0):
        return self.shape(text, size, tracking)[1]

    def path(self, text, size, x0, y0, tracking=0.0, anchor="start"):
        glyphs, w, s = self.shape(text, size, tracking)
        if anchor == "middle":
            x0 -= w / 2
        elif anchor == "end":
            x0 -= w
        pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for name, gx, gy in glyphs:
            # font units are y-up; SVG is y-down
            t = TransformPen(pen, (s, 0, 0, -s, x0 + gx, y0 - gy))
            self.gs[name].draw(t)
        return pen.getCommands()


display = Face("fraunces.ttf", {"wght": 560, "opsz": 144, "SOFT": 100, "WONK": 0})
body = Face("instrument.ttf", {"wght": 430, "wdth": 100})
mono = Face("geistmono.ttf", {"wght": 500})
mono_b = Face("geistmono.ttf", {"wght": 600})

THEMES = {
    "light": dict(
        bg="#faf5e9", edge="#16324a", edge_o=0.14,
        eyebrow="#1e4f8f", name="#16324a", sub="#16324a", sub_o=0.74,
        meta="#16324a", meta_o=0.52,
        grid="#1e4f8f", grid_o=0.16, sacc="#1e4f8f", sacc_o=0.55,
        fix="#e8a25f", fix_fill_o=0.30, num="#16324a", rule="#e8a25f",
    ),
    "dark": dict(
        bg="#0e1a29", edge="#faf5e9", edge_o=0.12,
        eyebrow="#8fb8e8", name="#faf5e9", sub="#faf5e9", sub_o=0.74,
        meta="#faf5e9", meta_o=0.50,
        grid="#8fb8e8", grid_o=0.14, sacc="#8fb8e8", sacc_o=0.55,
        fix="#e8a25f", fix_fill_o=0.32, num="#faf5e9", rule="#e8a25f",
    ),
}

W, H = 1200, 340
LX = 76  # left text column

# Scanpath: (x, y, fixation duration ms). Radius scales with duration.
FIX = [
    (842, 112, 220), (968, 92, 340), (1082, 136, 180), (1010, 196, 420),
    (884, 228, 260), (958, 268, 160), (1098, 250, 300),
]


def svg(theme):
    t = THEMES[theme]
    eyebrow = mono.path("HCI RESEARCHER  ·  SOFTWARE ENGINEER", 17, LX, 104, tracking=1.6)
    name = display.path("Hugo Correia", 104, LX - 4, 196)
    sub = body.path("Eye tracking, usability evaluation & multimodal interaction", 24, LX, 248)
    meta = mono.path("AVEIRO, PORTUGAL  ·  40.64°N 8.65°W", 14, LX, 286, tracking=1.2)

    name_w = display.width("Hugo Correia", 104)
    sub_w = body.width("Eye tracking, usability evaluation & multimodal interaction", 24)

    # dot grid behind the scanpath ("stimulus" area)
    dots = []
    for gx in range(806, 1140, 24):
        for gy in range(64, 300, 24):
            dots.append(f"M{gx} {gy}h0")
    grid = " ".join(dots)

    # One polyline, so the dash animation draws it end to end like a gaze trace.
    sacc = f"M{FIX[0][0]} {FIX[0][1]}" + "".join(f"L{x} {y}" for x, y, _ in FIX[1:])
    cum = [0.0]
    for a, b in zip(FIX, FIX[1:]):
        cum.append(cum[-1] + ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)
    seg_len = cum[-1]
    T0, T1 = 0.45, 2.6  # the trace runs from fixation 1 (at T0) to fixation 7 (at T1)

    fix_nodes = []
    for i, (x, y, d) in enumerate(FIX):
        r = 7 + d / 22
        # each fixation lands as the trace reaches it
        delay = (0.2 if i == 0 else T0 + cum[i] / seg_len * (T1 - T0) - 0.12)
        fix_nodes.append(
            f'<g class="f" style="animation-delay:{delay:.2f}s;transform-origin:{x}px {y}px">'
            f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="{t["fix"]}" fill-opacity="{t["fix_fill_o"]}" '
            f'stroke="{t["fix"]}" stroke-width="2"/>'
            f'<path d="{mono_b.path(str(i + 1), 13, x, y + 4.6, anchor="middle")}" fill="{t["num"]}"/></g>'
        )

    css = f"""
    .f{{animation:pop .45s cubic-bezier(.2,.8,.2,1) both}}
    .s{{stroke-dasharray:{seg_len + 1:.0f};animation:draw {T1 - T0:.2f}s {T0:.2f}s linear both}}
    @keyframes pop{{from{{opacity:0;transform:scale(.4)}}to{{opacity:1;transform:scale(1)}}}}
    @keyframes draw{{from{{stroke-dashoffset:{seg_len + 1:.0f}}}to{{stroke-dashoffset:0}}}}
    @media (prefers-reduced-motion:reduce){{.f,.s{{animation:none}}}}
    """

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">Hugo Correia: HCI researcher and software engineer</title>
<style>{css}</style>
<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="{t['bg']}" stroke="{t['edge']}" stroke-opacity="{t['edge_o']}" stroke-width="1.5"/>
<path d="{grid}" stroke="{t['grid']}" stroke-opacity="{t['grid_o']}" stroke-width="3" stroke-linecap="round"/>
<path class="s" d="{sacc}" fill="none" stroke="{t['sacc']}" stroke-opacity="{t['sacc_o']}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
{''.join(fix_nodes)}
<rect x="{LX}" y="96" width="28" height="3" rx="1.5" fill="{t['rule']}"/>
<path d="{eyebrow}" transform="translate(40 0)" fill="{t['eyebrow']}"/>
<path d="{name}" fill="{t['name']}"/>
<path d="{sub}" fill="{t['sub']}" fill-opacity="{t['sub_o']}"/>
<path d="{meta}" fill="{t['meta']}" fill-opacity="{t['meta_o']}"/>
</svg>
""", name_w, sub_w


OUT.mkdir(parents=True, exist_ok=True)
for theme in THEMES:
    content, nw, sw = svg(theme)
    (OUT / f"header-{theme}.svg").write_text(content)
    print(theme, f"name_w={nw:.0f} sub_w={sw:.0f} bytes={len(content)}")
