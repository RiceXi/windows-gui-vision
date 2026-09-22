#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write a wire into a .DSN by editing the file. Verified against ISIS 7.08 SP2.

The wire section is a list of objects, and what makes this fiddly is that a wire's contents
are not all inside its own record: after the points comes the wire's *body*, and the body ends
with a 15 byte tail block that the loader reads. When Isis adds a wire it does not invent a
new body - it hands the new wire the body that sat at the insertion point and gives the old
owner a plain default tail instead. Get that wrong and the file is refused or crashes the
loader with an access violation in VGDVCDLL.

Three things have to happen, and the second one took the longest to find:

1. splice the new wire in at the insertion point, moving the body across;
2. **relocate every pointer that pointed past the insertion point**. A pointer here is a four
   byte field whose value is the file offset of a wire tail block. Isis shifts all of them by
   the number of bytes inserted. A stale one is what crashes the loader: a design with two
   wires crashed even though each half was written the way Isis writes it;
3. fill the pointer slots that are still zero - the wire section's own "current tail" slots -
   with the tail offset this insert creates.

Where the new wire goes depends on the design's state, and there are two shapes:

* `end`  - Isis saved the design with nothing pending: the wire goes where the last wire's
           body starts. This is what Isis writes for the first wire added to a design that had
           none added in that session.
* `head` - the record whose tail block sits just before the first wire still carries a pending
           body (a `01` tag, a point and a list of tail offsets): the new wire takes that body
           and the record gets a plain tail. This is what Isis writes for the second wire.

Both were pinned down by diffing two saves of the same design, one edit apart, and then
reproducing Isis's own file byte for byte apart from the two byte stamp it rewrites on every
save. See references/dsn-wires.md for the measurements and the load test table.

    python dsn_add_wire.py --base design.DSN --points 0.7,0.8 --points 0.7,0.9 \\
           --mode end --out wired.DSN
    powershell -File design_loadcheck.ps1 -Path wired.DSN

Always run the load check. These rules were derived on one design family, and a Labcenter
sample with a different section header crashed on the first insert, so a design class has to
be confirmed once. The refusal is silent in Isis - an unverified file is worse than no file.
"""
import argparse
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"
PREFIX = bytes.fromhex("ffffff00ffffff00")
DEFAULT_TAIL = bytes.fromhex("001d00000000c09e00000040000001")
UNITS = 2540000


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def wires(d, head, tail):
    """(offset of the object header, point count) for every wire in the object area.

    "WIRE" also occurs inside property text, so keep only the candidates that carry the eight
    byte object prefix and a point count that leaves room for a body inside the area.
    """
    out = []
    for m in re.finditer(rb"\x02\x7fWIRE\x00", d[head:tail]):
        o = head + m.start()
        if d[o - 8:o] != PREFIX:
            continue
        n = u16(d, o + 9)
        if n > 64 or o + 11 + 8 * n + 15 > tail:
            continue
        out.append((o, n))
    return out


def body_offset(o, n):
    return o + 11 + 8 * n


def tail_offsets(d, head, tail):
    """Offsets of the 15 byte blocks that terminate a wire's body.

    The body start of each wire gives one candidate block; the blocks that show up more than
    once are the shared tail blocks (a design has a handful), and every occurrence of those is
    a tail offset. Bodies that occur once are attachment lists, not tails.
    """
    seen = {}
    for o, n in wires(d, head, tail):
        b = body_offset(o, n)
        seen.setdefault(bytes(d[b:b + 15]), []).append(b)
    out = set()
    for blk in seen:
        hits = []
        p = d.find(blk, head)
        while 0 <= p < tail:
            hits.append(p)
            p = d.find(blk, p + 1)
        if len(hits) >= 2:
            out.update(hits)
    return out


def relocate(d, tails, at, delta):
    """Shift every pointer into the object area that the insert moves past."""
    moved = []
    for off in range(0, len(d) - 4):
        v = u32(d, off)
        if v in tails and v >= at:
            struct.pack_into("<I", d, off, v + delta)
            moved.append((off, v, v + delta))
    return moved


def slot_run(d, head, off, tails):
    """How many u32 in a row, ending just before `off`, hold tail offsets."""
    n = 0
    p = off
    while p - 4 >= head and u32(d, p - 4) in tails:
        n += 1
        p -= 4
    return n


def empty_slots(d, head, tail, tails, run=3):
    """The wire section's zeroed "current tail" slots.

    They sit at the end of a run of tail offsets inside the junction records. Isis fills them
    with the tail block its insert creates; a design Isis saved with no wire drawn in the
    session has them zero.
    """
    return [off for off in range(head + 4, tail - 4)
            if u32(d, off) == 0 and slot_run(d, head, off, tails) >= run]


def pending_slots(d, head, tail, tails, limit=64):
    """Zero slots in front of a pending body - the tag, point and tail refs shape."""
    out = []
    for off in range(head + 4, tail - 12):
        if u32(d, off) != 0 or u32(d, off - 4) not in tails:
            continue
        tag = off + 4
        x, y = struct.unpack_from("<ii", d, tag + 1)
        if not 0 < d[tag] < 0x80:
            continue
        if abs(x) > limit * 2540000 or abs(y) > limit * 2540000:
            continue
        out.append(off)
    return out


def run_start(d, head, end, tails):
    p = end
    while p - 4 >= head and u32(d, p - 4) in tails:
        p -= 4
    return p


def add_wire(base, points, mode="end", out=None):
    d = bytearray(base)
    head = d.find(MARKER)
    tail = d.find(MARKER, head + 1)
    if min(head, tail) < 0:
        raise SystemExit("not an ISIS design file")
    ws = wires(d, head, tail)
    if not ws:
        raise SystemExit("no wire in this design; there is nothing to append beside")
    tails = tail_offsets(d, head, tail)

    rec = bytearray(PREFIX + b"\x02\x7fWIRE\x00\x00\x00")
    rec += struct.pack("<H", len(points))
    for x, y in points:
        rec += struct.pack("<ii", int(round(x * UNITS)), int(round(y * UNITS)))

    filled = []
    if mode == "head":
        t = d.rfind(DEFAULT_TAIL, head, ws[0][0] - 8)
        if t < 0:
            raise SystemExit("no head tail block found")
        run = run_start(d, head, t, tails)
        at = run - 9                       # the tag byte plus an eight byte point
        if at < head or d[at] != 0x01:
            at = run
        slots = [off for off in pending_slots(d, head, t + 15, tails)
                 if not (at <= off < t + 15)]
        delta = 8 + 11 + 8 * len(points) + 15
        moved = relocate(d, tails, at, delta)
        body = bytes(d[at:t])
        keep = bytes(d[t:t + 15])
        d[at:t + 15] = DEFAULT_TAIL + bytes(rec) + body + keep
        for off in slots:
            struct.pack_into("<I", d, off + (delta if off >= at else 0), at)
            filled.append(off)
    else:
        o, n = ws[-1]
        at = body_offset(o, n)
        body = bytes(d[at:at + 15])
        rec += body
        delta = len(rec)
        slots = empty_slots(d, head, tail, tails) if mode == "end" else []
        moved = relocate(d, tails, at, delta)
        if mode == "end0":
            # the layout an earlier version wrote: the record in front of the tail block
            d[at:at + 15] = DEFAULT_TAIL
            d[at:at] = bytes(rec)
        else:
            d[at:at + 15] = DEFAULT_TAIL + bytes(rec)
        for off in slots:
            target = off + (delta if off >= at else 0)
            if target < at or target >= at + delta:
                struct.pack_into("<I", d, target, at)
                filled.append(off)

    struct.pack_into("<I", d, head - 4, u32(d, head - 4) + delta)
    marker = d.find(MARKER, head + 1)          # the field naming the second section
    for off in range(tail, len(d) - 4):
        if u32(d, off) == tail:
            struct.pack_into("<I", d, off, marker)
            break

    if out:
        open(out, "wb").write(bytes(d))
    return dict(data=bytes(d), inserted_at=at, inserted=delta, moved=moved, filled=filled,
                tails=len(tails))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--points", action="append", required=True,
                    help="x,y in inches, in order; repeat for each point")
    ap.add_argument("--mode", default="end", choices=("end", "head", "end0"),
                    help="end and head are the two shapes Isis writes; end0 is an older layout")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pts = [tuple(float(v) for v in p.split(",")) for p in args.points]
    info = add_wire(open(args.base, "rb").read(), pts, mode=args.mode, out=args.out)
    print("wrote %s: %d bytes (+%d), %d points, spliced at %d"
          % (args.out, len(info["data"]), info["inserted"], len(pts), info["inserted_at"]))
    print("  tail blocks known: %d" % info["tails"])
    for off, was, now in info["moved"]:
        print("  relocated u32 at %d: %d -> %d" % (off, was, now))
    if info["filled"]:
        print("  filled pointer slots: %s" % info["filled"])
    print("check it with scripts/design_loadcheck.ps1 - the loader refuses bad files silently")
    return 0


if __name__ == "__main__":
    sys.exit(main())
