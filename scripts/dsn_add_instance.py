#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add another instance of a device the design already embeds, by writing the file.

**Verified.** Two placements with this script produce a file that differs from ISIS's own by
exactly the two-byte volatile stamp, and ISIS loads it. Getting there needed five things that
the first attempt missed:

* the record's anchor appears three times, once at +6 and again in the COMPONENT ID and
  COMPONENT VALUE blocks, the later two offset by 0.416 inch in y;
* the point that was clicked is stored too, about 380 bytes in, and must be patched - once;
  patching it by value alone rewrites an unrelated pair and the design crashes instead;
* the record carries its own object id and unit number at +396, little-endian;
* the entry's unit counter is little-endian, unlike the id and sequence at the head of the entry,
  which are big-endian;
* the record's last byte is the object-area sentinel `FF`, which the template's copy does not
  have because another record followed it there.

`\u201cUnit counter\u201d means the value the header already holds, not one more than it - the
stored value and the counter in the header are the same number, and the counter is incremented
afterwards. That off-by-one was the last five bytes.

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
                    # each pair is [len key][key][len value][value]
                    if p >= len(d) or not (1 <= d[p] <= 4):
                        ok = False
                        break
                    p += 1 + d[p]
                    if p >= len(d) or not (1 <= d[p] <= 4):
                        ok = False
                        break
                    p += 1 + d[p]
                if ok:
                    tail_len = 4 + (p - tail_start - 4) + 3
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
    # The instance's position is written three times inside the record - once in the header at
    # +6 and again in each of the COMPONENT ID and COMPONENT VALUE blocks - so patch every
    # occurrence of the template's own pair, not just the first.
    old_x, old_y = struct.unpack_from("<ii", rec, 6)
    new_x, new_y = int(round(x * UNITS)), int(round(y * UNITS))
    # A record also remembers the point that was clicked when it was placed, which sits a fixed
    # distance from the anchor: clicking stored the part 0.308 in right and 0.208 in below.
    click_dx, click_dy = int(0.308 * UNITS), int(-0.208 * UNITS)
    patched = 0
    patched_click = 0
    i = 0
    while i <= len(rec) - 8:
        vx = struct.unpack_from("<i", rec, i)[0]
        if vx == old_x:
            by = struct.unpack_from("<i", rec, i + 4)[0]
            if abs(by - old_y) < UNITS * 2:          # a relative copy of the same position
                struct.pack_into("<ii", rec, i, new_x, new_y + (by - old_y))
                patched += 1
        elif vx == old_x + click_dx and patched_click == 0:
            by = struct.unpack_from("<i", rec, i + 4)[0]
            if by == old_y + click_dy:               # the point that was clicked
                struct.pack_into("<ii", rec, i, new_x + click_dx, new_y + click_dy)
                patched += 1
                patched_click = 1
        i += 1
    print("patched the position at %d places in the record" % patched)

    id_counter = u16(d, head + 19)
    # the counter at head+21 is one ahead of what the record and the entry store, so the stored
    # value is the counter's own value, not the incremented one
    unit_counter = u16(d, head + 21)
    # the record carries its own object id and unit number too, as little-endian u16s 396 bytes
    # in for this record type; leaving them at the template's values is what the earlier attempts
    # did, and the design was refused for it
    if len(rec) > 400:
        struct.pack_into("<HH", rec, 396, id_counter, unit_counter)
    # the record's last byte is the object-area sentinel ISIS puts after the final object; the
    # template's copy of it is zero because a record followed it there
    rec[-1] = 0xFF
    part_records = len(re.findall(rb"\xff\x02[\x20-\x7e]{2}", d[head:tail])) + len(names)
    seq = 1 + part_records
    tail_bytes = b"\x00" * 5
    if pins:
        # big-endian here, unlike the entry's id and sequence, which are big-endian too but
        # written by pack() above - both orders appear in this file format and mixing them up
        # produces a design ISIS crashes on rather than merely rejects
        t = bytearray(struct.pack("<HH", unit_counter, len(pins)))
        for key, nums in pins:
            s = str(nums[unit_no - 1])
            t += bytes([len(key)]) + key.encode()
            t += bytes([len(s)]) + s.encode()
        tail_bytes = bytes(t) + b"\x00" * 3

    off_hit = d.find(struct.pack("<I", tail), tail)
    # The new entry goes after the last existing one. Anchoring on a marker like `#@CX0000`
    # looks right and is wrong: that one sits before ROOT1, so the entry lands in the middle of
    # the directory and ISIS rejects the file. The earlier scripts got away with it because in
    # those designs the last entry happened to be a graphic, whose five-byte tail the old
    # anchor could compute.
    last = ens[-1]
    anchor = last[0] + 8 + len(last[3]) + len(last[4])
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
    struct.pack_into("<H", d, head + 21, unit_counter + 1)
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
