#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate a coloured UI element (chart title bar, border, highlight) by colour.

Two modes:
  blob    - bounding boxes of coloured blobs (default)
  rowband - rows whose coloured run is wider than --min-width; use this for wide bars such
            as a graph window's title strip, then read the x extent off that row

    python colorfind.py shot.png 0,0,2800,1650 --color green --mode rowband --min-width 300
    python colorfind.py shot.png 300,150,2600,1600 --rgb 0,0,192 --tol 80 --min-px 25
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image

PRESETS = {
    "blue": lambda r, g, b: (b > r + 40) & (b > g + 40),
    "green": lambda r, g, b: (g > r + 40) & (g > b + 40),
    "red": lambda r, g, b: (r > g + 40) & (r > b + 40),
    "magenta": lambda r, g, b: (r > g + 40) & (b > g + 40),
    "yellow": lambda r, g, b: (r > b + 40) & (g > b + 40),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("region", help="x0,y0,x1,y1 or -1")
    ap.add_argument("--color", default="green", help="one of: " + ", ".join(PRESETS))
    ap.add_argument("--rgb", default=None, help="match a specific R,G,B instead of a preset")
    ap.add_argument("--tol", type=int, default=60)
    ap.add_argument("--mode", choices=["blob", "rowband"], default="blob")
    ap.add_argument("--min-px", type=int, default=60, help="blob mode: minimum blob size")
    ap.add_argument("--min-width", type=int, default=200, help="rowband mode: minimum run width")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    im = Image.open(args.image).convert("RGB")
    if args.region.strip() == "-1":
        x0, y0, x1, y1 = 0, 0, im.width, im.height
    else:
        x0, y0, x1, y1 = (int(v) for v in args.region.split(","))
    a = np.array(im.crop((x0, y0, x1, y1))).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    if args.rgb:
        target = np.array([int(v) for v in args.rgb.split(",")])
        mask = np.abs(a - target).sum(axis=2) <= args.tol
    else:
        mask = PRESETS[args.color](r, g, b)

    out = []
    if args.mode == "rowband":
        rows = mask.sum(axis=1)
        start = None
        for i, v in enumerate(rows):
            wide = v >= args.min_width
            if wide and start is None:
                start = i
            elif not wide and start is not None:
                mid = (start + i - 1) // 2
                cols = np.nonzero(mask[mid])[0]
                out.append({"y0": y0 + start, "y1": y0 + i - 1,
                            "x0": x0 + int(cols.min()), "x1": x0 + int(cols.max()),
                            "row": y0 + mid, "width": int(cols.max() - cols.min() + 1)})
                start = None
        if start is not None:
            mid = (start + len(rows) - 1) // 2
            cols = np.nonzero(mask[mid])[0]
            out.append({"y0": y0 + start, "y1": y0 + len(rows) - 1,
                        "x0": x0 + int(cols.min()), "x1": x0 + int(cols.max()),
                        "row": y0 + mid, "width": int(cols.max() - cols.min() + 1)})
    else:
        h, w = mask.shape
        seen = np.zeros_like(mask, dtype=bool)
        ys, xs = np.nonzero(mask)
        groups = {}
        for sy, sx in zip(ys.tolist(), xs.tolist()):
            if seen[sy, sx]:
                continue
            stack = [(sy, sx)]
            seen[sy, sx] = True
            pts = []
            while stack:
                cy, cx = stack.pop()
                pts.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            if len(pts) >= args.min_px:
                py = [p[0] for p in pts]
                px = [p[1] for p in pts]
                groups[(min(px), min(py), max(px), max(py))] = len(pts)
        out = [{"x0": x0 + k[0], "y0": y0 + k[1], "x1": x0 + k[2], "y1": y0 + k[3],
                "width": k[2] - k[0] + 1, "height": k[3] - k[1] + 1, "px": n}
               for k, n in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0]))]

    if args.json:
        print(json.dumps({"image": args.image, "mode": args.mode, "matches": out},
                         ensure_ascii=False, indent=1))
    else:
        print("%s  %s  matches=%d" % (args.image, args.mode, len(out)))
        for m in out:
            if args.mode == "rowband":
                print("  row y=%d  band y %d..%d  x %d..%d  width=%d"
                      % (m["row"], m["y0"], m["y1"], m["x0"], m["x1"], m["width"]))
            else:
                print("  box (%d,%d)-(%d,%d)  %dx%d  px=%d"
                      % (m["x0"], m["y0"], m["x1"], m["y1"], m["width"], m["height"], m["px"]))
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main())
