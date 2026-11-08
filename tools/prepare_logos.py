"""Prepare tournament logos for the React dashboard: map the supplied image files to tournaments, resize, and extract a colour theme from each logo.
Usage: python tools/prepare_logos.py <folder with the numbered source images>   ->  frontend/public/logos/*.png|webp + frontend/src/data/themes.json"""
import colorsys, json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

SRC = Path(sys.argv[1]); OUT = Path("frontend/public/logos"); OUT.mkdir(parents=True, exist_ok=True)
# edition id -> (logo file number, banner/artwork file number or None)
MAP = {"wc-2002": (4, 9), "wc-2006": (5, 8), "wc-2010": (6, 7), "wc-2014": (10, 11), "wc-2018": (12, 13), "wc-2022": (14, 15), "wc-2026": (16, 17),
       "euro-2000": (18, 19), "euro-2004": (20, 21), "euro-2008": (22, 23), "euro-2012": (24, 25), "euro-2016": (26, 27), "euro-2020": (28, 29), "euro-2024": (30, 31), "euro-2028": (32, 33),
       "copa-2001": (34, 35), "copa-2004": (36, 37), "copa-2007": (38, 39), "copa-2011": (40, 41), "copa-2015": (42, 43), "copa-2016": (44, 45), "copa-2019": (46, 47), "copa-2021": (48, 49),
       "copa-2024": (50, 51), "copa-2028": (52, None), "unl": (53, 54), "wc-2030": (55, None)}


def palette(im: Image.Image, k=6):
    a = np.asarray(im.convert("RGBA").resize((160, 160)))
    px = a[a[..., 3] > 200][:, :3].astype(float) / 255
    if len(px) < 50:
        return []
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in px])
    keep = (hsv[:, 1] > 0.28) & (hsv[:, 2] > 0.22) & (hsv[:, 2] < 0.97)                      # drop white / grey / near-black: keep the brand colours
    px = px[keep] if keep.sum() > 80 else px
    km = KMeans(k, n_init=6, random_state=0).fit(px)
    counts = np.bincount(km.labels_, minlength=k)
    out = []
    for c, n in sorted(zip(km.cluster_centers_, counts), key=lambda t: -t[1]):
        h, s, v = colorsys.rgb_to_hsv(*c)
        if all(abs(h - colorsys.rgb_to_hsv(*np.array([int(x[i:i + 2], 16) for i in (1, 3, 5)]) / 255)[0]) > 0.06 or True for x in []):
            pass
        out.append((tuple(c), n / counts.sum(), s, v))
    return out


def hexc(c): return "#%02x%02x%02x" % tuple(int(round(x * 255)) for x in c)


def lum(c):
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = c; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


themes = {}
for eid, (lg, bn) in MAP.items():
    logo = Image.open(SRC / f"{lg}.png").convert("RGBA")
    lw = logo.copy(); lw.thumbnail((720, 720)); lw.save(OUT / f"{eid}.png", optimize=True)
    banner = None
    if bn:
        b = Image.open(SRC / f"{bn}.png").convert("RGB"); b.thumbnail((1280, 800)); b.save(OUT / f"{eid}-banner.webp", quality=80); banner = f"/logos/{eid}-banner.webp"
        mean_lum = float(np.mean([lum(tuple(np.asarray(b.resize((32, 32))).reshape(-1, 3)[i] / 255)) for i in range(0, 1024, 7)]))
    else:
        mean_lum = 0.8
    cols = palette(logo)
    pri = [c for c in cols if c[2] > 0.35][:4] or cols[:4]
    primary = pri[0][0]
    second = next((c[0] for c in pri[1:] if abs(c[0][0] - primary[0]) + abs(c[0][1] - primary[1]) + abs(c[0][2] - primary[2]) > 0.45), pri[min(1, len(pri) - 1)][0])
    accent = next((c[0] for c in pri if c[0] not in (primary, second) and min(sum(abs(c[0][i] - o[i]) for i in range(3)) for o in (primary, second)) > 0.4), second)
    themes[eid] = {"logo": f"/logos/{eid}.png", "banner": banner, "palette": [hexc(c[0]) for c in cols[:6]], "primary": hexc(primary), "secondary": hexc(second), "accent": hexc(accent),
                   "bannerLuminance": round(mean_lum, 3), "logoSize": list(logo.size)}
Path("frontend/src/data/themes.auto.json").write_text(json.dumps(themes, indent=1), encoding="utf-8")
print(len(themes), "themes;", sum(1 for t in themes.values() if t["banner"]), "with banner art")
for k, t in themes.items(): print(f"{k:10s} {t['primary']} {t['secondary']} {t['accent']} bannerLum={t['bannerLuminance']}")
