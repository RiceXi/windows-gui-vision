#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inspect a region of a screenshot numerically and render it as ASCII art.

Usage:
    python region_ascii.py shot.png x0,y0,x1,y1 [--thresh 150] [--block 3]

Prints ink statistics, the ink bounding box, long horizontal/vertical runs
(useful for detecting wires), and an ASCII rendering of the region so that
symbol outlines and line endpoints can be located without seeing the image.
"""
import argparse
import sys

import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("region", help="x0,y0,x1,y1")
    ap.add_argument("--thresh", type=int, default=150, help="ink threshold on grayscale")
    ap.add_argument("--block", type=int, default=3, help="ascii downsample block size")
    ap.add_argument("--runs", type=int, default=25, help="minimum run length to report")
    a = ap.parse_args()

    x0, y0, x1, y1 = (int(v) for v in a.region.split(","))
    img = Image.open(a.image).convert("L")
    reg = np.array(img)[y0:y1, x0:x1]
    ink = reg < a.thresh
    total = int(ink.sum())
    print("region %d,%d-%d,%d  size %dx%d  ink(<%d)=%d (%.2f%%)"
          % (x0, y0, x1, y1, x1 - x0, y1 - y0, a.thresh, total, 100.0 * total / ink.size))
    if total == 0:
        print("no ink: region is blank (or the capture is empty/black)")
        return 0

    ys, xs = np.nonzero(ink)
    print("ink bbox: x %d..%d  y %d..%d" % (x0 + xs.min(), x0 + xs.max(), y0 + ys.min(), y0 + ys.max()))

    def runs(profile, axis_name, offset):
        out, cur = [], None
        for i, v in enumerate(profile):
            if v >= 2 and cur is None:
                cur = i
            elif v < 2 and cur is not None:
                if i - cur >= a.runs:
                    out.append((offset + cur, offset + i, i - cur))
                cur = None
        if cur is not None and len(profile) - cur >= a.runs:
            out.append((offset + cur, offset + len(profile), len(profile) - cur))
        for s, e, n in out:
            print("  long %s run %d..%d (len %d)" % (axis_name, s, e, n))

    runs(ink.sum(axis=0), "horizontal", x0)
    runs(ink.sum(axis=1), "vertical", y0)

    b = a.block
    H, W = ink.shape
    for y in range(0, H, b):
        row = []
        for x in range(0, W, b):
            row.append("#" if ink[y:y + b, x:x + b].sum() >= max(1, b * b // 3) else " ")
        print("   " + "".join(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
