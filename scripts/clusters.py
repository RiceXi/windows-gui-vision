#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find connected ink blobs in a region and report their bounding boxes.

This is how you locate a widget without asking a vision model: pick the colour or
darkness that identifies it, then read the geometry.

    python clusters.py shot.png 0,0,800,600 [--dark 150] [--color blue] [--min-px 40]
    python clusters.py shot.png 0,0,800,600 --json
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
    "any": lambda r, g, b: (np.abs(r - g) + np.abs(g - b) + np.abs(r - b)) > 120,
}


def mask_for(a, args):
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    if args.rgb:
        target = np.array([int(v) for v in args.rgb.split(",")])
        return np.abs(a - target).sum(axis=2) <= args.tol
    if args.dark is not None:
        return lum < args.dark
    if args.light is not None:
        return lum > args.light
    if args.color in PRESETS:
        return PRESETS[args.color](r, g, b)
    return lum < 150


def label_components(mask, min_px):
    """[(x0,y0,x1,y1,pixels)] for 8-connected components with at least min_px pixels."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.nonzero(mask)
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
        if len(pts) >= min_px:
            py = [p[0] for p in pts]
            px = [p[1] for p in pts]
            out.append((min(px), min(py), max(px), max(py), len(pts)))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("region", help="x0,y0,x1,y1, or -1 for the whole image")
    ap.add_argument("--dark", type=int, default=None, help="ink = luminance below N")
    ap.add_argument("--light", type=int, default=None, help="ink = luminance above N")
    ap.add_argument("--rgb", default=None, help="ink = pixels near R,G,B")
    ap.add_argument("--tol", type=int, default=60)
    ap.add_argument("--color", default=None, help="one of: " + ", ".join(sorted(PRESETS)))
    ap.add_argument("--min-px", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    im = Image.open(args.image).convert("RGB")
    if args.region.strip() == "-1":
        x0, y0, x1, y1 = 0, 0, im.width, im.height
    else:
        x0, y0, x1, y1 = (int(v) for v in args.region.split(","))
    sub = np.array(im.crop((x0, y0, x1, y1))).astype(int)
    mask = mask_for(sub, args)
    blobs = [(a + x0, b + y0, c + x0, d + y0, n)
             for a, b, c, d, n in label_components(mask, args.min_px)]
    if args.json:
        print(json.dumps({"image": args.image, "region": [x0, y0, x1, y1],
                          "ink_px": int(mask.sum()), "blobs": blobs}, indent=1))
        return 0
    print("region %d,%d-%d,%d  ink %d px  blobs %d (min %d px)"
          % (x0, y0, x1, y1, int(mask.sum()), len(blobs), args.min_px))
    for bx0, by0, bx1, by1, n in blobs:
        print("  center=(%5d,%5d)  box=(%d,%d)-(%d,%d)  %dx%d  px=%d"
              % ((bx0 + bx1) // 2, (by0 + by1) // 2, bx0, by0, bx1, by1,
                 bx1 - bx0 + 1, by1 - by0 + 1, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
