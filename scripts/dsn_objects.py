#!/usr/bin/env python3
"""List the objects of a Proteus .DSN: parts with their anchors, terminals, wires.

    python dsn_objects.py design.DSN

Anchor offsets were measured against this build: an instance record is
[0xFF][type][name][anchor x,y as little-endian int32 in 1/2540000 inch]...
so the anchor sits at record offset 2 + len(name).
"""
import re
import struct
import sys

UNITS = 2540000.0


def main(path):
    d = open(path, "rb").read()
    head = d.find(b"ISIS CIRCUIT FILE")
    tail = d.find(b"ISIS CIRCUIT FILE", head + 1)
    if head < 0 or tail < 0:
        print("no circuit markers: %s" % path)
        return
    print("== %s  %d bytes, object area %d..%d" % (path, len(d), head, tail))

    # A terminal record is [0xFF][len]["$TERPOWER"][0x0D][0x00][0xFF][len][name]
    # so the net name is the length-prefixed string a dozen bytes further on.
    for m in re.finditer(b"[\t\n]\\$TER(POWER|GROUND)", d[head:tail]):
        o = head + m.start()
        kind = "$TER" + m.group(1).decode("latin1")
        # [len][$TERPOWER][0x0D][0x00][0xFF][len][name][anchor x][anchor y]
        cat = o + 1 + len(kind) + 3
        nlen = d[cat]
        label = d[cat + 1:cat + 1 + nlen].decode("latin1", "replace")
        x, y = struct.unpack_from("<ii", d, cat + 1 + nlen)
        print("  %-12s @%-7d (%.4f, %.4f)  name=%r"
              % (kind, o, x / UNITS, y / UNITS, label))

    pat = re.compile(b"\xff([\x02\x03\x07])([\x20-\x7e]{1,14})")
    for m in pat.finditer(d[head:tail]):
        o = head + m.start()
        kind = m.group(1)[0]
        name = m.group(2).decode("latin1")
        if o + 16 < head or name.startswith("$TER"):
            continue
        pos = o + 2 + len(name)
        x, y = struct.unpack_from("<ii", d, pos)
        print("  part %-14s kind=%d @%-7d (%.4f, %.4f)"
              % (name, kind, o, x / UNITS, y / UNITS))

    for m in re.finditer(b"\x02\x7fWIRE\x00", d[head:tail]):
        o = head + m.start()
        n = struct.unpack_from("<H", d, o + 9)[0]
        pts = [struct.unpack_from("<ii", d, o + 11 + 8 * i) for i in range(n)]
        print("  WIRE @%-7d n=%d  %s" % (o, n, " ".join(
            "(%.3f,%.3f)" % (a / UNITS, b / UNITS) for a, b in pts)))


if __name__ == "__main__":
    main(sys.argv[1])
