#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Derive a window's UI geometry from a capture, in the application's own pixel space.

Why this matters: an application lays itself out in *logical* pixels, so a capture taken
with PrintWindow (or the window's client rect) has the same geometry on every monitor and
every DPI setting. Only the screenshot-to-input scale changes. Calibrate once per app, save
the result, and the coordinates stay valid on other machines/resolutions.

Detected here, generically:
  * canvas    - the large uniform "work area" rectangle (rows x cols where one colour dominates)
  * toolbar   - ink bands in the narrow strip left of the canvas (one band per icon button)
  * list      - text rows in the left panel (first row centre + row pitch)
  * scale     - screenshot_width / print_width, when a second capture is supplied

    python calibrate.py --print pw.png [--screen shot.png] [--out layout.json]

Everything printed is in the coordinate space of --print.
"""
import argparse
import json
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image


def bands(profile, threshold, min_len=3, max_gap=2):
    """Group runs where profile >= threshold into (start, end) inclusive pairs."""
    out = []
    start = None
    gap = 0
    for i, v in enumerate(profile):
        if v >= threshold:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                end = i - gap
                if end - start + 1 >= min_len:
                    out.append((start, end))
                start = None
                gap = 0
    if start is not None and len(profile) - start >= min_len:
        out.append((start, len(profile) - 1))
    return out


def dominant_color(a):
    h, w, _ = a.shape
    mid = a[int(h * 0.3):int(h * 0.7), int(w * 0.3):int(w * 0.7)].reshape(-1, 3)
    step = max(1, mid.shape[0] // 20000)
    samples = [tuple(int(v) for v in row) for row in mid[::step]]
    return Counter(samples).most_common(1)[0][0]


def canvas_box(a, bg, tol=12):
    d = np.abs(a - np.array(bg)).sum(axis=2) <= tol * 3
    h, w = d.shape
    mid_rows = d[int(h * 0.35):int(h * 0.65), :]
    col_frac = mid_rows.mean(axis=0)
    mid_cols = d[:, int(w * 0.35):int(w * 0.65)]
    row_frac = mid_cols.mean(axis=1)
    cols = bands(col_frac, 0.5, min_len=20, max_gap=40)
    rows = bands(row_frac, 0.5, min_len=20, max_gap=40)
    if not cols or not rows:
        return None
    col = max(cols, key=lambda b: b[1] - b[0])
    row = max(rows, key=lambda b: b[1] - b[0])
    return (col[0], row[0], col[1], row[1])


def analyze(path, icon_dark=190, text_dark=200, toolbar_strip="auto", panel_top=0.08):
    """Return the geometry dict for one window capture. Used by calibrate.py and the
    scaling self-test."""
    im = Image.open(path).convert("RGB")
    a = np.array(im).astype(int)
    h, w, _ = a.shape
    lum = 0.3 * a[:, :, 0] + 0.59 * a[:, :, 1] + 0.11 * a[:, :, 2]
    bg = dominant_color(a)
    box = canvas_box(a, bg)

    result = {
        "source": os.path.abspath(path),
        "size": [w, h],
        "background_rgb": list(bg),
        "canvas": list(box) if box else None,
    }

    panel_x1 = box[0] if box else int(w * 0.11)

    # --- icon column -------------------------------------------------------------
    if toolbar_strip == "auto":
        # the icon column is the narrow vertical strip in the left margin with the most
        # distinct ink bands; scanning for it keeps this working across DPI and themes
        best = (0, None, None)
        width = max(12, int(w * 0.013))
        for x in range(2, max(3, int(w * 0.05))):
            prof = (lum[:, x:x + width] < icon_dark).sum(axis=1)
            cand = bands(prof, 1, min_len=3, max_gap=2)
            if len(cand) > best[0]:
                best = (len(cand), x, cand)
        _, strip_x0, strip_bands = best
        strip_x1 = (strip_x0 or 0) + width
        icon_rows = strip_bands or []
    else:
        f0, f1 = (float(v) for v in toolbar_strip.split(","))
        strip_x0 = max(1, int(w * f0))
        strip_x1 = max(strip_x0 + 4, int(w * f1))
        strip = lum[:, strip_x0:strip_x1] < icon_dark
        icon_rows = bands(strip.sum(axis=1), 1, min_len=3, max_gap=2)
    icons = [int((s + e) / 2) for s, e in icon_rows]
    result["toolbar"] = {
        "x": int((strip_x0 + strip_x1) / 2),
        "strip": [strip_x0, strip_x1],
        "buttons_y": icons,
        "pitch_y": (int(np.median(np.diff(icons))) if len(icons) > 2 else None),
    }

    # --- object/list panel text rows --------------------------------------------
    px0 = max(strip_x1 + 2, int(w * 0.03))
    px1 = max(px0 + 8, panel_x1 - int(w * 0.004))
    panel = lum[:, px0:px1] < text_dark
    row_ink = panel.sum(axis=1)
    top = int(h * panel_top)
    text_rows = [b for b in bands(row_ink, 3, min_len=4, max_gap=3) if b[0] >= top]
    centers = [int((s + e) / 2) for s, e in text_rows]
    # A list is a run of evenly spaced rows. Take the median gap, then the longest run of
    # gaps that match it - that run's first row is the list's first row, and it survives
    # toolbars / preview panes / separators sitting above or below the list.
    pitch = None
    first_list = None
    if len(centers) >= 4:
        deltas = [int(d) for d in np.diff(centers)]
        # a list row pitch is small relative to the window; the cap keeps a resampled or
        # blurry capture from reporting half the list as one "row"
        cap = max(20, int(h * 0.045))
        plausible = [d for d in deltas if 6 <= d <= cap]
        if plausible:
            pitch = int(np.median(plausible))
            best_start, best_len = 0, 0
            start, run = 0, 1
            for i, d in enumerate(deltas):
                if abs(d - pitch) <= 2:
                    run += 1
                    if run > best_len:
                        best_len, best_start = run, start
                else:
                    start, run = i + 1, 1
            if best_len >= 3:
                first_list = (centers[best_start], centers[best_start + best_len - 1])
    sep = [int(np.argmax(row_ink))] if len(row_ink) else []
    result["list"] = {
        "x": int((px0 + px1) / 2),
        "panel": [px0, px1],
        "title_separator_y": (sep[0] if sep else None),
        "first_row_y": first_list[0] if first_list else None,
        "last_row_y": first_list[1] if first_list else None,
        "pitch_y": pitch,
        "all_text_rows": [[s, e] for s, e in text_rows],
    }

    result["fractions"] = {
        "canvas": [round(v / (w if i % 2 == 0 else h), 4)
                   for i, v in enumerate(box)] if box else None,
        "toolbar_x": round(result["toolbar"]["x"] / float(w), 4),
        "list_x": round(result["list"]["x"] / float(w), 4),
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="pw", required=True, help="PrintWindow capture (logical space)")
    ap.add_argument("--screen", dest="shot", default=None, help="Computer Use screenshot of the same window")
    ap.add_argument("--out", default=None, help="write the calibration as JSON")
    ap.add_argument("--icon-dark", type=int, default=190,
                    help="luminance below which an icon pixel counts (icons are often light)")
    ap.add_argument("--text-dark", type=int, default=200,
                    help="luminance below which a list/text pixel counts")
    ap.add_argument("--toolbar-strip", default="auto",
                    help="'auto' or x0,x1 as fractions of width: the narrow icon column")
    ap.add_argument("--panel-top", type=float, default=0.08,
                    help="fraction of height where the left panel starts (below the toolbars)")
    args = ap.parse_args()

    result = analyze(args.pw, args.icon_dark, args.text_dark,
                     args.toolbar_strip, args.panel_top)
    w, h = result["size"]
    px0, px1 = result["list"]["panel"]
    box = result["canvas"]
    icons = result["toolbar"]["buttons_y"]
    if args.shot:
        shot = Image.open(args.shot)
        result["screen"] = {"source": os.path.abspath(args.shot),
                            "size": [shot.width, shot.height]}
        result["scale"] = round(shot.width / float(w), 4)

    print("capture      %dx%d   background rgb%s"
          % (w, h, tuple(result["background_rgb"])))
    print("canvas       %s   (fractions %s)" % (box, result["fractions"]["canvas"]))
    print("icon column  x=%d  %d buttons, y=%s"
          % (result["toolbar"]["x"], len(icons), icons[:24]))
    if result["toolbar"]["pitch_y"]:
        print("             pitch %d px" % result["toolbar"]["pitch_y"])
    print("list panel   x=%d..%d  title separator y=%s  first row y=%s  pitch=%s"
          % (px0, px1, result["list"]["title_separator_y"],
             result["list"]["first_row_y"], result["list"]["pitch_y"]))
    if args.shot:
        print("scale        screenshot/print = %s  (multiply logical coords by this to click)"
              % result["scale"])
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
