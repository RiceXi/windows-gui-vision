#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Keep a per-application widget map in the app's logical pixel space and convert it to
click coordinates for the machine you are actually on.

    # start from a calibration run and add named anchors as you discover them
    python layout.py init  layout.json --from calib.json --app "Proteus ISIS 7"
    python layout.py set   layout.json generators_button 14,346 --note "mode toolbar"
    python layout.py show  layout.json

    # turn a named anchor into the coordinates an input API wants
    python layout.py click layout.json generators_button --print-width 1416 --shot-width 2804
    python layout.py click layout.json generators_button --scale 2

Values are stored in logical pixels; `click` multiplies by the scale you supply (measured as
screenshot width / print width), which is what makes the same map valid at any DPI/resolution.
"""
import argparse
import json
import os
import sys


def load(path):
    if not os.path.exists(path):
        return {"app": None, "anchors": {}, "notes": {}}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)


def cmd_init(args):
    data = load(args.path)
    if args.app:
        data["app"] = args.app
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as fh:
            calib = json.load(fh)
        data["calibration"] = calib
        tb = calib.get("toolbar", {})
        if tb.get("buttons_y"):
            data.setdefault("anchors", {})
            for i, y in enumerate(tb["buttons_y"]):
                data["anchors"].setdefault("icon_%02d" % i, [tb.get("x", 0), y])
        lst = calib.get("list", {})
        if lst.get("first_row_y") is not None and lst.get("pitch_y"):
            data["anchors"]["list_row_0"] = [lst.get("x", 0), lst["first_row_y"]]
            data["notes"]["list_row_pitch"] = lst["pitch_y"]
    save(args.path, data)
    print("initialised %s with %d anchors" % (args.path, len(data.get("anchors", {}))))
    return 0


def cmd_set(args):
    data = load(args.path)
    x, y = (float(v) for v in args.point.split(","))
    data.setdefault("anchors", {})[args.name] = [x, y]
    if args.note:
        data.setdefault("notes", {})[args.name] = args.note
    save(args.path, data)
    print("%s = (%.0f, %.0f)  [%d anchors]" % (args.name, x, y, len(data["anchors"])))
    return 0


def cmd_row(args):
    """List anchor for row n, using the calibrated first row + pitch."""
    data = load(args.path)
    first = data["anchors"].get("list_row_0")
    pitch = data["notes"].get("list_row_pitch")
    if not first or not pitch:
        print("no list_row_0 / list_row_pitch in %s - run init from a calibration first" % args.path)
        return 2
    x, y = first[0], first[1] + pitch * args.index
    print("%s" % json.dumps([x, y]))
    return 0


def cmd_show(args):
    data = load(args.path)
    print("app:", data.get("app"))
    calib = data.get("calibration") or {}
    if calib:
        print("calibrated from %s  size=%s  canvas=%s" %
              (calib.get("source"), calib.get("size"), calib.get("canvas")))
        if "scale" in calib:
            print("known scale (shot/print):", calib["scale"])
    for name, pt in sorted((data.get("anchors") or {}).items()):
        note = (data.get("notes") or {}).get(name, "")
        print("  %-20s (%7.1f, %7.1f)  %s" % (name, pt[0], pt[1], note))
    return 0


def cmd_click(args):
    data = load(args.path)
    pt = (data.get("anchors") or {}).get(args.name)
    if pt is None:
        print("unknown anchor %r" % args.name, file=sys.stderr)
        return 2
    if args.scale is not None:
        scale = args.scale
    elif args.print_width and args.shot_width:
        scale = float(args.shot_width) / float(args.print_width)
    else:
        scale = float((data.get("calibration") or {}).get("scale") or 1.0)
    off = (0.0, 0.0)
    if args.offset:
        off = tuple(float(v) for v in args.offset.split(","))
    x = (pt[0] + off[0]) * scale
    y = (pt[1] + off[1]) * scale
    if args.json:
        print(json.dumps({"name": args.name, "logical": pt, "scale": scale,
                          "input": [round(x, 1), round(y, 1)]}))
    else:
        print("%s: logical (%.0f, %.0f) x scale %.4f -> input (%.0f, %.0f)"
              % (args.name, pt[0], pt[1], scale, x, y))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("path")
    p.add_argument("--from", dest="from_file")
    p.add_argument("--app")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("set")
    p.add_argument("path")
    p.add_argument("name")
    p.add_argument("point", help="x,y in logical pixels")
    p.add_argument("--note", default="")
    p.set_defaults(fn=cmd_set)

    p = sub.add_parser("row")
    p.add_argument("path")
    p.add_argument("index", type=int)
    p.set_defaults(fn=cmd_row)

    p = sub.add_parser("show")
    p.add_argument("path")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("click")
    p.add_argument("path")
    p.add_argument("name")
    p.add_argument("--scale", type=float, default=None)
    p.add_argument("--print-width", type=int, default=None)
    p.add_argument("--shot-width", type=int, default=None)
    p.add_argument("--offset", default=None, help="logical dx,dy (e.g. aim right of an anchor)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_click)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
