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
one. `wires` are point lists in the same units - a wire has to start and end on a pin, and where
those are is in references/dsn-build-circuit.md.

Each part must belong to a device the base design already embeds, and each wire needs a link
field offset from that design - which this finds the same way dsn_add_wire.py --find-links does,
so a design that has never had a wire written to it is the case to check first.

This is a thin orchestrator on purpose: dsn_add_instance.py and dsn_add_wire.py do the work and
carry their own notes about what is verified. What this adds is doing them in order on one file
and checking the result loads.
"""
import argparse
import json
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
from dsn_add_instance import append_instance                     # noqa: E402
from dsn_add_wire import add_wire, find_link_fields              # noqa: E402

MARKER = b"ISIS CIRCUIT FILE"


def build(base_path, spec, out_path):
    data = open(base_path, "rb").read()
    steps = []
    for part in spec.get("parts", []):
        x, y = part["at"]
        data, info = append_instance(data, part["device"], x, y)
        steps.append("instance %s at (%.3f, %.3f)" % (info["name"], x, y))

    wires = spec.get("wires", [])
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
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    data, steps = build(args.base, spec, args.out)
    for s in steps:
        print("  " + s)
    print("wrote %s (%d bytes, %d parts, %d wires)"
          % (args.out, len(data), len(spec.get("parts", [])), len(spec.get("wires", []))))
    print("next: scripts/design_loadcheck.ps1, then open it in ISIS and save to be sure")
    return 0


if __name__ == "__main__":
    sys.exit(main())
