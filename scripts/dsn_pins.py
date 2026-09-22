#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List the connection points of every part in a design.

A wire ends on a pin, so the endpoints of the wires around a part are that part's pin
positions, in design inches. Reading them out of a design that is already wired is the cheap way
to learn the geometry of a part: place one instance in ISIS, wire it, save, and this tells you
where its pins are relative to the anchor stored in the record. That offset is what a script
needs in order to place another copy of the part and route a wire to the right pixel - or the
right 10 nm unit, since it is all the same grid.

    python dsn_pins.py design.DSN [--radius 1.0] [--json]

Output is one line per part: its reference, its anchor in inches, and each connection point as
an offset from that anchor.
"""
import argparse
import json
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"
PREFIX = bytes.fromhex("ffffff00ffffff00")
UNITS = 2540000


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def parts(d, head, tail):
    out = []
    for m in re.finditer(rb"\xff\x02([\x20-\x7e]{2})", d[head:tail]):
        o = head + m.start()
        x, y = struct.unpack_from("<ii", d, o + 4)
        # a real record carries these fields; a chance byte pair inside data does not
        if b"COMPONENT VALUE" not in d[o:o + 4000]:
            continue
        out.append((m.group(1).decode("latin1"), x / UNITS, y / UNITS, o))
    return out


def wire_ends(d, head, tail):
    out = []
    for m in re.finditer(rb"\x02\x7fWIRE\x00", d[head:tail]):
        o = head + m.start()
        if d[o - 8:o] != PREFIX:
            continue
        n = u16(d, o + 9)
        if n > 64 or o + 11 + 8 * n + 15 > tail:
            continue
        pts = [tuple(v / UNITS for v in struct.unpack_from("<ii", d, o + 11 + 8 * k))
               for k in range(n)]
        out.append(pts)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--radius", type=float, default=1.2,
                    help="how far from an anchor to look for wire ends, in inches")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    d = open(args.design, "rb").read()
    head = d.find(MARKER)
    tail = d.find(MARKER, head + 1)
    if min(head, tail) < 0:
        raise SystemExit("not an ISIS design file")

    ends = []
    for pts in wire_ends(d, head, tail):
        ends.extend(pts)
    result = {}
    for ref, ax, ay, _o in parts(d, head, tail):
        near = sorted({(round(p[0] - ax, 4), round(p[1] - ay, 4)) for p in ends
                       if abs(p[0] - ax) <= args.radius and abs(p[1] - ay) <= args.radius},
                      key=lambda t: (t[0], t[1]))
        result[ref] = {"anchor": [round(ax, 4), round(ay, 4)],
                       "pins_from_wires": [list(t) for t in near]}

    if args.json:
        print(json.dumps(result, indent=1))
    else:
        for ref, info in result.items():
            print("%-4s anchor (%7.3f, %7.3f)  %d wire ends nearby" %
                  (ref, info["anchor"][0], info["anchor"][1], len(info["pins_from_wires"])))
            for off in info["pins_from_wires"]:
                print("        offset (%6.3f, %6.3f)" % (off[0], off[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
