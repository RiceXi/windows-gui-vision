#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append a part record to an existing Proteus design. Verified against ISIS 7.08 SP2.

This is the recipe that works, measured by comparing a design ISIS itself saved after placing
a part against the same edit written by a script. The insert is the easy half; the failures
are all in the bookkeeping, and one missing byte is enough for ISIS to reject the file
silently or crash on it:

  1. the record goes at the end of the object area, just before the second marker;
  2. the byte before the insertion point becomes 00;
  3. the u32 at head-4 must equal the new object-area end plus 48;
  4. the u32 in the directory equal to the old object-area end (it sits just before ROOT1)
     becomes the new one;
  5. the u8 entry count at ROOT1+12 is incremented and a directory entry is appended.

Written this way, the file differs from ISIS's own output in six bytes: two of them a volatile
stamp, two the reference name you asked for, and two fields nothing appears to validate.

Two things this cannot do yet. The base design has to already contain that part - the symbol
and model live in the design, and a part it has never held makes ISIS reject the file. And the
record has to be one without out-of-line references, which normally means a part placed in a
design that has no wires or script attached to it; a record with those attached crashes ISIS
when it is moved to another design.

    python dsn_append.py --base base.DSN --record donor.DSN --ref U5 --at -1.2,1.5 --out new.DSN
    python dsn_append.py --base base.DSN --lib dsn_lib.json --part NAND_2 --ref U6 --at 0,0 \\
           --out new.DSN

Check the result with scripts/design_loadcheck.ps1 before believing it.
"""
import argparse
import json
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"

# An object header is 02 <flags> <type name> 00, and a part record is FF 02 <two characters>.
# The next one of either marks the end of the record you are looking at.
OBJECT_TYPES = [b"WIRE", b"BUS WIRE", b"WIRE DOT", b"2D GRAPHIC", b"MARKER", b"VPROBE",
                b"IPROBE", b"ACTUATOR", b"INDICATOR", b"TERMINAL", b"GENERATOR",
                b"SCRIPT", b"SUBCIRCUIT", b"DEVICE", b"PIN"]


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def record_end(d, start, tail):
    """Where a part record stops.

    Records carry no obvious length field, but every object starts with an object header, so
    the next one is the boundary. Miss the `FF 02 <ref>` case and a record swallows its
    neighbour, which is what made the first version of this script produce files that looked
    plausible and crashed ISIS.
    """
    best = None
    for t in OBJECT_TYPES:
        m = re.compile(b"\x02." + re.escape(t) + b"\x00", re.DOTALL).search(d, start + 12, tail)
        if m and (best is None or m.start() < best):
            best = m.start()
    m = re.compile(rb"\xff\x02[\x20-\x7e][\x20-\x7e]").search(d, start + 12, tail)
    if m and (best is None or m.start() < best):
        best = m.start()
    return best if best is not None else tail


def entry_anchor(d, count_off):
    """The byte after the last directory entry.

    An entry is an 8-byte header, the name, then five zero bytes:

        [u16 id][u16 sequence][u16 0][u8 0][u8 name length][name][5 x 00]

    Checking this against base2.DSN and the entry ISIS itself appended in new1.DSN puts both
    at the same byte, which is how the format was pinned down.
    """
    last = None
    for m in re.finditer(rb"\x09P2C[0-9A-Fa-f]{6}", d[count_off:count_off + 4096]):
        last = count_off + m.start() + 1 + 9 + 5
    if last is None:
        for m in re.finditer(rb"\x0aP2C[0-9A-Fa-f]{7}", d[count_off:count_off + 4096]):
            last = count_off + m.start() + 1 + 10 + 5
    if last is None:
        for m in re.finditer(rb"\x02[URCLDQ]\d\x00", d[count_off:count_off + 4096]):
            last = count_off + m.start() + 1 + 2 + 5
    return last if last is not None else count_off + 1


def entry_seqs(d, count_off):
    """The sequence field of every directory entry, in order.

    Entries are [u16 id][u16 sequence][u16 0][u8 0][u8 name length][name][tail], and the tail
    length varies: five zero bytes for most objects, twenty-two for a multi-unit device, which
    carries a unit and pin map (`01 00 03 00 01 41 01 31 ...`). Walking them needs both the
    name length and the tail, so this reads the parts it can and stops rather than guessing.
    """
    out = []
    o = count_off + 1
    for _ in range(64):
        if o + 8 > len(d):
            break
        seq = struct.unpack_from(">H", d, o + 2)[0]
        ln = d[o + 7]
        out.append(seq)
        o += 8 + ln + 5
        if o >= len(d):
            break
    return out


def append(base, record, ref=None, out=None, ref_field_len=2, entry_tail=None):
    """Return (bytes, info). ref None means an unnamed object such as a wire.

    ref_field_len is how many bytes the record keeps its reference in: 2 for the parts a design
    from an older library carries (`FF 02 U1`), 4 for the ones the current library writes for a
    multi-unit device (`FF 04 U3:A`).

    entry_tail is what goes after the name in the directory entry. Most objects have five zero
    bytes there; a multi-unit device carries a unit and pin map instead
    (`01 00 03 00 01 41 01 31 ...` for 74LS00), and without it the instance has no symbol.
    """
    d = bytearray(base)
    head = d.find(MARKER)
    tail = d.find(MARKER, head + 1)
    if min(head, tail) < 0:
        raise SystemExit("not an ISIS design file: no ISIS CIRCUIT FILE markers")
    if ref is not None:
        if len(record) < 12 or record[0] != 0xFF or record[1] != ref_field_len:
            raise SystemExit("a named record starts with FF %02X <reference of %d characters>"
                             % (ref_field_len, ref_field_len))
        if len(ref) != ref_field_len:
            raise SystemExit("the reference must be exactly %d characters; record sizes cannot "
                             "change" % ref_field_len)

    rec = bytearray(record)
    if ref:
        rec[2:2 + ref_field_len] = ref.encode()

    off_hit0 = d.find(struct.pack("<I", tail), tail)
    if off_hit0 < 0:
        raise SystemExit("no u32 pointing at the object-area end; is this a saved design?")
    root = d.find(b"ROOT1", off_hit0)
    if root < 0:
        raise SystemExit("no ROOT1 marker after the directory")
    count_off0 = root + 12
    anchor0 = entry_anchor(d, count_off0)
    # Two counters sit just after the marker: the object id at head+19 and a second one at
    # head+21. ISIS bumps both when it adds an instance - measured 16,1 -> 17,2 -> 18,3 as three
    # units of one device were placed. The directory entry's id comes from the first of the two.
    new_id = u16(d, head + 19)
    n = len(rec)

    # Insert the record first. Every directory offset moves by the length of the record, and
    # writing the directory at its pre-insertion offsets lands inside the record itself.
    d[tail - 1] = 0x00
    d[tail:tail] = bytes(rec)
    new_tail = tail + n
    off_hit = off_hit0 + n
    count_off = count_off0 + n
    anchor = anchor0 + n

    struct.pack_into("<I", d, head - 4, new_tail + 48)
    struct.pack_into("<I", d, off_hit, new_tail)
    info = dict(head=head, tail=tail, new_tail=new_tail, count_off=count_off, off_hit=off_hit,
                anchor=anchor, new_id=new_id, record_len=n)

    if ref is not None:
        count = d[count_off]
        d[count_off] = count + 1
        tail = b"\x00" * 5 if entry_tail is None else entry_tail
        # seq is the part-entry number, not the raw entry count: 1, 2, 3, 4 as U1, U2, U3:A, U3:B
        # were placed, with the graphics entries (P2C...) left at zero.
        seq = 1 + sum(1 for e in entry_seqs(d, count_off0) if e)
        entry = (struct.pack(">HHH", new_id, seq, 0) + b"\x00"
                 + bytes([len(ref)]) + ref.encode() + tail)
        d[anchor:anchor] = entry
        struct.pack_into("<H", d, head + 19, new_id + 1)
        struct.pack_into("<H", d, head + 21, u16(d, head + 21) + 1)

    if out:
        open(out, "wb").write(bytes(d))
    return bytes(d), info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="the design to add to")
    ap.add_argument("--record", help="design to lift one record out of")
    ap.add_argument("--lib", help="library built by dsn_templates.py")
    ap.add_argument("--part", help="part name in that library")
    ap.add_argument("--trim", action="store_true",
                    help="cut the record at the next object header")
    ap.add_argument("--ref", required=True, help="two characters, unique in the design")
    ap.add_argument("--at", default="0,0", help="position in inches, for example -1.2,1.5")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.lib:
        lib = json.load(open(args.lib, encoding="utf-8"))["parts"]
        if args.part not in lib:
            raise SystemExit("no such part in the library: %s" % args.part)
        rec = bytes.fromhex(lib[args.part]["hex"])
    elif args.record:
        raw = open(args.record, "rb").read()
        s = raw.find(b"\xff\x02")
        if s < 0:
            raise SystemExit("no FF 02 record in that file")
        rec = raw[s:]
    else:
        raise SystemExit("give either --record or --lib/--part")

    if args.trim:
        e = record_end(bytearray(rec), 0, len(rec))
        print("record is %d bytes, trimmed to %d" % (len(rec), e))
        rec = rec[:e] + b"\xff"

    base = open(args.base, "rb").read()
    x, y = [float(v) for v in args.at.split(",")]
    rec = bytearray(rec)
    struct.pack_into("<ii", rec, 4, int(round(x * 2540000)), int(round(y * 2540000)))

    data, info = append(base, bytes(rec), args.ref, out=args.out)
    print("wrote %s: %d bytes, record %d bytes, reference %s"
          % (args.out, len(data), info["record_len"], args.ref))
    print("the base has to contain that part already, or ISIS will not load the result.")
    print("check it with scripts/design_loadcheck.ps1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
