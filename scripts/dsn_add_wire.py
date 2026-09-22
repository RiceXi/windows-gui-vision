#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add one wire to a .DSN by editing the file. Verified against ISIS 7.08 SP2.

The wire group in a design ends with a 15-byte tail block that is not a constant. When ISIS adds
a wire it takes that block off the previous last wire, gives that wire the default block, and
hands the old values to the new wire. Get that wrong and the new wire lands in a state the
loader rejects, which is what six earlier attempts at appending a wire did.

What this does:

  1. finds the last wire in the object area and its tail block;
  2. replaces that block with the default one and inserts, at the same offset,
     `FF FF FF 00 FF FF FF 00` + `02 7F "WIRE" 00 00 00` + point count + points + the old block;
  3. writes the insertion offset into the two 2-byte link fields that the operation updates;
  4. grows the object-area end field at head-4 by the length inserted.

Step 3 is the part that is not general yet. In the design these offsets were measured in, the
fields sit at the end of an offset list inside a component record and inside a wire record, and
the value written is the insertion offset. Until the rule that identifies them is worked out,
pass them in with --link, one per wire endpoint, using the offsets a ground-truth pair gives
you (see references/dsn-wires.md).

    python dsn_add_wire.py --base design.DSN --points -0.5,0.5 --points 0.5,0.5 \\
           --link 13591 --link 13790 --out wired.DSN
"""
import argparse
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"
DEFAULT_TAIL = bytes.fromhex("001d00000000c09e00000040000001")
PREFIX = bytes.fromhex("ffffff00ffffff00")
UNITS = 2540000


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def last_wire(d, head, tail):
    """(header offset of the last wire, offset of its tail block, point count)."""
    hits = [m.start() for m in re.finditer(rb"\x02\x7fWIRE\x00", d[head:tail])]
    if not hits:
        raise SystemExit("no wire in this design; nothing to append next to")
    # "WIRE" also appears inside property strings, so keep only the candidates that look like
    # a real wire object: the 8-byte object prefix in front, a sane point count, and room for
    # the 15-byte tail block inside the object area.
    ok = []
    for h in hits:
        o = head + h
        if d[o - 8:o] != PREFIX:
            continue
        n = u16(d, o + 9)
        block = o + 11 + 8 * n
        if n > 64 or block + 15 > tail:
            continue
        ok.append((o, block, n))
    if not ok:
        raise SystemExit("no complete wire object found in the object area")
    return ok[-1]


def add_wire(base, points, links, out=None):
    d = bytearray(base)
    head = d.find(MARKER)
    tail = d.find(MARKER, head + 1)
    if min(head, tail) < 0:
        raise SystemExit("not an ISIS design file")
    _o, block, _n = last_wire(d, head, tail)
    live = bytes(d[block:block + 15])

    wire = bytearray(PREFIX + b"\x02\x7fWIRE\x00\x00\x00")
    wire += struct.pack("<H", len(points))
    for x, y in points:
        wire += struct.pack("<ii", int(round(x * UNITS)), int(round(y * UNITS)))
    wire += live

    d[block:block + 15] = DEFAULT_TAIL + wire
    for off in links:
        struct.pack_into("<H", d, off, block & 0xFFFF)

    old = struct.unpack_from("<I", base, head - 4)[0]
    struct.pack_into("<I", d, head - 4, old + len(wire))
    if out:
        open(out, "wb").write(bytes(d))
    return bytes(d), dict(inserted_at=block, inserted=len(wire), live=live.hex())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--points", action="append", required=True,
                    help="x,y in inches, in order; repeat for each point")
    ap.add_argument("--link", action="append", type=int, default=[],
                    help="offset of a 2-byte link field to point at the new wire")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pts = [tuple(float(v) for v in p.split(",")) for p in args.points]
    base = open(args.base, "rb").read()
    data, info = add_wire(base, pts, args.link, out=args.out)
    print("wrote %s: %d bytes (+%d), wire at %d, %d points"
          % (args.out, len(data), info["inserted"], info["inserted_at"], len(pts)))
    print("tail block moved to the new wire:", info["live"])
    if not args.link:
        print("WARNING: no --link fields given. The design will most likely fail to load;")
        print("ISIS updates two link fields when it adds a wire (see references/dsn-wires.md).")
    print("check it with scripts/design_loadcheck.ps1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
