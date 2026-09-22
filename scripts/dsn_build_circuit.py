#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a design from a circuit description, on top of the two verified editors.

    python dsn_build_circuit.py --base design.DSN --spec circuit.json --out built.DSN

The description is json:

    {
      "parts": [{"device": "74LS00", "at": [-2.0, 2.0]},
                {"device": "74LS00", "at": [-0.5, 2.0]}],
      "wires": [{"points": [[-1.75, 2.02], [-1.0, 2.02]]}]
    }

`parts` are anchors in inches, not the point you would click in the editor; the anchor a record
stores is 0.308 inch left of and 0.208 inch below the click, and this script deals in the stored
one.

Wire two parts by pin name instead of by coordinates, using the table in pin_tables.json:

    "nets": [{"from": ["U4:B", "Y"], "to": ["U4:C", "A"]}]

Each named part is one the run placed, referred to by the reference the script assigned - so a
spec that wants to wire parts should also give each of them a `label`:

    {"device": "74LS00", "label": "gate1", "at": [-2.0, 2.0]},
    {"device": "74LS00", "label": "gate2", "at": [-0.5, 2.0]}

and the nets refer to the labels. A net is routed as an orthogonal path on the 0.1 inch grid.
Wires can still be given as raw point lists when the table has nothing for a device.

Each part must belong to a device the base design already embeds, and each wire needs a link
field offset from that design - which this finds the same way dsn_add_wire.py --find-links does,
so a design that has never had a wire written to it is the case to check first.

This is a thin orchestrator on purpose: dsn_add_instance.py and dsn_add_wire.py do the work and
carry their own notes about what is verified. What this adds is doing them in order on one file
and checking the result loads.
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from dsn_add_instance import append_instance                     # noqa: E402
from dsn_add_wire import add_wire, find_link_fields              # noqa: E402

MARKER = b"ISIS CIRCUIT FILE"


def load_pins(path):
    try:
        return json.load(open(path, encoding="utf-8"))["devices"]
    except (OSError, KeyError, ValueError):
        return {}


def pin_xy(anchor, offset):
    return [round(anchor[0] + offset[0], 4), round(anchor[1] + offset[1], 4)]


def route(a, b):
    """An orthogonal path between two points, bending on the 0.1 inch grid."""
    (x1, y1), (x2, y2) = a, b
    if abs(x1 - x2) < 0.05 or abs(y1 - y2) < 0.05:
        return [a, b]
    mid_x = round(round((x1 + x2) / 2, 3) * 10) / 10.0
    return [a, [mid_x, y1], [mid_x, y2], b]


def build(base_path, spec, out_path, pins_path):
    data = open(base_path, "rb").read()
    steps = []
    anchors = {}
    for part in spec.get("parts", []):
        x, y = part["at"]
        data, info = append_instance(data, part["device"], x, y)
        steps.append("instance %s at (%.3f, %.3f)" % (info["name"], x, y))
        anchors[part.get("label", info["name"])] = {
            "device": part["device"], "name": info["name"], "at": [x, y]}

    pins = load_pins(pins_path)
    wires = [dict(w) for w in spec.get("wires", [])]
    for net in spec.get("nets", []):
        parts_of_net = [net["from"], net["to"]] if "from" in net else net["nodes"]
        points = []
        for label, pin in parts_of_net:
            if label not in anchors:
                raise SystemExit("no part labelled %s in the spec" % label)
            dev = anchors[label]["device"]
            if dev not in pins or pin not in pins[dev]["offsets"]:
                raise SystemExit("pin_tables.json has no %s pin %s" % (dev, pin))
            xy = pin_xy(anchors[label]["at"], pins[dev]["offsets"][pin])
            points.append(xy)
            steps.append("net %s: %s.%s at (%.3f, %.3f)" % (
                net.get("name", "?"), label, pin, xy[0], xy[1]))
        for a, b in zip(points, points[1:]):
            wires.append({"points": route(a, b)})

    if wires:
        head = data.find(MARKER)
        tail = data.find(MARKER, head + 1)
        links = [off for off, _cnt, _offs in find_link_fields(data, head, tail)]
        for w in wires:
            data, info = add_wire(data, [tuple(p) for p in w["points"]], links)
            steps.append("wire of %d points at %s" % (len(w["points"]), info["inserted_at"]))

    open(out_path, "wb").write(data)
    return data, steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pins", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                   "pin_tables.json"))
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    data, steps = build(args.base, spec, args.out, args.pins)
    for s in steps:
        print("  " + s)
    print("wrote %s (%d bytes, %d parts, %d wires)"
          % (args.out, len(data), len(spec.get("parts", [])), len(spec.get("wires", []))))
    print("next: scripts/design_loadcheck.ps1, then open it in ISIS and save to be sure")
    return 0


if __name__ == "__main__":
    sys.exit(main())
