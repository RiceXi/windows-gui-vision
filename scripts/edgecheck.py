#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Did a crop cut through the content?

Counts dark pixels in the outermost band of every crop. A non-zero count means something
is touching (and probably crossing) the edge, so re-crop with more margin.

    python edgecheck.py *.png [--thresh 150] [--band 3] [--allow 40]
"""
import argparse
import sys

import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--thresh", type=int, default=150, help="'dark' below this luminance")
    ap.add_argument("--band", type=int, default=3, help="edge band width in px")
    ap.add_argument("--allow", type=int, default=40, help="dark px tolerated on the rim")
    args = ap.parse_args()

    bad = 0
    for path in args.images:
        a = np.array(Image.open(path).convert("L"))
        h, w = a.shape
        b = args.band
        rim = np.concatenate([a[:b, :].ravel(), a[-b:, :].ravel(),
                              a[:, :b].ravel(), a[:, -b:].ravel()])
        n = int((rim < args.thresh).sum())
        flag = "CUT? " if n > args.allow else "ok   "
        if n > args.allow:
            bad += 1
        print("%s %-32s %5dx%-5d rim-dark=%5d" % (flag, path.split("\\")[-1].split("/")[-1],
                                                  w, h, n))
    print("%d/%d crops look cut" % (bad, len(args.images)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
