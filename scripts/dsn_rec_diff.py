#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare one instance's record between two .DSN files, byte by byte.

    python dsn_rec_diff.py base.DSN other.DSN U3:A U3:C ...

This is the tool that read the layout. An instance starts at its `ff 04 <ref>` marker and the
list of instances is 420 bytes apart, so the record is the 420 bytes from the marker; whatever
follows it up to the next marker is the group of objects that instance owns. Both are printed
for each reference, together with every byte of the record that differs.

Used on the five instance base against a hand-edited copy, it shows the wire records, the shift
they put on everything after them, and - in the record's last bytes - the per-pin connection
slots (see references/dsn-wire-slots.md).
"""
import re
import struct
import sys


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def load(path):
    d = open(path, "rb").read()
    head = d.find(b"ISIS CIRCUIT FILE")
    tail = d.find(b"ISIS CIRCUIT FILE", head + 1)
    marks = [(head + m.start(), m.group(1).decode("latin1"))
             for m in re.finditer(rb"\xff\x04([0-9A-Za-z]+:[A-D])", d[head:tail])]
    return d, head, tail, marks


def group(d, marks, i, tail):
    off, ref = marks[i]
    nxt = marks[i + 1][0] if i + 1 < len(marks) else tail
    return off, nxt, d[off:nxt]


def show(d, off, nxt, label):
    g = d[off:nxt]
    print("  %s: record %d..%d (420), group ends %d, extra %d bytes"
          % (label, off, off + 420, nxt, len(g) - 420))
    print("    last 36 of record:")
    for p in range(off + 384, off + 420, 4):
        print("      %6d  %s  u32=%d" % (p, d[p:p + 4].hex(" "), u32(d, p)))
    if len(g) > 420:
        print("    beyond the record (first 200 bytes):")
        for p in range(off + 420, min(nxt, off + 620), 16):
            row = d[p:p + 16]
            print("      %6d  %-47s  %s"
                  % (p, row.hex(" "), "".join(chr(c) if 32 <= c < 127 else "." for c in row)))


def main():
    a_path, b_path = sys.argv[1], sys.argv[2]
    refs = sys.argv[3:]
    da, ha, ta, ma = load(a_path)
    db, hb, tb, mb = load(b_path)
    print("A %s: %d bytes, area %d..%d" % (a_path, len(da), ha, ta))
    print("B %s: %d bytes, area %d..%d" % (b_path, len(db), hb, tb))
    for ref in refs:
        ia = [i for i, (_, r) in enumerate(ma) if r == ref]
        ib = [i for i, (_, r) in enumerate(mb) if r == ref]
        if not ia or not ib:
            print("\n== %s: missing in %s" % (ref, "A" if not ia else "B"))
            continue
        oa, na, ga = group(da, ma, ia[0], ta)
        ob, nb, gb = group(db, mb, ib[0], tb)
        print("\n== %s" % ref)
        show(da, oa, na, "A")
        show(db, ob, nb, "B")
        print("    changed bytes in the 420 byte record (offsets are A's):")
        n = 0
        for k in range(420):
            if ga[k] != gb[k]:
                n += 1
                print("      %6d  A=%02x B=%02x" % (oa + k, ga[k], gb[k]))
        if not n:
            print("      none")


if __name__ == "__main__":
    main()
