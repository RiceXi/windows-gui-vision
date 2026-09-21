#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stack or tile several images into one picture, each tagged with its file name.

Cheap way to ask one vision question about N crops instead of N questions.

    python montage.py out.png a.png b.png c.png --labels
    python montage.py out.png *.png --grid 3 --scale 0.5
"""
import argparse
import math
import os
import sys

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--grid", type=int, default=0, help="columns; 0 = vertical stack")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--labels", action="store_true", help="draw the file name on each tile")
    ap.add_argument("--gap", type=int, default=6)
    args = ap.parse_args()

    tiles = []
    for p in args.images:
        im = Image.open(p).convert("RGB")
        if args.scale != 1.0:
            im = im.resize((max(1, int(im.width * args.scale)), max(1, int(im.height * args.scale))),
                           Image.LANCZOS)
        tiles.append((os.path.basename(p), im))
    if not tiles:
        return 2

    if args.grid and args.grid > 1:
        cols = args.grid
        rows = math.ceil(len(tiles) / cols)
        cw = max(t.width for _, t in tiles) + args.gap
        ch = max(t.height for _, t in tiles) + args.gap
        canvas = Image.new("RGB", (cols * cw + args.gap, rows * ch + args.gap), (255, 255, 255))
        for i, (_n, t) in enumerate(tiles):
            canvas.paste(t, (args.gap + (i % cols) * cw, args.gap + (i // cols) * ch))
    else:
        width = max(t.width for _, t in tiles) + 2 * args.gap
        height = sum(t.height + args.gap for _, t in tiles) + args.gap
        canvas = Image.new("RGB", (width, height), (255, 255, 255))
        y = args.gap
        for _n, t in tiles:
            canvas.paste(t, (args.gap, y))
            y += t.height + args.gap

    if args.labels:
        d = ImageDraw.Draw(canvas)
        y = args.gap
        for name, t in tiles:
            d.rectangle([args.gap, y, args.gap + 8 * len(name) + 6, y + 14], fill=(255, 0, 0))
            d.text((args.gap + 3, y + 2), name, fill=(255, 255, 255))
            y += t.height + args.gap
    canvas.save(args.out)
    print("saved %s %dx%d (%d tiles)" % (args.out, canvas.width, canvas.height, len(tiles)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
