#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crop, trim and scale captures - the step between "window screenshot" and "figure".

    # fixed boxes
    python crop.py in.png out/ --box 100,100,600,400 --box 700,100,1200,400 --prefix fig

    # fixed size around centres (one figure per object)
    python crop.py in.png out/ --center 500,300 --center 900,300 --half 260x200 --prefix fig

    # auto-trim each box to its ink, then pad (great for symbols/labels)
    python crop.py in.png out/ --box ... --trim --dark 160 --pad 40 --scale 1.7

--box/--center may be repeated; they are matched 1:1 with the outputs.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image


def trim_box(im, box, dark, pad, color=None):
    x0, y0, x1, y1 = box
    a = np.array(im.crop(box)).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    if color == "blue":
        mask = (b > r + 40) & (b > g + 40)
    elif color == "green":
        mask = (g > r + 40) & (g > b + 40)
    elif color is not None:
        mask = (np.abs(r - g) + np.abs(g - b) + np.abs(r - b)) > 120
    else:
        mask = lum < dark
    ys, xs = np.nonzero(mask)
    if len(ys) < 20:
        return box, False
    return (max(0, x0 + int(xs.min()) - pad), max(0, y0 + int(ys.min()) - pad),
            min(im.width, x0 + int(xs.max()) + pad), min(im.height, y0 + int(ys.max()) + pad)), True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("outdir")
    ap.add_argument("--box", action="append", default=[], help="x0,y0,x1,y1")
    ap.add_argument("--center", action="append", default=[], help="cx,cy")
    ap.add_argument("--half", default="260x200", help="half width x half height for --center")
    ap.add_argument("--prefix", default="crop")
    ap.add_argument("--trim", action="store_true", help="shrink each box to its ink")
    ap.add_argument("--dark", type=int, default=160, help="ink threshold for --trim")
    ap.add_argument("--color", default=None, help="trim on a colour class instead of darkness")
    ap.add_argument("--pad", type=int, default=40, help="margin added back after --trim")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--clamp-right", type=int, default=None,
                    help="never crop past this x (keeps neighbouring content/scrollbars out)")
    ap.add_argument("--clamp-bottom", type=int, default=None)
    args = ap.parse_args()

    im = Image.open(args.image).convert("RGB")
    os.makedirs(args.outdir, exist_ok=True)
    hw, hh = (int(v) for v in args.half.lower().split("x"))
    boxes = []
    for spec in args.box:
        boxes.append(tuple(int(v) for v in spec.split(",")))
    for spec in args.center:
        cx, cy = (int(v) for v in spec.split(","))
        boxes.append((max(0, cx - hw), max(0, cy - hh),
                      min(im.width, cx + hw), min(im.height, cy + hh)))
    if not boxes:
        print("need at least one --box or --center", file=sys.stderr)
        return 2

    for i, box in enumerate(boxes):
        x0, y0, x1, y1 = box
        if args.clamp_right is not None:
            x1 = min(x1, args.clamp_right)
        if args.clamp_bottom is not None:
            y1 = min(y1, args.clamp_bottom)
        box = (x0, y0, x1, y1)
        if args.trim:
            box, found = trim_box(im, box, args.dark, args.pad, args.color)
            if not found:
                print("  %s: no ink in box, kept as-is" % (args.prefix + "%02d" % i))
        t = im.crop(box)
        if args.scale != 1.0:
            t = t.resize((max(1, int(t.width * args.scale)), max(1, int(t.height * args.scale))),
                         Image.LANCZOS)
        path = os.path.join(args.outdir, "%s%02d.png" % (args.prefix, i))
        t.save(path)
        print("%s  box=(%d,%d)-(%d,%d)  -> %dx%d"
              % (os.path.basename(path), box[0], box[1], box[2], box[3], t.width, t.height))
    return 0


if __name__ == "__main__":
    sys.exit(main())
