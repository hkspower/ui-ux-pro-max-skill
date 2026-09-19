#!/usr/bin/env python3
"""AHMED -- the preview booklet, built rather than laid out.

WHAT THIS MAKES: `ahmed-preview.pdf`, eight pages, the thing you hand
someone at a show. Japanese-animation register -- cel tones, ink weight,
screentone, speed lines -- and every place, person and number in it written
in Arabic first and English second, because the game is Kuwait's.

WHY IT IS A SCRIPT. Every name, briefing, hit point and talent on these
pages is read out of the game's own tables at build time. A booklet typed by
hand goes stale the first time a number moves and nobody can tell by looking;
this one cannot, because there is nothing in it to go stale. If a stage is
renamed, rebuild and the page is right. The one thing written here and
nowhere else is the prose about the game itself -- the pitch, the sections'
own sentences -- which is not data and does not pretend to be.

    python3 build_preview.py                 # -> ahmed-preview.pdf
    python3 build_preview.py --png out/      # every page as a PNG, to look at
    python3 build_preview.py --html only.html

A NOTE ON THE ART DIRECTION. `../../../ahmed-fighter-ue5/CLAUDE.md` says the
Unreal build is not cartoonish and names flat cel shading and toon outlines
among the things to avoid. That rule is about the game. This is a printed
preview sheet, asked for in this style on purpose, and it does not set the
look of anything that ships inside the engine.

FONTS are fetched once from Google Fonts into `_fonts/` and embedded in the
page, so the PDF carries its own type and does not depend on the machine it
is opened on. Latin is Bebas Neue and Barlow Condensed; Arabic is Reem Kufi
and Cairo. The Japanese lines use whatever CJK face the system has.
"""

import argparse
import base64
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import figures as F                                            # noqa: E402
import levels                                                  # noqa: E402

BROWSER = os.path.normpath(os.path.join(HERE, "..", ".."))
UE5 = os.path.normpath(os.path.join(BROWSER, "..", "ahmed-fighter-ue5"))
DATA = os.path.join(UE5, "Content", "Data")
FONTDIR = os.path.join(HERE, "_fonts")

RIYADH = timezone(timedelta(hours=3))
CHROME = next((p for p in (
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome", shutil.which("chromium") or "",
    shutil.which("google-chrome") or "") if p and os.path.exists(p)), None)

W, H = 1920, 1080


# ---------------------------------------------------------------- the numbers

# Where each token of the game's scheme sits on the booklet's own print
# ladder. A token not named here is paint, and paint takes the straight
# black-point lift.
SCHEME_ROLES = {"void": "page", "screen": "panel", "deep": "panel",
                "panel": "card", "raised": "raised"}


def colours():
    """The scheme, read out of the browser build's own colours.js, and put
    through the booklet's print levels on the way in.

    Not copied. `../../assets/colors.js` is the single answer for what colour
    anything in this game is, and a press sheet that invented its own would
    be the tenth place the palette lived. But a screen palette is not a print
    palette. Measured on the finished pages, 55 to 80 per cent of every sheet
    sat below L* 6, where a press has no ink left to tell one thing from
    another, and the sheet and the figures standing on it were 0.3 of an L*
    apart -- the same disease as the visors, one layer down. `levels.to_print`
    raises the black point, pulls the white point off bare paper, and puts
    the four structural greys on rungs four and a half L* apart. The game's
    own file is untouched: the game is not printed.
    """
    src = open(os.path.join(BROWSER, "assets", "colors.js"), encoding="utf-8").read()
    want = {
        "void": r"void:\s*'([^']+)'", "screen": r"screen:\s*'([^']+)'",
        "panel": r"panel:\s*'([^']+)'", "raised": r"raised:\s*'([^']+)'",
        "deep": r"deep:\s*'([^']+)'", "bright": r"bright:\s*'([^']+)'",
        "white": r"white:\s*'([^']+)'", "sand": r"sand:\s*'([^']+)'",
        "dim": r"dim:\s*'([^']+)'", "red": r"red:\s*'([^']+)'",
        "green": r"green:\s*'([^']+)'", "gold": r"gold:\s*'([^']+)'",
        "health": r"health:\s*'([^']+)'", "critical": r"critical:\s*'([^']+)'",
        "mana": r"mana:\s*'([^']+)'", "stamina": r"stamina:\s*'([^']+)'",
        "rageFull": r"rageFull:\s*'([^']+)'",
    }
    out = {}
    for k, pat in want.items():
        m = re.search(pat, src)
        if not m:
            sys.exit(f"colors.js has no {k} -- the scheme moved; fix this script.")
        out[k] = levels.to_print(m.group(1), SCHEME_ROLES.get(k))
    return out


def stages():
    return json.load(open(os.path.join(DATA, "DT_Stages.json"), encoding="utf-8"))


def table(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------------ the type

# Arabic display is Almarai, Arabic text is Tajawal, and both are chosen for
# a reason that is not taste: they are STATIC fonts. Chromium's print path
# will not embed a variable font -- it silently falls back to whatever the
# machine has -- so Cairo and Reem Kufi, which Google now serves as one
# variable file per family, came out of the PDF as Liberation Serif while
# looking perfect in an on-screen proof. `font_css` refuses to build if a
# family ever ships one file for two weights again.
GF = {
    "Almarai": "Almarai:wght@400;700;800",
    "Tajawal": "Tajawal:wght@400;500;700;900",
    "Bebas Neue": "Bebas+Neue",
    "Barlow Condensed": "Barlow+Condensed:wght@400;500;600",
}
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")


def fetch(url):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, url],
                       capture_output=True)
    if r.returncode:
        sys.exit(f"could not fetch {url}: {r.stderr.decode().strip()}")
    return r.stdout


def font_css():
    """@font-face rules with the files embedded, cached in _fonts/.

    Embedded rather than linked so the PDF is the whole artefact: it prints
    the same on a machine that has never heard of Google Fonts.
    """
    os.makedirs(FONTDIR, exist_ok=True)
    cache = os.path.join(FONTDIR, "faces.json")
    if os.path.exists(cache):
        faces = json.load(open(cache, encoding="utf-8"))
    else:
        faces = []
        for fam, spec in GF.items():
            css = fetch(f"https://fonts.googleapis.com/css2?family={spec}"
                        "&display=block").decode()
            for blk in re.findall(r"@font-face\s*\{(.*?)\}", css, re.S):
                src = re.search(r"url\((https://[^)]+\.woff2)\)", blk)
                if not src:
                    continue
                # Arabic and Latin are all this booklet speaks; the other
                # slices Google offers would be bytes nobody reads.
                ur = re.search(r"unicode-range:\s*([^;]+);", blk)
                rng = ur.group(1).strip() if ur else ""
                if rng and not (rng.startswith("U+0600") or rng.startswith("U+0000")):
                    continue
                data = fetch(src.group(1))
                if not data.startswith(b"wOF2"):
                    sys.exit(f"{src.group(1)} did not come back as a font")
                wm = re.search(r"font-weight:\s*(\d+)", blk)
                faces.append({
                    "family": fam,
                    "weight": int(wm.group(1)) if wm else 400,
                    "range": rng,
                    "url": src.group(1),
                    "b64": base64.b64encode(data).decode(),
                })
        # A variable font serves one file for every weight. Chromium will not
        # embed one in a PDF, so catching it here is the difference between a
        # booklet and a booklet in the wrong typeface.
        seen = {}
        for f in faces:
            if f["family"] != fam:
                continue
            key = (f.get("range"), f["url"])
            if key in seen and seen[key] != f["weight"]:
                sys.exit(f"{fam} serves one file for weights {seen[key]} and "
                         f"{f['weight']} -- it is a variable font and will not "
                         f"embed. Choose a static family.")
            seen[key] = f["weight"]
        json.dump(faces, open(cache, "w", encoding="utf-8"))
    out = []
    for f in faces:
        rule = (f"@font-face{{font-family:'{f['family']}';font-style:normal;"
                f"font-weight:{f['weight']};font-display:block;"
                f"src:url(data:font/woff2;base64,{f['b64']}) format('woff2');")
        if f["range"]:
            rule += f"unicode-range:{f['range']};"
        out.append(rule + "}")
    return "".join(out)


# ------------------------------------------------------------------ the sheet

def stylesheet(C):
    return f"""
@page {{ size: {W}px {H}px; margin: 0; }}
* {{ box-sizing: border-box; -webkit-print-color-adjust: exact;
     print-color-adjust: exact; }}
html, body {{ margin: 0; padding: 0; background: {C['void']};
  /* Nothing may inherit the browser's default serif: an element that does
     prints in whatever face the machine has, and the booklet stops being
     self-contained. */
  font-family: 'Barlow Condensed', 'Tajawal', sans-serif; }}
.page {{ position: relative; width: {W}px; height: {H}px; overflow: hidden;
         background: {C['void']}; color: {C['bright']};
         break-after: page; page-break-after: always; }}
.page:last-child {{ break-after: auto; page-break-after: auto; }}
.abs {{ position: absolute; }}
/* Only a page's own backdrop is pinned to the corner. A drawing inside a
   card is ordinary content and must be allowed to sit where it is put --
   this rule used to catch those too, and every talent mark ended up in the
   top left of its card. */
.page > svg {{ position: absolute; left: 0; top: 0; }}

/* --- type. Latin is condensed and shouting; Arabic is not asked to shout
       in a face that was not drawn for it, so headings are Reem Kufi and
       running text is Cairo. */
.dsp  {{ font-family: 'Bebas Neue', 'Barlow Condensed', 'Tajawal', sans-serif;
         font-weight: 400; letter-spacing: .02em; }}
.lat  {{ font-family: 'Barlow Condensed', 'Tajawal', sans-serif; }}
.ar   {{ font-family: 'Tajawal', 'Almarai', sans-serif; direction: rtl; }}
.arh  {{ font-family: 'Almarai', 'Tajawal', sans-serif; direction: rtl;
         font-weight: 800; }}
.jp   {{ font-family: 'IPAGothic', 'Noto Sans JP', 'WenQuanYi Zen Hei', sans-serif; }}
.jpv  {{ writing-mode: vertical-rl; text-orientation: upright; }}

.kick {{ font-family: 'Barlow Condensed', 'Tajawal', sans-serif;
         font-weight: 600;
         letter-spacing: .42em; text-transform: uppercase; }}
.gold {{ color: {C['gold']}; }}
.sand {{ color: {C['sand']}; }}
.dim  {{ color: {C['dim']}; }}
.red  {{ color: {C['red']}; }}

/* --- the ink frame every interior page is printed inside */
.frame {{ position: absolute; left: 56px; top: 44px;
          width: {W - 112}px; height: {H - 88}px;
          border: 2px solid rgba(237,190,87,.22); }}
.corner {{ position: absolute; width: 34px; height: 34px;
           border: 3px solid {C['gold']}; }}

.hdr-ar {{ font-family: 'Almarai', sans-serif; font-weight: 800; direction: rtl;
           color: {C['gold']}; line-height: 1.3; }}
.hdr-en {{ font-family: 'Bebas Neue', 'Tajawal', sans-serif; line-height: .92;
           color: {C['bright']}; }}
.rule {{ position: absolute; height: 3px;
         background: linear-gradient(90deg,{C['gold']},rgba(237,190,87,0)); }}

.card {{ position: absolute; background: rgba(21,27,40,.86);
         border: 1px solid rgba(237,190,87,.20); overflow: hidden; }}
.tag  {{ font-family: 'Barlow Condensed', 'Tajawal', sans-serif;
         font-weight: 600;
         letter-spacing: .20em; text-transform: uppercase; font-size: 15px; }}
.num  {{ font-family: 'Bebas Neue', 'Tajawal', sans-serif; line-height: .8; }}

.foot {{ position: absolute; left: 96px; right: 96px; bottom: 26px;
         display: flex; justify-content: space-between; align-items: baseline;
         font-family: 'Barlow Condensed', 'Tajawal', sans-serif;
         font-size: 17px; letter-spacing: .26em; text-transform: uppercase;
         color: rgba(244,241,232,.60); }}
"""


def corners(C, x, y, w, h, s=34):
    """Four registration corners. A printed sheet says where its edges are."""
    b = f"3px solid {C['gold']}"
    return "".join([
        f'<div class="abs" style="left:{x}px;top:{y}px;width:{s}px;height:{s}px;'
        f'border-left:{b};border-top:{b}"></div>',
        f'<div class="abs" style="left:{x + w - s}px;top:{y}px;width:{s}px;height:{s}px;'
        f'border-right:{b};border-top:{b}"></div>',
        f'<div class="abs" style="left:{x}px;top:{y + h - s}px;width:{s}px;height:{s}px;'
        f'border-left:{b};border-bottom:{b}"></div>',
        f'<div class="abs" style="left:{x + w - s}px;top:{y + h - s}px;width:{s}px;'
        f'height:{s}px;border-right:{b};border-bottom:{b}"></div>',
    ])


def header(C, ar, en, n, note="", sub=""):
    """Every interior page wears the same head: Arabic first, then English.

    The page number is not up here. It lives in the foot with the rest of
    the furniture, because the one thing a heading must not do is collide
    with the Arabic line set beside it.
    """
    return f"""
<div class="abs hdr-ar" style="right:112px;top:56px;font-size:76px">{ar}</div>
<div class="abs hdr-en dsp" style="left:112px;top:82px;font-size:70px">{en}</div>
<div class="abs kick dim" style="left:116px;top:158px;font-size:16px">{note}</div>
<div class="abs ar" style="right:112px;top:176px;width:700px;font-size:22px;
     font-weight:600;color:rgba(244,241,232,.62)">{sub}</div>
<div class="rule" style="left:112px;top:200px;width:700px"></div>
"""


def foot(C, left, right, n=None):
    mid = (f'<span class="num" style="font-size:30px;color:rgba(237,190,87,.45)">'
           f'{n:02d}</span>') if n else "<span></span>"
    return (f'<div class="foot"><span>{left}</span>{mid}'
            f'<span>{right}</span></div>')


def grain(seed=1, n=520, op=0.05):
    """Film grain, as dots. A flat fill on a printed page reads as plastic."""
    out = []
    for i in range(n):
        h = math.sin((i + 1) * 12.9898 + seed * 78.233) * 43758.5453
        j1 = h - math.floor(h)
        h2 = math.sin((i + 1) * 78.233 + seed * 12.9898) * 43758.5453
        j2 = h2 - math.floor(h2)
        out.append(f'<circle cx="{j1 * W:.0f}" cy="{j2 * H:.0f}" '
                   f'r="{0.8 + 1.8 * j2:.1f}" fill="#e7e4db" opacity="{op:.3f}"/>')
    return "".join(out)


# ------------------------------------------------------------- 01 · the cover

def page_cover(C, S, stamp):
    sx, sy, sr = 1180, 430, 430
    svg = f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  {F.screentone('tone-sun', 11, 3.4, '#f4d196', 0.55, 24)}
  {F.screentone('tone-dark', 9, 2.2, '#17191b', 0.5, -12)}
  <radialGradient id="dusk" cx="62%" cy="42%" r="72%">
    <stop offset="0%" stop-color="#452e21"/>
    <stop offset="46%" stop-color="#252028"/>
    <stop offset="100%" stop-color="{C['void']}"/>
  </radialGradient>
  <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="rgba(5,7,11,0)"/>
    <stop offset="62%" stop-color="rgba(5,7,11,.72)"/>
    <stop offset="100%" stop-color="{C['void']}"/>
  </linearGradient>
  <linearGradient id="left" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="rgba(5,7,11,.94)"/>
    <stop offset="52%" stop-color="rgba(5,7,11,.72)"/>
    <stop offset="100%" stop-color="rgba(5,7,11,0)"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{H}" fill="url(#dusk)"/>
{F.speed_lines(sx, sy, sr * 1.02, 1800, n=190, seed=4, colour='#d3a362', op=0.22,
               wmin=1.0, wmax=7.0)}
<circle cx="{sx}" cy="{sy}" r="{sr}" fill="#d39741" opacity="0.92"/>
<circle cx="{sx}" cy="{sy}" r="{sr}" fill="url(#tone-sun)"/>
<circle cx="{sx}" cy="{sy}" r="{sr - 26}" fill="#e1ae56" opacity="0.55"/>
<path d="M{sx - sr},{sy + 150} a{sr},{sr} 0 0,0 {2 * sr},0 Z"
      fill="{C['void']}" opacity="0.18"/>
{F.speed_lines(sx, sy, sr * 0.42, sr * 0.98, n=70, seed=9, colour='#f2e3c3', op=0.16,
               wmin=1.0, wmax=4.0)}
{F.impact_star(944, 664, 340, points=20, inner=0.26, seed=12,
               fill='#f3daa5', op=0.30)}
{F.ahmed_cross()}
<rect x="0" y="{H - 300}" width="{W}" height="300" fill="url(#floor)"/>
<rect x="0" y="0" width="980" height="{H}" fill="url(#left)"/>
{grain(3, 460, 0.045)}
<rect x="0" y="0" width="{W}" height="{H}" fill="none"
      stroke="rgba(237,190,87,.18)" stroke-width="2"/>
</svg>"""

    flag = "".join(
        f'<div class="abs" style="left:96px;top:{150 + i * 74}px;width:16px;'
        f'height:74px;background:{c};outline:1px solid rgba(244,241,232,.12)"></div>'
        for i, c in enumerate(("#080b10", C['green'], "#e6e8eb", C['red'])))

    return f"""<section class="page">{svg}{flag}
<div class="abs kick" style="left:136px;top:152px;font-size:18px;
     color:rgba(244,241,232,.55)">SPORTA &nbsp;·&nbsp; ALMUHALLAB CODE &nbsp;·&nbsp; KUWAIT</div>
<div class="abs ar" style="left:136px;top:182px;width:520px;font-size:21px;
     font-weight:600;color:rgba(244,241,232,.55);text-align:left">
  سبورتا &nbsp;·&nbsp; شركة المهلب للبرمجة &nbsp;·&nbsp; الكويت</div>

<div class="abs arh gold" style="left:120px;top:190px;font-size:210px;
     line-height:1.32;letter-spacing:0;text-align:left;width:780px">أحمد</div>
<div class="abs dsp" style="left:132px;top:486px;font-size:186px;line-height:.82;
     color:{C['white']}">AHMED</div>
<div class="abs kick" style="left:140px;top:654px;font-size:40px;
     color:{C['sand']}">KUWAIT&nbsp;FIGHTER</div>
<div class="abs ar" style="left:140px;top:706px;width:620px;font-size:33px;
     font-weight:600;color:{C['gold']};text-align:left">مقاتل من الكويت</div>

<div class="rule" style="left:140px;top:780px;width:520px"></div>
<div class="abs ar" style="left:140px;top:812px;width:640px;font-size:28px;
     font-weight:600;line-height:1.7;color:{C['bright']};text-align:left">
  سقط في حفرة بالشارع، وخرج في الحلقة.<br>لم يبقَ معه إلا يداه.</div>
<div class="abs lat" style="left:142px;top:922px;width:640px;font-size:24px;
     line-height:1.45;color:rgba(244,241,232,.74)">
  He fell through a hole in the street and came out in AL-HALQA.
  All he brought with him was his hands.</div>

<div class="abs jp jpv" style="right:54px;top:104px;height:640px;font-size:30px;
     letter-spacing:.34em;color:rgba(244,241,232,.46)">クウェート・ファイター</div>
<div class="abs" style="right:92px;top:700px;width:150px;height:150px;
     border-radius:50%;background:{C['red']};display:flex;align-items:center;
     justify-content:center">
  <span class="jp" style="font-size:52px;color:#efece4;letter-spacing:.06em">予告</span>
</div>
<div class="abs kick" style="right:92px;top:864px;width:150px;text-align:center;
     font-size:13px;color:rgba(244,241,232,.62)">PREVIEW</div>

<div class="foot" style="left:136px;right:96px;bottom:40px">
  <span>GAME SHOW PREVIEW &nbsp;·&nbsp; معاينة</span>
  <span>UNREAL ENGINE 5 &nbsp;·&nbsp; PC &amp; CONSOLE &nbsp;·&nbsp; {stamp}</span>
</div>
</section>"""


# ---------------------------------------------------------- 02 · the fall

_PANEL_N = [0]


def panel(x, y, w, h, inner, C, edge=1.0):
    """One manga frame. Black ground, cream border, hard clip.

    The gutter between frames is the page showing through, so panels are
    placed with gaps rather than drawn with margins.
    """
    _PANEL_N[0] += 1
    pid = f"pan{_PANEL_N[0]}"
    return f"""<g>
  <clipPath id="{pid}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>
  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{C['deep']}"/>
  <g clip-path="url(#{pid})">{inner}</g>
  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none"
        stroke="{C['bright']}" stroke-width="{4 * edge}" opacity="0.92"/>
</g>"""


def page_fall(C, S, stamp):
    gold, ink, cream = C['gold'], C['void'], C['bright']

    # A -- the street, and the thing in it nobody is looking at
    ax, ay, aw, ah = 112, 232, 744, 352
    blocks = ""
    for i, (bx, bw, bh) in enumerate(((0, 120, 168), (126, 86, 226), (218, 150, 132),
                                      (374, 98, 208), (478, 132, 170), (616, 94, 244),
                                      (716, 140, 150))):
        blocks += (f'<rect x="{ax + bx}" y="{ay + 196 - bh}" width="{bw}" height="{bh}" '
                   f'fill="#050b19"/>')
        for wy in range(int(bh // 46)):
            if (i * 7 + wy * 5) % 3 == 0:
                continue
            blocks += (f'<rect x="{ax + bx + 18}" y="{ay + 208 - bh + wy * 46}" '
                       f'width="{(bw - 36) * (0.4 + 0.25 * ((i + wy) % 3)):.0f}" '
                       f'height="9" fill="{gold}" '
                       f'opacity="{0.10 + 0.06 * ((i + wy) % 3)}"/>')
    a = f"""
<rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" fill="#1c222e"/>
<rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" fill="url(#tone-b)"/>
{blocks}
<rect x="{ax}" y="{ay + 196}" width="{aw}" height="{ah - 196}" fill="#1f2228"/>
<path d="M{ax},{ay + 250} L{ax + aw},{ay + 236}" stroke="{cream}" stroke-width="3"
      opacity="0.22"/>
{"".join(f'<rect x="{ax + 30 + i * 96}" y="{ay + 296}" width="52" height="7" fill="{cream}" opacity="0.30"/>' for i in range(8))}
<ellipse cx="{ax + 470}" cy="{ay + 300}" rx="96" ry="34" fill="{ink}"/>
<ellipse cx="{ax + 470}" cy="{ay + 300}" rx="96" ry="34" fill="none"
         stroke="{gold}" stroke-width="4" opacity="0.8"/>
<ellipse cx="{ax + 470}" cy="{ay + 296}" rx="72" ry="24" fill="#000"/>
<g transform="translate({ax + 250},{ay + 300}) scale(0.30)">
  <ellipse cx="0" cy="-330" rx="44" ry="48" fill="{ink}"/>
  <path d="M-56,-262 C-20,-286 30,-286 62,-262 C78,-176 78,-84 62,-10
           C24,6 -20,6 -54,-10 C-70,-84 -70,-176 -56,-262 Z" fill="{ink}"/>
  <path d="M-54,-10 C-72,54 -80,140 -80,214 L-30,218 C-26,142 -14,72 2,26 Z" fill="{ink}"/>
  <path d="M56,-8 C78,52 90,140 92,214 L44,220 C36,146 22,78 4,30 Z" fill="{ink}"/>
  <path d="M-58,-250 C-104,-214 -134,-152 -144,-84 L-98,-70
           C-86,-132 -62,-182 -30,-214 Z" fill="{ink}"/>
  <path d="M60,-248 C104,-212 132,-150 142,-84 L96,-70
           C84,-132 60,-182 30,-212 Z" fill="{ink}"/>
  <path d="M-56,-262 C-20,-286 30,-286 62,-262" stroke="{gold}" stroke-width="10"
        fill="none" opacity="0.7"/>
</g>
{F.speed_lines(ax + 470, ay + 296, 120, 520, n=46, seed=21, colour=cream, op=0.10, wmax=4)}
"""

    # B -- the hole, looked into
    bx, by, bw, bh = 872, 232, 400, 352
    b = f"""
<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="#1f2228"/>
{F.speed_lines(bx + bw / 2, by + bh / 2, 30, 420, n=120, seed=33, colour=cream, op=0.22)}
<ellipse cx="{bx + bw / 2}" cy="{by + bh / 2}" rx="150" ry="118" fill="#000"/>
<ellipse cx="{bx + bw / 2}" cy="{by + bh / 2}" rx="150" ry="118" fill="none"
         stroke="{gold}" stroke-width="5"/>
<ellipse cx="{bx + bw / 2}" cy="{by + bh / 2}" rx="104" ry="80" fill="none"
         stroke="{gold}" stroke-width="3" opacity="0.45"/>
<ellipse cx="{bx + bw / 2}" cy="{by + bh / 2}" rx="62" ry="46" fill="none"
         stroke="{gold}" stroke-width="2" opacity="0.25"/>
"""

    # C -- going down it
    cx0, cy0, cw, ch = 1288, 232, 520, 612
    c = f"""
<rect x="{cx0}" y="{cy0}" width="{cw}" height="{ch}" fill="#17191b"/>
<ellipse cx="{cx0 + cw / 2}" cy="{cy0 + 30}" rx="150" ry="44" fill="#e1ae56" opacity="0.5"/>
<ellipse cx="{cx0 + cw / 2}" cy="{cy0 + 30}" rx="104" ry="28" fill="#f3daa5" opacity="0.7"/>
{F.rain_lines(cx0 - 40, cy0, cw + 80, ch, n=110, seed=7, colour=cream, op=0.34,
              lean=0.05, lmin=140, lmax=520)}
{F.ahmed_falling(cx0 + cw / 2 + 16, cy0 + 344, 0.70, rot=66)}
<rect x="{cx0}" y="{cy0 + ch - 150}" width="{cw}" height="150" fill="url(#fade-b)"/>
"""

    # D -- the landing
    dx, dy, dw, dh = 112, 600, 560, 340
    d = f"""
<rect x="{dx}" y="{dy}" width="{dw}" height="{dh}" fill="#251f2c"/>
<rect x="{dx}" y="{dy}" width="{dw}" height="{dh}" fill="url(#tone-b)"/>
{F.impact_star(dx + dw / 2, dy + dh - 118, 190, points=22, inner=0.22, seed=44,
               fill='#f3daa5', op=0.42)}
{F.speed_lines(dx + dw / 2, dy + dh - 96, 120, 520, n=64, seed=51, colour=cream,
               op=0.30, wmax=6, spread=3.14159, a0=3.14159)}
<ellipse cx="{dx + dw / 2}" cy="{dy + dh - 60}" rx="210" ry="40" fill="#1f2228"/>
<g transform="translate({dx + dw / 2 - 10},{dy + dh - 48}) scale(0.84)">
  <path d="M-96,0 C-84,-46 -50,-78 -8,-86 L14,-40 C-14,-30 -38,-14 -52,6 Z" fill="{ink}"/>
  <path d="M14,-108 L54,-108 L58,-70 L10,-70 Z" fill="{ink}"/>
  <ellipse cx="34" cy="-142" rx="40" ry="44" fill="{ink}"/>
  <path d="M-2,-146 C-8,-196 26,-224 62,-218 C96,-212 106,-176 100,-146
           C98,-168 84,-180 66,-182 C74,-166 70,-156 60,-150
           C54,-170 36,-180 16,-176 C2,-172 -4,-158 -2,-146 Z" fill="{ink}"/>
  <path d="M30,-216 C14,-252 -14,-258 -30,-248 C-2,-244 16,-232 26,-214 Z"
        fill="{ink}"/>
  <path d="M62,-220 C64,-256 86,-276 110,-272 C86,-260 72,-242 68,-218 Z"
        fill="{ink}"/>
  <path d="M92,-186 C120,-198 148,-186 158,-162 C136,-178 112,-180 94,-172 Z"
        fill="{ink}"/>
  <clipPath id="landface"><ellipse cx="34" cy="-142" rx="40" ry="44"/></clipPath>
  <g clip-path="url(#landface)">{F.face(34, -140, 40, 44, tone="#2f272d",
     rim=gold, iris="#e0bc63", mood="set", lit=-1, turn=0.28, catch=True)}</g>
  <path d="M-6,-92 C22,-110 66,-108 88,-88 C104,-46 106,4 96,36
           C58,50 14,48 -16,32 C-22,-8 -16,-58 -6,-92 Z" fill="{ink}"/>
  <path d="M88,-88 C132,-74 170,-40 190,4 L146,28 C130,-6 106,-32 76,-46 Z" fill="{ink}"/>
  <path d="M-16,32 C-46,42 -80,42 -108,32 L-100,64 C-64,76 -22,74 6,60 Z" fill="{ink}"/>
  <path d="M-6,-92 C22,-110 66,-108 88,-88" stroke="{gold}" stroke-width="9"
        fill="none" opacity="0.85"/>
  <path d="M96,36 C58,50 14,48 -16,32" stroke="{gold}" stroke-width="7"
        fill="none" opacity="0.5"/>
</g>
"""

    # E -- and the ring closes
    ex, ey, ew, eh = 688, 600, 584, 340
    e = f"""
<rect x="{ex}" y="{ey}" width="{ew}" height="{eh}" fill="#232029"/>
{F.speed_lines(ex + ew / 2, ey + eh, 60, 620, n=90, seed=61, colour='#e1ae56', op=0.16,
               spread=3.14159, a0=3.14159)}
{F.crowd(ex - 30, ey + eh, ew + 60, n=13, seed=17, rim=gold, h=170)}
<rect x="{ex}" y="{ey}" width="{ew}" height="{eh}" fill="url(#tone-b)" opacity="0.5"/>
"""

    return f"""<section class="page">
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
  {F.screentone('tone-b', 10, 2.4, '#e7e4db', 0.14, 30)}
  <linearGradient id="fade-b" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="rgba(5,7,11,0)"/>
    <stop offset="100%" stop-color="#17191b"/>
  </linearGradient>
</defs>
<rect width="{W}" height="{H}" fill="{C['void']}"/>
{panel(ax, ay, aw, ah, a, C)}
{panel(bx, by, bw, bh, b, C)}
{panel(cx0, cy0, cw, ch, c, C)}
{panel(dx, dy, dw, dh, d, C)}
{panel(ex, ey, ew, eh, e, C)}
{grain(9, 300, 0.035)}
</svg>
{header(C, 'الحفرة', 'THE FALL', 2, 'THE FIRST MINUTE OF THE GAME',
        'أول دقيقة في اللعبة')}

<div class="abs ar" style="left:{ax + 18}px;top:{ay + 18}px;width:400px;font-size:25px;
     font-weight:700;color:{C['bright']};text-shadow:0 2px 10px #17191b">
  يمشي. لا شيء يحدث.</div>
<div class="abs lat" style="left:{ax + 20}px;top:{ay + 56}px;width:380px;font-size:19px;
     color:rgba(244,241,232,.72)">He is walking. Nothing is happening.</div>

<div class="abs ar" style="left:{bx + 18}px;top:{by + 18}px;width:300px;font-size:25px;
     font-weight:700;color:{C['gold']}">في الشارع حفرة.</div>
<div class="abs lat" style="left:{bx + 20}px;top:{by + 56}px;width:300px;font-size:19px;
     color:rgba(244,241,232,.72)">There is a hole in the street.</div>

<div class="abs jp" style="left:{cx0 + 28}px;top:{cy0 + 26}px;font-size:58px;
     color:{C['bright']};letter-spacing:.12em;opacity:.9">ズウゥゥ</div>
<div class="abs ar" style="right:{W - cx0 - cw + 26}px;top:{cy0 + ch - 116}px;
     width:400px;font-size:27px;font-weight:700;color:{C['bright']}">
  ثم يسقط.</div>
<div class="abs lat" style="right:{W - cx0 - cw + 28}px;top:{cy0 + ch - 70}px;
     width:400px;font-size:19px;text-align:right;color:rgba(244,241,232,.72)">
  Then he goes down it.</div>

<div class="abs jp" style="left:{dx + 22}px;top:{dy + 16}px;font-size:54px;
     color:{C['gold']};letter-spacing:.08em">ドォン</div>
<div class="abs ar" style="left:{dx + 20}px;top:{dy + dh - 92}px;width:420px;
     font-size:25px;font-weight:700;color:{C['bright']}">
  يخرج في مكان لا يعرفه أحد فوق.</div>
<div class="abs lat" style="left:{dx + 22}px;top:{dy + dh - 50}px;width:460px;
     font-size:19px;color:rgba(244,241,232,.72)">
  He comes out somewhere nobody above has heard of.</div>

<div class="abs arh" style="left:{ex + 30}px;top:{ey + 22}px;font-size:96px;
     line-height:1.1;color:{C['gold']};text-shadow:0 4px 18px #17191b">الحلقة</div>
<div class="abs dsp" style="left:{ex + 32}px;top:{ey + 142}px;font-size:46px;
     color:{C['bright']}">AL-HALQA</div>
<div class="abs lat" style="left:{ex + 34}px;top:{ey + 196}px;width:520px;font-size:19px;
     line-height:1.4;color:rgba(244,241,232,.78)">
  A ring, a circle, a link in a chain, and the ring of onlookers that closes
  around a fight in a marketplace. All four meanings are the place.</div>

{foot(C, 'AHMED — KUWAIT FIGHTER', 'SPORTA · ALMUHALLAB CODE COMPANY · KUWAIT', 2)}
</section>"""


# ------------------------------------------------------------ 03 · the ring

def page_ring(C, S, stamp):
    """The map, drawn from the table that the game walks.

    Eight districts on a ring, the arena at the hub, and one door off the
    souq that leads inward rather than out. Nothing here is placed by eye:
    a district's angle is its index and the talent on each arc is the reward
    its stage's gate actually pays.
    """
    gold, cream = C['gold'], C['bright']
    cx, cy, R = 1176, 598, 238
    ring = [st for st in S if not st["bSurvival"] and not (st["Index"] == 8)]
    hub = next(st for st in S if st["Index"] == 8)
    surv = next(st for st in S if st["bSurvival"])
    tal = {t["Ability"]: t for t in table("DT_Talents.csv")}

    nodes, spokes, labels = [], [], []
    pts = []
    for i, st in enumerate(ring):
        a = math.radians(-90 + i * (360 / len(ring)))
        pts.append((cx + R * math.cos(a), cy + R * math.sin(a), a, st))

    for i, (x, y, a, st) in enumerate(pts):
        x2, y2, _, _ = pts[(i + 1) % len(pts)]
        spokes.append(f'<path d="M{x:.0f},{y:.0f} A{R},{R} 0 0,1 {x2:.0f},{y2:.0f}" '
                      f'fill="none" stroke="{gold}" stroke-width="3" opacity="0.30"/>')

    for i, (x, y, a, st) in enumerate(pts):
        boss = st["bIsBossStage"]
        nodes.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="46" fill="{C["panel"]}" '
            f'stroke="{C["red"] if boss else gold}" stroke-width="{5 if boss else 3}"/>'
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{30 + 4 * st["Tier"]}" '
            f'fill="{gold}" opacity="{0.08 + 0.05 * st["Tier"]}"/>')
        # the name sits outside the wheel, on the side it is on
        ox, oy = x + 100 * math.cos(a), y + 104 * math.sin(a)
        align = "center"
        if math.cos(a) > 0.4:
            align, ox = "left", ox - 4
        elif math.cos(a) < -0.4:
            align, ox = "right", ox + 4
        left = ox - (0 if align == "left" else (300 if align == "right" else 150))
        labels.append(
            f'<div class="abs ar" style="left:{left:.0f}px;top:{oy - 46:.0f}px;'
            f'width:300px;text-align:{align};font-size:31px;font-weight:700;'
            f'color:{gold};line-height:1.25">{st["DisplayNameArabic"]}</div>'
            f'<div class="abs lat" style="left:{left:.0f}px;top:{oy + 2:.0f}px;'
            f'width:300px;text-align:{align};font-size:19px;letter-spacing:.14em;'
            f'color:{cream}">{st["DisplayName"]}</div>'
            f'<div class="abs lat" style="left:{left:.0f}px;top:{oy + 26:.0f}px;'
            f'width:300px;text-align:{align};font-size:15px;letter-spacing:.20em;'
            f'text-transform:uppercase;color:rgba(244,241,232,.42)">'
            f'{st["Theme"]}{" · BOSS" if st["bIsBossStage"] else ""}</div>'
            f'<div class="abs num" style="left:{x - 40:.0f}px;top:{y - 20:.0f}px;'
            f'width:80px;text-align:center;font-size:44px;color:{cream}">'
            f'{st["Index"] + 1}</div>')

        # the talent this stage's own gate pays, written on the arc out of it
        reward = next((g["RewardAbility"] for g in st["Gates"]
                       if g["RewardAbility"] != "None"), None)
        if reward:
            t = tal[reward]
            am = a + math.radians(360 / len(pts) / 2)
            mx, my = cx + (R - 62) * math.cos(am), cy + (R - 62) * math.sin(am)
            labels.append(
                f'<div class="abs" style="left:{mx - 78:.0f}px;top:{my - 26:.0f}px;'
                f'width:156px;text-align:center">'
                f'<div class="ar" style="font-size:20px;font-weight:700;color:{cream}">'
                f'{t["DisplayNameArabic"]}</div>'
                f'<div class="lat" style="font-size:14px;letter-spacing:.18em;'
                f'color:{gold}">{t["DisplayName"]}</div></div>')

    # the one link that is not a street
    sx, sy, _, _ = pts[0]
    hawk = tal["HawkFist"]
    door = (f'<path d="M{sx:.0f},{sy + 46:.0f} L{cx},{cy - 128}" stroke="{C["rageFull"]}" '
            f'stroke-width="5" stroke-dasharray="14 10" opacity="0.9"/>')

    svg = f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>{F.screentone('tone-r', 12, 2.6, '#e5b750', 0.16, 16)}
  <radialGradient id="hubglow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="rgba(224,92,240,.34)"/>
    <stop offset="100%" stop-color="rgba(224,92,240,0)"/>
  </radialGradient></defs>
<rect width="{W}" height="{H}" fill="{C['void']}"/>
<circle cx="{cx}" cy="{cy}" r="{R + 120}" fill="url(#tone-r)" opacity="0.5"/>
<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{gold}" stroke-width="2"
        opacity="0.22"/>
<circle cx="{cx}" cy="{cy}" r="230" fill="url(#hubglow)"/>
{''.join(spokes)}{door}
<circle cx="{cx}" cy="{cy}" r="128" fill="{C['panel']}" stroke="{C['rageFull']}"
        stroke-width="5"/>
<circle cx="{cx}" cy="{cy}" r="104" fill="none" stroke="{C['rageFull']}"
        stroke-width="2" opacity="0.4"/>
{''.join(nodes)}
{grain(15, 260, 0.03)}
</svg>"""

    return f"""<section class="page">{svg}
{header(C, 'الحلقة', 'THE RING', 3, 'NINE PLACES, AND THE ONE IN THE MIDDLE',
        'تسعة أماكن، والتاسع في المنتصف')}
{''.join(labels)}
<div class="abs arh" style="left:{cx - 150}px;top:{cy - 92}px;width:300px;
     text-align:center;font-size:52px;color:{C['rageFull']};line-height:1.2">
  {hub['DisplayNameArabic']}</div>
<div class="abs dsp" style="left:{cx - 150}px;top:{cy - 8}px;width:300px;
     text-align:center;font-size:36px;color:{cream}">{hub['DisplayName']}</div>
<div class="abs kick" style="left:{cx - 150}px;top:{cy + 40}px;width:300px;
     text-align:center;font-size:14px;color:rgba(244,241,232,.52)">THE ARENA · BOSS</div>

<div class="abs" style="right:112px;top:236px;width:330px;text-align:right">
  <div style="border-top:4px dashed {C['rageFull']};width:120px;margin-left:auto;
       margin-bottom:10px"></div>
  <div class="ar" style="font-size:23px;font-weight:700;color:{C['rageFull']}">
    الباب — {hawk['DisplayNameArabic']}</div>
  <div class="lat" style="font-size:15px;letter-spacing:.18em;
       color:rgba(244,241,232,.70)">THE DOOR · {hawk['DisplayName']}</div></div>

<div class="card" style="left:112px;top:238px;width:400px;height:284px;padding:26px">
  <div class="tag gold">THE ARGUMENT</div>
  <div class="ar" style="margin-top:12px;font-size:23px;font-weight:700;
       line-height:1.62;color:{cream}">
    حلقة مغلقة. كل طريق فيها يعود إلى السوق، والباب الوحيد الذي ليس شارعًا
    يقود إلى المنتصف.</div>
  <div class="lat" style="margin-top:12px;font-size:17px;line-height:1.40;
       color:rgba(244,241,232,.70)">
    A closed loop. Every way through it comes back to the souq, and the only
    link that is not a street leads inward.</div>
</div>

<div class="card" style="left:112px;top:544px;width:400px;height:228px;padding:26px">
  <div class="tag gold">BEYOND THE STORY</div>
  <div class="ar" style="margin-top:12px;font-size:28px;font-weight:700;color:{gold}">
    {surv['DisplayNameArabic']}</div>
  <div class="lat" style="font-size:19px;letter-spacing:.16em;color:{cream}">
    {surv['DisplayName']} · SURVIVAL</div>
  <div class="ar" style="margin-top:12px;font-size:21px;font-weight:600;
       line-height:1.6;color:rgba(244,241,232,.80)">{surv['BriefingArabic']}</div>
  <div class="lat" style="margin-top:8px;font-size:17px;line-height:1.4;
       color:rgba(244,241,232,.62)">{surv['Briefing']}</div>
</div>

<div class="card" style="left:112px;top:794px;width:400px;height:228px;padding:26px">
  <div class="tag gold">HOW A WAY OPENS</div>
  <div class="ar" style="margin-top:10px;font-size:22px;font-weight:600;
       line-height:1.65;color:rgba(244,241,232,.84)">
    كل طريق مغلق حتى يتعلّم أحمد ما يفتحه، وما يفتحه يقع دائمًا خلف قتال.</div>
  <div class="lat" style="margin-top:10px;font-size:17px;line-height:1.42;
       color:rgba(244,241,232,.62)">
    Every link is sealed until Ahmed learns the thing that opens it, and the
    thing that opens it is always behind a fight.</div>
</div>
{foot(C, 'AL-HALQA — THE RING', 'EIGHT DISTRICTS · ONE ARENA · ONE DOOR', 3)}
</section>"""


# --------------------------------------------------- 04 & 05 · the districts

def district_card(C, st, x, y, w, h, tal, gates):
    gold, cream = C['gold'], C['bright']
    boss, survival = st["bIsBossStage"], st["bSurvival"]
    edge = C['rageFull'] if survival else (C['red'] if boss else "rgba(237,190,87,.24)")
    waves = len(st["Waves"])
    foes = sum(len(wv["Fighters"]) for wv in st["Waves"])
    metres = st["Length"] * 0.024                       # 1 px = 2.4 cm, always
    gate = st["Gates"][0] if st["Gates"] else None
    reward = next((g["RewardAbility"] for g in st["Gates"]
                   if g["RewardAbility"] != "None"), None)

    vh = 296
    rows = [("WAVES", waves), ("FIGHTERS", foes), ("WALK", f"{metres:.0f} m")]
    stat = "".join(
        f'<div style="flex:1"><div class="num gold" style="font-size:30px">{v}</div>'
        f'<div class="tag" style="font-size:11px;letter-spacing:.14em;'
        f'color:rgba(244,241,232,.45)">{k}</div></div>' for k, v in rows)

    if reward:
        t = tal[reward]
        pay = (f'<div class="ar" style="font-size:19px;font-weight:700;color:{gold}">'
               f'{t["DisplayNameArabic"]}</div>'
               f'<div class="lat" style="font-size:14px;letter-spacing:.16em;'
               f'color:{cream}">{t["DisplayName"]}</div>')
        paykick = "TALENT FOUND HERE"
    elif gate:
        gk = gates[gate["Type"]]
        pay = (f'<div class="ar" style="font-size:19px;font-weight:700;'
               f'color:rgba(244,241,232,.80)">{gk["DisplayNameArabic"]}</div>'
               f'<div class="lat" style="font-size:14px;letter-spacing:.16em;'
               f'color:rgba(244,241,232,.60)">{gk["DisplayName"]} · '
               f'{gate["RewardExperience"]} XP</div>')
        paykick = "WHAT IS IN THE WAY"
    else:
        pay = (f'<div class="ar" style="font-size:19px;font-weight:700;'
               f'color:rgba(244,241,232,.80)">لا بوابات</div>'
               f'<div class="lat" style="font-size:14px;letter-spacing:.16em;'
               f'color:rgba(244,241,232,.60)">NO GATES</div>')
        paykick = "WHAT IS IN THE WAY"

    badge = ""
    if boss:
        badge = (f'<div class="abs tag" style="right:18px;top:{vh - 34}px;'
                 f'background:{C["red"]};color:#efece4;padding:5px 12px">BOSS</div>')
    elif survival:
        badge = (f'<div class="abs tag" style="right:18px;top:{vh - 34}px;'
                 f'background:{C["rageFull"]};color:#2a1d2f;padding:5px 12px">'
                 f'ENDLESS</div>')

    tier = "".join(
        f'<span style="display:inline-block;width:14px;height:5px;margin-right:4px;'
        f'background:{gold if i <= st["Tier"] else "rgba(244,241,232,.16)"}"></span>'
        for i in range(5))

    return f"""
<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;
     border-color:{edge};border-width:{2 if (boss or survival) else 1}px">
  <svg width="{w}" height="{vh}" style="position:absolute;left:0;top:0">
    {F.vignette(st["Theme"], 0, 0, w, vh, gold=gold, ink=C['void'], cream=cream)}
    <rect x="0" y="{vh - 62}" width="{w}" height="62"
          fill="url(#cardfade)"/>
  </svg>
  <div class="abs num" style="left:18px;top:12px;font-size:62px;
       color:rgba(244,241,232,.90);text-shadow:0 3px 12px #17191b">
       {st["Index"] + 1:02d}</div>
  {badge}
  <div class="abs" style="left:20px;right:20px;top:{vh + 14}px">
    <div class="ar" style="font-size:30px;font-weight:700;color:{gold};
         line-height:1.3">{st["DisplayNameArabic"]}</div>
    <div class="lat" style="font-size:19px;letter-spacing:.14em;color:{cream};
         margin-top:2px">{st["DisplayName"]}</div>
    <div style="margin-top:8px">{tier}
      <span class="tag" style="margin-left:8px;color:rgba(244,241,232,.50)">
        {st["Theme"]}</span></div>
    <div class="ar" style="margin-top:14px;font-size:20px;font-weight:600;
         line-height:1.66;color:rgba(244,241,232,.92)">{st["BriefingArabic"]}</div>
    <div class="lat" style="margin-top:10px;font-size:16px;line-height:1.40;
         color:rgba(244,241,232,.66)">{st["Briefing"]}</div>
  </div>
  <div class="abs" style="left:20px;right:20px;bottom:104px;display:flex;
       text-align:left">{stat}</div>
  <div class="abs" style="left:20px;right:20px;bottom:18px;
       border-top:1px solid rgba(237,190,87,.22);padding-top:10px">
    <div class="tag" style="font-size:11px;letter-spacing:.16em;
         color:rgba(244,241,232,.40)">{paykick}</div>
    <div style="margin-top:4px">{pay}</div>
  </div>
</div>"""


def page_districts(C, S, stamp, half, n):
    tal = {t["Ability"]: t for t in table("DT_Talents.csv")}
    gates = {g["GateType"]: g for g in table("DT_GateKinds.csv")}
    here = S[:5] if half == 0 else S[5:]
    x0, y0, cw, ch, gap = 112, 236, 320, 748, 24
    cards = "".join(district_card(C, st, x0 + i * (cw + gap), y0, cw, ch, tal, gates)
                    for i, st in enumerate(here))
    ar = 'الأماكن' if half == 0 else 'الأماكن'
    sub = ('من السوق إلى الهلال' if half == 0
           else 'من جزيرة الحجر إلى ما لا ينتهي')
    note = ('SOUQ AL-DAWAR TO AL-HILAL' if half == 0
            else 'JAZIRAT AL-HAJAR TO WHAT DOES NOT END')
    return f"""<section class="page">
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><linearGradient id="cardfade" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0%" stop-color="rgba(21,27,40,0)"/>
  <stop offset="100%" stop-color="rgba(21,27,40,.96)"/>
</linearGradient>{F.screentone('tone-d', 13, 2.2, '#e5b750', 0.10, 40)}</defs>
<rect width="{W}" height="{H}" fill="{C['void']}"/>
<rect width="{W}" height="{H}" fill="url(#tone-d)" opacity="0.5"/>
{grain(20 + n, 240, 0.03)}
</svg>
{header(C, ar, 'THE PLACES', n, note, sub)}
{cards}
{foot(C, 'AHMED — KUWAIT FIGHTER',
      'EVERY NAME, LINE AND NUMBER READ FROM THE GAME&#39;S OWN TABLES', n)}
</section>"""


# ------------------------------------------------------------- 06 · the cast

# The three bosses' lines are the story file's own sentences about them,
# given in Arabic as well because this booklet is read in Arabic first.
# Nothing here is invented: the names, the Arabic names, the hit points and
# the move lists all come out of DT_Fighters.csv.
BOSS_LINES = {
    "Saqr": ("كل شيء فيه سيقان، ولا صبر عنده. سقط هو أيضًا قبل سنوات، وكفّ عن "
             "السؤال — وهذا مصدر نفاد صبره. هو ما سيصيره أحمد بعد سنة، ويقول "
             "له ذلك، ولا يصل.",
             "All legs, no patience. He fell too, years back, and gave up asking "
             "about it — which is where the impatience comes from. He is what "
             "Ahmed becomes in a year, and he says so, and it does not land."),
    "Boss": ("بطل الحلقة، وأطولهم بقاءً فيها. ليس وحشًا؛ هو صورة البقاء حين "
             "تتقنه. هزيمته ليست هزيمة له، بل حلولٌ محله.",
             "Champion of the Halqa, and the one who has been down here longest. "
             "He is not a monster; he is what staying looks like when you are "
             "very good at it. Beating him is not defeating him. It is "
             "replacing him."),
    "Zayos": ("وحش ملاكمة: قفازان، وجسد أكبر بمرة ونصف من أي رجل في الحلقة، "
              "ذراعان طويلتان، بطيء. لا يفعل شيئًا غير اللكم.",
              "A boxing monster — gloves, a body half again the size of any man "
              "in the Halqa, long arms, slow. He only punches."),
}
BOSS_ART = {"Zayos": ("zayos", "#f99537", "#35291b"),
            "Saqr": ("saqr", "#53b1fa", "#192f3b"),
            "Boss": ("wahsh", "#de5aee", "#361b3c")}


def page_cast(C, S, stamp):
    gold, cream = C['gold'], C['bright']
    fighters = table("DT_Fighters.csv")
    by = {f["Name"]: f for f in fighters}
    order = ["Zayos", "Saqr", "Boss"]
    plates = []
    px0, pw, pgap = 112, 544, 30
    for i, key in enumerate(order):
        f = by[key]
        fn, glow, wash = BOSS_ART[key]
        ar, en = BOSS_LINES[key]
        x = px0 + i * (pw + pgap)
        art = {"wahsh": F.wahsh, "saqr": F.saqr, "zayos": F.zayos}[fn]
        inner = (art(pw / 2, 86, 0.52) if fn != "saqr"
                 else art(pw / 2 + 78, 356, 0.62))
        moves = f["Moves"].replace('"', "").strip("()").split(",")
        plates.append(f"""
<div class="card" style="left:{x}px;top:232px;width:{pw}px;height:600px;
     border-color:{glow};border-width:2px;background:{wash}">
  <svg width="{pw}" height="352" style="position:absolute;left:0;top:0">
    <defs><radialGradient id="pg{i}" cx="50%" cy="46%" r="54%">
      <stop offset="0%" stop-color="{glow}" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="{glow}" stop-opacity="0"/>
    </radialGradient></defs>
    <rect width="{pw}" height="352" fill="{C['void']}" opacity="0.55"/>
    <circle cx="{pw / 2}" cy="180" r="176" fill="url(#pg{i})"/>
    {F.speed_lines(pw / 2, 180, 176, 420, n=64, seed=70 + i, colour=glow, op=0.14)}
    {inner}
    <rect x="0" y="266" width="{pw}" height="86" fill="url(#castfade)"/>
  </svg>
  <div class="abs" style="left:24px;right:24px;top:296px">
    <div class="arh" style="font-size:52px;line-height:1.24;color:{glow}">
      {f["DisplayNameArabic"]}</div>
    <div class="dsp" style="font-size:38px;color:{cream};line-height:1">
      {f["DisplayName"]}</div>
    <div style="margin-top:14px;display:flex;gap:26px;align-items:baseline">
      <div><span class="num" style="font-size:34px;color:{gold}">
        {f["MaxHealth"]}</span>
        <span class="tag" style="color:rgba(244,241,232,.45);margin-left:6px">HP</span>
      </div>
      <div class="tag" style="color:rgba(244,241,232,.55)">
        {len(moves)} MOVES · {f["ExperienceValue"]} XP</div>
    </div>
    <div class="ar" style="margin-top:12px;font-size:18px;font-weight:600;
         line-height:1.62;color:rgba(244,241,232,.92)">{ar}</div>
  </div>
</div>
<div class="abs lat" style="left:{x + 24}px;top:848px;width:{pw - 48}px;
     font-size:17px;line-height:1.44;color:rgba(244,241,232,.64)">{en}</div>""")

    # the rest of the house, in the order the table lists them
    rest = [f for f in fighters if f["bIsBoss"] == "false" and f["Name"] != "Ahmed"]
    rw = (1696 - 8 * 14) / 9
    roster = "".join(f"""
<div class="abs" style="left:{112 + i * (rw + 14):.0f}px;top:928px;width:{rw:.0f}px;
     height:84px;border-top:2px solid rgba(237,190,87,.30);padding-top:10px">
  <div class="ar" style="font-size:23px;font-weight:700;color:{gold}">
    {f["DisplayNameArabic"]}</div>
  <div class="lat" style="font-size:15px;letter-spacing:.12em;
       color:rgba(244,241,232,.72)">{f["DisplayName"]}</div>
  <div class="num" style="font-size:22px;color:rgba(244,241,232,.50);margin-top:4px">
    {f["MaxHealth"]} <span class="tag" style="font-size:10px">HP</span></div>
</div>""" for i, f in enumerate(rest))

    return f"""<section class="page">
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><linearGradient id="castfade" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0%" stop-color="rgba(5,7,11,0)"/>
  <stop offset="100%" stop-color="rgba(5,7,11,.92)"/>
</linearGradient></defs>
<rect width="{W}" height="{H}" fill="{C['void']}"/>
{grain(31, 240, 0.03)}
</svg>
{header(C, 'الخصوم', 'THE HOUSE', 6, 'THREE TITLE FIGHTS, AND EVERYONE ELSE',
        'ثلاث نزالات لقب، ومن دونهم')}
{''.join(plates)}
{roster}
{foot(C, 'AHMED — KUWAIT FIGHTER', 'HIT POINTS AND MOVE LISTS FROM DT_FIGHTERS', 6)}
</section>"""


# ----------------------------------------------------------- 07 · the ladder

SYSTEMS = [
    ("المواهب", "TALENTS", "تُوجد، ولا تُشترى",
     "ما تعلّمه الحلقة إياه، قتالًا لكل درجة. كل موهبة تفتح البوابة التي "
     "تمنحه التالية، وآخرها يفتح الحلبة. هو يقرؤها طريقًا للخروج. وهي تفصيل "
     "على مقاسه.",
     "What the Halqa teaches him, one fight per rung. Each opens the gate "
     "that yields the next, and the last one opens the arena. He reads them "
     "as a way out. They are a fitting."),
    ("المستويات", "LEVELS", "تُكتسب بالقتال",
     "سلّم الحلقة نفسه، وما تقدّمه له بدل الباب. كل رتبة هي قول المكان له "
     "إنه صار أحدًا هنا.",
     "The Halqa's own ladder, and what it offers instead of a door. Every "
     "rank is the place telling him he is somebody here."),
    ("الترقيات", "UPGRADES", "تُشترى بالخبرة",
     "اختياره أيّ مقاتل يصير هنا. لا يلزمه أن يعيد بناء الرجل الذي كانه، "
     "وفي النهاية لم يفعل.",
     "Him choosing what kind of fighter he becomes here. He does not have to "
     "rebuild the man he was, and by the end he has not."),
]


def page_ladder(C, S, stamp):
    gold, cream = C['gold'], C['bright']
    tal = table("DT_Talents.csv")
    lv = table("DT_Levels.csv")
    ranks, seen = [], set()
    for r in lv:
        if r["Title"] not in seen:
            seen.add(r["Title"])
            ranks.append((r["Title"], int(r["Level"])))

    tw, tgap = 316, 29
    cards = []
    for i, t in enumerate(tal):
        turn = t["Name"] == "HawkFist"
        x = 112 + i * (tw + tgap)
        accent = C['mana'] if turn else gold
        cards.append(f"""
<div class="card" style="left:{x}px;top:242px;width:{tw}px;height:306px;
     border-color:{accent};border-width:{2 if turn else 1}px;
     background:{'rgba(42,26,10,.80)' if turn else 'rgba(21,27,40,.86)'}">
  <div class="abs" style="left:0;right:0;top:24px;text-align:center">
    {F.talent_mark(t["Name"], colour=accent, size=68)}</div>
  <div class="abs" style="left:20px;right:20px;top:112px;text-align:center">
    <div class="ar" style="font-size:31px;font-weight:700;color:{accent};
         line-height:1.3">{t["DisplayNameArabic"]}</div>
    <div class="lat" style="font-size:19px;letter-spacing:.16em;color:{cream};
         margin-top:2px">{t["DisplayName"]}</div>
    <div class="lat" style="margin-top:14px;font-size:16px;line-height:1.42;
         color:rgba(244,241,232,.70)">{t["Description"]}</div>
  </div>
  <div class="abs tag" style="left:20px;bottom:18px;
       color:rgba(244,241,232,.42)">RUNG {i + 1}</div>
  <div class="abs tag" style="right:20px;bottom:18px;color:{accent}">
    {'THE TURN' if turn else ('FREE' if t["ManaCost"] == '0' else t["ManaCost"] + ' MP')}
  </div>
</div>""")

    step = (1696 - 40) / (len(ranks) - 1)
    rung = "".join(f"""
<div class="abs" style="left:{112 + i * step:.0f}px;top:616px;width:{step:.0f}px">
  <div style="width:18px;height:18px;border-radius:50%;background:{gold};
       opacity:{0.35 + 0.13 * i}"></div>
  <div class="dsp" style="margin-top:12px;font-size:30px;color:{cream}">{name}</div>
  <div class="tag" style="color:rgba(244,241,232,.42)">LEVEL {lvl}</div>
</div>""" for i, (name, lvl) in enumerate(ranks))

    sw = (1696 - 2 * 30) / 3
    sys_cards = "".join(f"""
<div class="card" style="left:{112 + i * (sw + 30):.0f}px;top:706px;width:{sw:.0f}px;
     height:316px;padding:26px">
  <div class="ar" style="font-size:32px;font-weight:700;color:{gold}">{ar}</div>
  <div class="lat" style="font-size:19px;letter-spacing:.18em;color:{cream}">
    {en} · <span style="color:rgba(244,241,232,.52)">{how}</span></div>
  <div class="ar" style="margin-top:12px;font-size:19px;font-weight:600;
       line-height:1.62;color:rgba(244,241,232,.88)">{arb}</div>
  <div class="lat" style="margin-top:10px;font-size:16px;line-height:1.38;
       color:rgba(244,241,232,.62)">{enb}</div>
</div>""" for i, (ar, en, how, arb, enb) in enumerate(SYSTEMS))

    return f"""<section class="page">
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="{W}" height="{H}" fill="{C['void']}"/>
<path d="M112,{625} L{112 + 1656},{625}" stroke="{gold}" stroke-width="3"
      opacity="0.30"/>
{grain(37, 240, 0.03)}
</svg>
{header(C, 'السلّم', 'THE LADDER', 7,
        'THE PROGRESSION IS NOT A SYSTEM BOLTED ON. IT IS THE PLOT.',
        'التقدّم ليس نظامًا مضافًا إلى الحكاية — هو الحكاية')}
{''.join(cards)}
<div class="abs tag gold" style="left:112px;top:576px">THE RANK LADDER ·
  سلّم الرتب</div>
{rung}
{sys_cards}
{foot(C, 'AHMED — KUWAIT FIGHTER',
      'FIVE TALENTS · SIX RANKS · XP SPENT ON WHO HE BECOMES', 7)}
</section>"""


# ------------------------------------------------------------- 08 · the back

def page_back(C, S, stamp):
    gold, cream = C['gold'], C['bright']
    facts = [
        ("الحكاية", "STORY", "عشرة أماكن · تسعة على الحلقة وواحد في المنتصف",
         "Ten places · nine on the ring and one at the hub"),
        ("المحرّك", "ENGINE", "أنريل إنجن 5 من إيبك",
         "Epic's Unreal Engine 5"),
        ("المنصّات", "PLATFORM", "حاسب ومنصّات — لا هاتف",
         "PC and console — not a phone game"),
        ("اللغة", "LANGUAGE", "عربي وإنجليزي في كل جدول",
         "Arabic and English in every table"),
    ]
    rows = "".join(f"""
<div class="abs" style="left:{112 + i * 424}px;top:640px;width:396px;
     border-top:2px solid rgba(237,190,87,.30);padding-top:14px">
  <div class="tag gold">{en}</div>
  <div class="ar" style="margin-top:8px;font-size:25px;font-weight:700;
       color:{cream}">{ar}</div>
  <div class="ar" style="margin-top:8px;font-size:19px;font-weight:600;
       line-height:1.6;color:rgba(244,241,232,.82)">{arb}</div>
  <div class="lat" style="margin-top:6px;font-size:16px;line-height:1.4;
       color:rgba(244,241,232,.58)">{enb}</div>
</div>""" for i, (ar, en, arb, enb) in enumerate(facts))

    return f"""<section class="page">
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>{F.screentone('tone-k', 12, 2.6, '#e5b750', 0.14, 22)}
  <radialGradient id="back" cx="50%" cy="34%" r="66%">
    <stop offset="0%" stop-color="#2f251d"/>
    <stop offset="100%" stop-color="{C['void']}"/>
  </radialGradient></defs>
<rect width="{W}" height="{H}" fill="url(#back)"/>
<circle cx="{W / 2}" cy="330" r="250" fill="#d39741" opacity="0.14"/>
<circle cx="{W / 2}" cy="330" r="250" fill="url(#tone-k)"/>
{F.speed_lines(W / 2, 330, 252, 1200, n=150, seed=8, colour='#d3a362', op=0.13)}
{F.crowd(-40, H - 40, W + 80, n=34, seed=29, rim=gold, op=0.85, h=110)}
{grain(41, 320, 0.04)}
</svg>
<div class="abs arh gold" style="left:0;right:0;top:160px;text-align:center;
     font-size:176px;line-height:1.34;direction:rtl">أحمد</div>
<div class="abs dsp" style="left:0;right:0;top:428px;text-align:center;
     font-size:96px;color:{C['white']};line-height:1">AHMED</div>
<div class="abs kick" style="left:0;right:0;top:536px;text-align:center;
     font-size:26px;color:{C['sand']}">KUWAIT FIGHTER &nbsp;·&nbsp;
     <span class="ar" style="display:inline">مقاتل من الكويت</span></div>
{rows}
<div class="abs" style="left:0;right:0;top:848px;text-align:center">
  <div class="ar" style="font-size:30px;font-weight:700;color:{cream}">
    سبورتا &nbsp;·&nbsp; شركة المهلب للبرمجة &nbsp;·&nbsp; الكويت</div>
  <div class="kick" style="margin-top:10px;font-size:20px;
       color:rgba(244,241,232,.66)">
    SPORTA &nbsp;·&nbsp; ALMUHALLAB CODE COMPANY &nbsp;·&nbsp; KUWAIT</div>
</div>
<div class="abs jp" style="left:0;right:0;top:944px;text-align:center;
     font-size:22px;letter-spacing:.44em;color:rgba(244,241,232,.34)">
  アハメド・クウェート・ファイター</div>
{foot(C, 'GAME SHOW PREVIEW &nbsp;·&nbsp; معاينة', stamp + ' · RIYADH TIME (UTC+3)', 8)}
</section>"""


# -------------------------------------------------------------------- the run

def document(C, S, pages, stamp):
    return f"""<!DOCTYPE html>
<html lang="ar" dir="ltr"><head><meta charset="utf-8">
<title>AHMED — Kuwait Fighter · معاينة</title>
<style>{font_css()}{stylesheet(C)}</style></head>
<body>{''.join(pages)}</body></html>"""


def render(html, out_pdf, pngs=None):
    if not CHROME:
        sys.exit("no chromium on this machine; cannot print the booklet.")
    tmp = tempfile.mkdtemp(prefix="ahmed-preview-")
    src = os.path.join(tmp, "booklet.html")
    open(src, "w", encoding="utf-8").write(html)
    base = ["--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
            "--hide-scrollbars", "--force-device-scale-factor=1",
            "--virtual-time-budget=20000", "--font-render-hinting=none"]
    if out_pdf:
        r = subprocess.run([CHROME] + base + ["--no-pdf-header-footer",
                           f"--print-to-pdf={out_pdf}", f"file://{src}"],
                           capture_output=True)
        if not os.path.exists(out_pdf):
            sys.exit("chromium printed nothing:\n" + r.stderr.decode()[-2000:])
        print(f"{out_pdf}  {os.path.getsize(out_pdf) / 1024:.0f} KB")
        blob = open(out_pdf, "rb").read()
        used = sorted({m.decode().split("+")[-1] for m in
                       re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-]+)", blob)})
        ours = ("Almarai", "Tajawal", "BebasNeue", "BarlowCondensed", "IPAGothic")
        stray = [u for u in used if not u.startswith(ours)]
        print("  fonts: " + ", ".join(used))
        if stray:
            print("  WARNING: not embedded from this booklet's own type -- "
                  + ", ".join(stray) + ". Something fell back to the machine's "
                  "fonts and will print differently elsewhere.")
    if pngs:
        os.makedirs(pngs, exist_ok=True)
        body = html[html.index("<body>") + 6:html.rindex("</body>")]
        parts = [p for p in body.split("<section class=\"page\">") if p.strip()]
        head = html[:html.index("<body>") + 6]
        for i, p in enumerate(parts, 1):
            one = head + '<section class="page">' + p + "</body></html>"
            f1 = os.path.join(tmp, f"p{i}.html")
            open(f1, "w", encoding="utf-8").write(one)
            png = os.path.join(pngs, f"page-{i:02d}.png")
            subprocess.run([CHROME] + base + [f"--window-size={W},{H + 140}",
                           f"--screenshot={png}", f"file://{f1}"],
                           capture_output=True)
            print("  " + png)
    return tmp


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdf", default=os.path.join(HERE, "..", "ahmed-preview.pdf"))
    ap.add_argument("--png", default=None, help="also write every page as a PNG")
    ap.add_argument("--html", default=None, help="keep the intermediate page")
    a = ap.parse_args()

    C = colours()
    S = stages()
    stamp = datetime.now(RIYADH).strftime("%d %b %Y").upper()

    pages = [
        page_cover(C, S, stamp),
        page_fall(C, S, stamp),
        page_ring(C, S, stamp),
        page_districts(C, S, stamp, 0, 4),
        page_districts(C, S, stamp, 1, 5),
        page_cast(C, S, stamp),
        page_ladder(C, S, stamp),
        page_back(C, S, stamp),
    ]
    html = document(C, S, pages, stamp)
    if a.html:
        open(a.html, "w", encoding="utf-8").write(html)
        print(a.html)
    render(html, os.path.abspath(a.pdf) if a.pdf else None, a.png)


if __name__ == "__main__":
    main()
