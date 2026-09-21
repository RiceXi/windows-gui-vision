#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add one component to a Proteus ISIS .DSN by editing the file.

The record is cloned from a template - a file in which ISIS itself placed that part - because
only ISIS can write a valid record. See references/dsn-generate.md for why, and for the
round-trip test that tells you whether the result was really accepted.

    python dsn_add_component.py --base design.DSN --template part_example.DSN \\
           --out design_plus.DSN --ref U9 [--at 2.5,1.75] [--dry-run]

--at takes logical inches for the new part's anchor; the template's coordinates are kept
otherwise, which means the clone lands on top of the template's part.

Assumptions, all measured on designs written by ISIS 7.8:
  * the object area sits between the first and second "ISIS CIRCUIT FILE" marker;
  * a u16 near the file header holds the object-area end plus 48 (found by search, not by a
    hard-coded offset);
  * the directory keeps a u8 entry count at ROOT1+12 and entries of the shape
    u16 id, u16 sequence, u16 zero, u8 name length, name, six zero bytes.
"""
import argparse
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"


def u16(buf, off):
    return struct.unpack_from("<H", buf, off)[0]


def find_record(template, tail):
    """The FF 02 <ref> record that ends just before the object-area end."""
    start = template.rfind(b"\xFF\x02", 12000, tail)
    if start < 0:
        raise SystemExit("no FF 02 record found in the template before the object-area end")
    return bytearray(template[start:tail])


def find_object_end_field(buf, tail, limit=25000):
    """u16 that tracks the object-area end (value == tail + 48)."""
    want = (tail + 48) & 0xFFFF
    for off in range(512, min(limit, len(buf) - 1)):
        if u16(buf, off) == want:
            return off
    return None


def find_entry_anchor(buf, dirpos):
    """End of the last object entry in the directory.

    ISIS names auto-placed objects P2C followed by six hex digits, stored as
    [u8 length][name][6 zero bytes]. Inserting after the last of those puts the new entry at
    the end of the list, which is where ISIS appends its own.
    """
    last = None
    for m in re.finditer(rb"\x09P2C[0-9A-Fa-f]{6}", buf[dirpos:]):
        last = dirpos + m.start()
    if last is None:
        for m in re.finditer(rb"\x0[aA]P2C[0-9A-Fa-f]{7}", buf[dirpos:]):
            last = dirpos + m.start()
    if last is None:
        return None
    return last + 1 + 9 + 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", required=True, help="reference name, same length as the template's")
    ap.add_argument("--at", default=None, help="x,y in logical inches for the new part's anchor")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = bytearray(open(args.base, "rb").read())
    tpl = open(args.template, "rb").read()
    size0 = len(data)

    head = data.find(MARKER)
    tail = data.find(MARKER, head + 1)
    ttail = tpl.find(MARKER, tpl.find(MARKER) + 1)
    if min(head, tail, ttail) < 0:
        raise SystemExit("could not find both ISIS CIRCUIT FILE markers")

    rec = find_record(tpl, ttail)
    old_ref = bytes(rec[2:4])
    new_ref = args.ref.encode()
    if len(new_ref) != len(old_ref):
        raise SystemExit("reference name must stay %d bytes, got %d (%r vs %r)"
                         % (len(old_ref), len(new_ref), old_ref, new_ref))
    rec[2:4] = new_ref

    if args.at:
        # the first two int32s after the reference are the anchor coordinates, in 10 nm units
        x, y = (float(v) for v in args.at.split(","))
        struct.pack_into("<ii", rec, 4, int(round(x * 2540000)), int(round(y * 2540000)))

    next_id_off = head + 19
    old_next = u16(data, next_id_off)

    dirpos = data.rfind(b"OBJECT DATA")
    root = data.find(b"ROOT1", dirpos)
    count_off = root + 12
    old_count = data[count_off]
    end_field = find_object_end_field(data, tail)

    print("template record %d bytes, reference %r -> %r" % (len(rec), old_ref, new_ref))
    print("next-id %d -> %d, directory entries %d -> %d, object-end field at %s"
          % (old_next, old_next + 1, old_count, old_count + 1, end_field))
    if args.dry_run:
        return 0

    struct.pack_into("<H", data, next_id_off, (old_next + 1) & 0xFFFF)

    data[tail:tail] = rec
    delta = len(rec)
    data[tail - 1] = 0x00
    if end_field is not None:
        struct.pack_into("<H", data, end_field, (u16(data, end_field) + delta) & 0xFFFF)

    # second offset field: a u32 inside the directory holding the old object-area end.
    # Leave it out and ISIS still opens the file, but rewrites it on save to repair things.
    off_b = data.find(struct.pack("<I", tail), dirpos)
    if off_b < 0:
        print("warning: object-area offset field (u32) not found; ISIS may rewrite on save")
    else:
        struct.pack_into("<I", data, off_b, tail + delta)

    count_off += delta
    data[count_off] = old_count + 1
    dirpos += delta

    ins = find_entry_anchor(data, dirpos)
    if ins is None:
        raise SystemExit("could not find where to append the directory entry")
    entry = struct.pack("<HHH", old_next, old_count + 1, 0) + bytes([len(new_ref)]) + new_ref + b"\x00" * 6
    data[ins:ins] = entry

    open(args.out, "wb").write(bytes(data))
    print("wrote %s: %d -> %d bytes (+%d, record %d + directory entry %d)"
          % (args.out, size0, len(data), len(data) - size0, delta, len(entry)))
    print("now open it in ISIS and save it again; if it survives, the edit was accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
