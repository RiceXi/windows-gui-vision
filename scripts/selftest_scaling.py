#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prove that calibration is resolution independent.

Resamples one window capture to several sizes, calibrates each, and checks that every
measured distance scales by the same factor as the image. Run this after copying the skill to
a machine with a different DPI or monitor: if the ratios track the scale factors, widget
anchors taken from the logical-pixel capture remain valid there.

    python selftest_scaling.py path/to/printwindow.png [--factors 0.75,1,1.25,1.5,2]
"""
import argparse
import os
import sys
import tempfile

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate  # noqa: E402  (same directory)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--factors", default="0.75,1,1.25,1.5,2")
    ap.add_argument("--tol", type=float, default=0.18,
                    help="relative error tolerated between measured pitch and the scale")
    args = ap.parse_args()

    factors = [float(v) for v in args.factors.split(",")]
    base = Image.open(args.image)
    work = tempfile.mkdtemp(prefix="wgv_scale_")
    rows = []
    for f in factors:
        path = os.path.join(work, "s%.2f.png" % f)
        base.resize((max(80, int(base.width * f)), max(80, int(base.height * f))),
                    Image.LANCZOS).save(path)
        r = calibrate.analyze(path)
        rows.append((f, r))

    ref_f, ref = rows[[r[0] for r in rows].index(1.0)] if 1.0 in [r[0] for r in rows] else rows[0]
    ref_icon = ref["toolbar"]["pitch_y"]
    ref_list = ref["list"]["pitch_y"]
    ref_x = ref["toolbar"]["x"]

    print("reference: scale %.2f  icon pitch=%s  list pitch=%s  icon x=%d"
          % (ref_f, ref_icon, ref_list, ref_x))
    print()
    print("%-7s %-9s %-11s %-11s %-11s %s" %
          ("scale", "img", "icon pitch", "list pitch", "icon x", "verdict"))
    ok = True
    for f, r in rows:
        icon = r["toolbar"]["pitch_y"]
        lst = r["list"]["pitch_y"]
        x = r["toolbar"]["x"]
        ratio = f / ref_f
        checks = []
        skipped = []
        for name, val, base_v in (("icon", icon, ref_icon), ("list", lst, ref_list),
                                  ("x", x, ref_x)):
            if not base_v:
                continue
            if val is None:
                # not detected at this size (blurred rows): not a scaling failure
                skipped.append(name)
                continue
            checks.append((name, abs(val / float(base_v) - ratio) <= args.tol))
        good = all(c[1] for c in checks) and bool(checks)
        ok = ok and good
        verdict = ("proportional" if good else "MISMATCH " + ",".join(n for n, g in checks if not g))
        if skipped:
            verdict += " (not detected: %s)" % ",".join(skipped)
        print("%-7.2f %-9s %-11s %-11s %-11s %s"
              % (f, "%dx%d" % (r["size"][0], r["size"][1]),
                 "-" if icon is None else icon, "-" if lst is None else lst, x, verdict))
    print()
    print("verdict:", "calibration scales linearly - anchors are resolution independent"
          if ok else "some measurements did not scale; re-capture at full resolution")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
