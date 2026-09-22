#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read the object area of a .DSN: the wires, their bodies and the pointers between them.

What it prints, and what each part means:

  wire @o   offset of the wire object; n  how many points it has;
  body @b   where the bytes after the points start - this is the wire's body, and the first
            15 bytes of the body are the tail block the loader reads;
  tail @t   every occurrence of a shared 15 byte tail block - these are the offsets the
            pointer fields in the file point at, which is what makes them recognisable;
  pointer   a 4 byte field holding one of those tail offsets, i.e. a field that has to be
            shifted when bytes are inserted in front of it.

    python dsn_walk.py design.DSN
"""
import re
import struct
import sys

PREFIX = bytes.fromhex("ffffff00ffffff00")
DEFAULT_TAIL = bytes.fromhex("001d00000000c09e00000040000001")
UNITS = 2540000.0


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def wire_list(d, head, tail):
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


def main():
    path = sys.argv[1]
    d = open(path, "rb").read()
    head = d.find(b"ISIS CIRCUIT FILE")
    tail = d.find(b"ISIS CIRCUIT FILE", head + 1)
    print("== %s (%d bytes) area %d..%d" % (path, len(d), head, tail))
    print("   object area end field at head-4: %d" % u32(d, head - 4))

    ws = wire_list(d, head, tail)
    bodies = {}
    for o, n in ws:
        b = o + 11 + 8 * n
        bodies[b] = bytes(d[b:b + 15])
        pts = [struct.unpack_from("<ii", d, o + 11 + 8 * i) for i in range(n)]
        print("  wire @%-6d n=%-3d body @%-6d %s"
              % (o, n, b, " ".join("(%.2f,%.2f)" % (x / UNITS, y / UNITS) for x, y in pts[:8])))
        print("        body bytes: %s" % bodies[b].hex())

    # a tail block is one whose bytes occur at a second wire's body start as well
    shared = [blk for blk in set(bodies.values())
              if len([b for b in bodies if bodies[b] == blk]) >= 2]
    tails = set()
    for blk in shared:
        p = d.find(blk, head)
        while 0 <= p < tail:
            tails.add(p)
            p = d.find(blk, p + 1)
    print("  tail blocks: %d at %s" % (len(tails), sorted(tails)))

    print("  pointer fields (value is a tail offset):")
    for off in range(head, tail - 3):
        v = u32(d, off)
        if v in tails:
            print("    %6d -> %6d" % (off, v))


if __name__ == "__main__":
    main()
