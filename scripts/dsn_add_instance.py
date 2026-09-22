#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add another instance of a device the design already embeds, by writing the file.

**Status: not accepted yet.** The field values this produces agree with ISIS's own output -
name, id, sequence, unit counter, pin map all match - but ISIS rejects the file on load, so the
directory entry is still going in the wrong place or at the wrong length. Measured: for two
placements ISIS inserts 65 bytes of entry where this writes 59, and its insert lands some 240
bytes earlier in the file than the end of the entry list this parser finds. Kept because the
rules below are right and the remaining gap is narrow; do not use it on a design you need.

Measured against ISIS 7.08 SP2, which is fussier here than anywhere else in this folder. Placing
the same device five times in a row gave five samples to copy, and every field turned out to
have a rule:

* the name continues the same physical package - `U3:A`, `U3:B`, `U3:C`, `U3:D` - and only then
  opens a new one, `U4:A`;
* the directory entry is
  `[u16 id][u16 sequence][u16 0][u8 0][u8 name length][name][tail]`, where id comes from the
  object counter at head+19, sequence counts part entries only (1 for the first part, 2 for the
  second, graphics entries stay 0), and the tail is six zero bytes for a single-unit device or,
  for a multi-unit one, `[u16 unit counter][u16 pins per unit]` followed by the pin numbers of
  that unit - "A" then "B" then "Y" - which have to be read out of the device's own PINOUT block
  because unit C lists them reversed;
* the unit counter is global, not per package: it ran 1,2,3,4,5 across `U3:A` to `U4:A`;
* the object counter at head+19 and the object-area end field at head-4 move as usual.

    python dsn_add_instance.py --base design.DSN --device 74LS00 --at -3.9,-2.5 --out new.DSN
"""
import argparse
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"
UNITS = 2540000


def u16(b, o, big=False):
    return struct.unpack_from(">H" if big else "<H", b, o)[0]


def entries(d, count_off):
    """Every directory entry as (offset, id, sequence, name, tail)."""
    out = []
    o = count_off + 1
    while o + 8 <= len(d):
        eid = u16(d, o, big=True)
        seq = u16(d, o + 2, big=True)
        ln = d[o + 7]
        name = d[o + 8:o + 8 + ln]
        if not all(32 <= c < 127 for c in name):
            break
        tail_start = o + 8 + ln
        if b"P2C" in name:
            tail_len = 5
        else:
            # A part entry either ends in five zero bytes or, for a multi-unit device, carries
            # `[u16 unit counter][u16 pins per unit]` and then that many length-prefixed pin
            # numbers before six zero bytes.
            # the id and sequence at the head of an entry are big-endian, but the two fields
            # here are little-endian: 01 00 03 00 is unit 1 with three pins per unit
            unit_counter = u16(d, tail_start)
            per_unit = u16(d, tail_start + 2)
            tail_len = 5
            if 1 <= unit_counter <= 64 and 1 <= per_unit <= 32:
                p = tail_start + 4
                ok = True
                for _ in range(per_unit):
                    if p >= len(d) or not (1 <= d[p] <= 4):
                        ok = False
                        break
                    p += 1 + d[p]
                if ok:
                    tail_len = 4 + (p - tail_start - 4) + 6
        out.append((o, eid, seq, name.decode("latin1"), d[tail_start:tail_start + tail_len]))
        o = tail_start + tail_len
    return out


def pinout(d):
    """(elements, [(pin name, [pin number per unit])]) from the device's PINOUT block."""
    m = re.search(rb"PINOUT [A-Za-z0-9]+\n\nELEMENTS=(\d+)\nPINS=\d+\n\n(.*?)\n\n",
                  d, re.S)
    if not m:
        return None, []
    elements = int(m.group(1))
    pins = []
    for line in m.group(2).split(b"\n"):
        pm = re.match(rb"(?:IP|OP|PP)\s*\(?([A-Za-z0-9_]+)\)?\s*=\s*([0-9,\s]+)", line)
        if not pm:
            continue
        nums = [int(x) for x in re.findall(rb"\d+", pm.group(2))]
        if len(nums) == elements:
            pins.append((pm.group(1).decode("latin1"), nums))
    return elements, pins


def append_instance(base, device, x, y, out=None):
    d = bytearray(base)
    head = d.find(MARKER)
    tail = d.find(MARKER, head + 1)
    dirpos = d.rfind(b"OBJECT DATA")
    root = d.find(b"ROOT1", dirpos)
    count_off = root + 12
    ens = entries(d, count_off)

    # an existing instance of the same device gives the record template and the prefix
    src = None
    names = [m for m in re.finditer(rb"\xff\x04([A-Za-z]{1,3}\d+:[A-Z])", d[head:tail])]
    for nm in names:
        name = nm.group(1).decode("latin1")
        rec_off = head + nm.start()
        ids = re.search(rb"COMPONENT ID\x00\x00{0,6}\xFF(.)([\x20-\x7e]{1,24})",
                        d[rec_off:rec_off + 600])
        if ids and ids.group(2).decode("latin1") == device:
            # the record ends where the next instance record begins, not at the object-area end
            nxt = re.search(rb"\xff\x04[A-Za-z]{1,3}\d+:[A-Z]", d[rec_off + 4:tail])
            end = rec_off + 4 + nxt.start() if nxt else tail
            src = (rec_off, name, d[rec_off:end])
            break
    if src is None:
        raise SystemExit("no instance of %s in this design to copy" % device)
    rec_off, src_name, rec = src

    prefix = re.match(r"([A-Za-z]+)(\d+):([A-Z])", src_name)
    if not prefix:
        raise SystemExit("cannot read the reference style of %s" % src_name)
    pre, pkg, unit = prefix.group(1), int(prefix.group(2)), prefix.group(3)
    elements, pins = pinout(d)
    if elements is None:
        raise SystemExit("no PINOUT block: this design does not embed the device's pins")

    # next unit of the same package, or the first unit of a new one
    used = {m.group(1).decode("latin1").split(":")[1] for m in names}
    packages = [int(m.group(1).decode("latin1").split(":")[0][len(pre):]) for m in names]
    pkg = max(packages)
    used = {n.split(":")[1] for n in
            [m.group(1).decode("latin1") for m in names]
            if n.startswith("%s%d:" % (pre, pkg))}
    unit_no = max([ord(u) - 64 for u in used] or [0]) + 1
    if unit_no > elements:
        pkg += 1
        unit_no = 1
    unit = chr(64 + unit_no)
    name = "%s%d:%s" % (pre, pkg, unit)
    print("next instance: %s (package %d, unit %d of %d)" % (name, pkg, unit_no, elements))

    rec = bytearray(rec)
    rec[2:2 + len(src_name)] = name.encode()
    struct.pack_into("<ii", rec, 6, int(round(x * UNITS)), int(round(y * UNITS)))

    id_counter = u16(d, head + 19)
    unit_counter = u16(d, head + 21) + 1
    part_records = len(re.findall(rb"\xff\x02[\x20-\x7e]{2}", d[head:tail])) + len(names)
    seq = 1 + part_records
    tail_bytes = b"\x00" * 5
    if pins:
        t = bytearray(struct.pack(">HH", unit_counter, len(pins)))
        for key, nums in pins:
            s = str(nums[unit_no - 1])
            t += bytes([len(s)]) + s.encode()
        tail_bytes = bytes(t) + b"\x00" * 6

    off_hit = d.find(struct.pack("<I", tail), tail)
    # the entry list ends where the next section starts, marked by a length-prefixed string
    anchor = d.find(b"\x08#@CX0000", root)
    if anchor < 0:
        raise SystemExit("cannot find the end of the directory entry list")
    d[tail - 1] = 0x00
    d[tail:tail] = bytes(rec)
    struct.pack_into("<I", d, head - 4, tail + len(rec) + 48)
    struct.pack_into("<I", d, off_hit + len(rec), tail + len(rec))
    count = d[count_off + len(rec)]
    d[count_off + len(rec)] = count + 1
    entry = (struct.pack(">HHH", id_counter, seq, 0) + b"\x00" + bytes([len(name)])
             + name.encode() + tail_bytes)
    d[anchor + len(rec):anchor + len(rec)] = entry
    struct.pack_into("<H", d, head + 19, id_counter + 1)
    struct.pack_into("<H", d, head + 21, unit_counter)
    if out:
        open(out, "wb").write(bytes(d))
    return bytes(d), dict(name=name, seq=seq, id=id_counter, unit_counter=unit_counter,
                          record_len=len(rec), entry_len=len(entry))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--device", required=True, help="the COMPONENT ID to copy, e.g. 74LS00")
    ap.add_argument("--at", required=True, help="x,y in inches; this is the anchor, not the "
                                               "point you would click")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    x, y = [float(v) for v in args.at.split(",")]
    base = open(args.base, "rb").read()
    data, info = append_instance(base, args.device, x, y, out=args.out)
    print("wrote %s: %d bytes; %s id=%d seq=%d unit counter=%d record=%d entry=%d"
          % (args.out, len(data), info["name"], info["id"], info["seq"],
             info["unit_counter"], info["record_len"], info["entry_len"]))
    print("check it with scripts/design_loadcheck.ps1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
