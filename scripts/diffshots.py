#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prove that an action changed what you think it changed.

A click that "succeeds" can still do nothing. Compare two captures taken before and after
the action: this prints how many pixels changed, where, and whether the change is confined
to the areas you expect.

    python diffshots.py before.png after.png [--region 300,170,2560,1570] [-o heat.png]
"""
import argparse
import sys

import numpy as np
from PIL import Image, ImageChops


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--region", default=None, help="x0,y0,x1,y1 to limit the comparison")
    ap.add_argument("--thresh", type=int, default=60, help="per-pixel RGB delta counted as changed")
    ap.add_argument("-o", "--heat", default=None, help="write a red-on-grey heat map")
    args = ap.parse_args()

    a = Image.open(args.before).convert("RGB")
    b = Image.open(args.after).convert("RGB")
    if a.size != b.size:
        print("size mismatch %s vs %s - compare captures of the same window"
              % (a.size, b.size))
        return 2
    if args.region:
        x0, y0, x1, y1 = (int(v) for v in args.region.split(","))
        a = a.crop((x0, y0, x1, y1))
        b = b.crop((x0, y0, x1, y1))
    else:
        x0 = y0 = 0

    d = np.array(ImageChops.difference(a, b)).sum(axis=2)
    changed = d > args.thresh
    n = int(changed.sum())
    total = changed.size
    print("changed %d / %d px (%.3f%%)" % (n, total, 100.0 * n / total))
    if n:
        ys, xs = np.nonzero(changed)
        print("bbox (image coords): x %d..%d  y %d..%d"
              % (x0 + xs.min(), x0 + xs.max(), y0 + ys.min(), y0 + ys.max()))
        # column/row profile: tells you whether the change is in a panel or the canvas
        cols = changed.sum(axis=0)
        rows = changed.sum(axis=1)
        hot_c = np.nonzero(cols > cols.max() * 0.15)[0]
        hot_r = np.nonzero(rows > rows.max() * 0.15)[0]
        print("busiest columns: %d..%d   busiest rows: %d..%d"
              % (x0 + hot_c.min(), x0 + hot_c.max(), y0 + hot_r.min(), y0 + hot_r.max()))
    if args.heat:
        grey = np.array(a.convert("L").convert("RGB")).copy()
        grey[changed] = (255, 0, 0)
        Image.fromarray(grey).save(args.heat)
        print("heat map ->", args.heat)
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
