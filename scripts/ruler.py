#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zoom a region and burn a labelled ruler into it, so pixel positions can be read off
by eye or by a vision model without guessing.

    python ruler.py shot.png 0,150,70,1500 -o toolbar.png --scale 4 --step 50
"""
import argparse
import sys

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("region", help="x0,y0,x1,y1")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--step", type=int, default=50)
    args = ap.parse_args()

    x0, y0, x1, y1 = (int(v) for v in args.region.split(","))
    im = Image.open(args.image).convert("RGB").crop((x0, y0, x1, y1))
    if args.scale != 1:
        im = im.resize((im.width * args.scale, im.height * args.scale), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    y = (y0 // args.step) * args.step
    while y <= y1:
        py = (y - y0) * args.scale
        if py >= 0:
            major = (y % (args.step * 2) == 0)
            d.line([(0, py), (im.width, py)], fill=(255, 0, 0) if major else (0, 160, 255),
                   width=2 if major else 1)
            d.text((2, py + 2), str(y), fill=(255, 0, 0))
        y += args.step
    x = (x0 // args.step) * args.step
    while x <= x1:
        px = (x - x0) * args.scale
        if px >= 0:
            d.line([(px, 0), (px, im.height)], fill=(0, 180, 0), width=1)
            d.text((px + 2, 2), str(x), fill=(0, 128, 0))
        x += args.step
    im.save(args.out)
    print("saved %s %dx%d (region %d,%d-%d,%d, scale %d)"
          % (args.out, im.width, im.height, x0, y0, x1, y1, args.scale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
