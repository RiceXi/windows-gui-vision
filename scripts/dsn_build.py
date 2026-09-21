#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EXPERIMENTAL: assemble a design from a json circuit description. It does not work yet.

Every file this produced failed to load in ISIS 7.08 SP2, even when the part records came from
the base design itself. Inserting a record changes the size of the object area, and something
in the file validates that - see the re-test in references/dsn-generate.md. The script is here
anyway because the parts that are correct are the tedious ones: the record lookup, the wire
record, and the four length fields that have to be maintained. Whoever finds the missing field
can start from this.

    python dsn_build.py --base skeleton.DSN --lib dsn_lib.json --circuit c.json --out new.DSN

The circuit description is inches with the origin at the sheet centre, on the 0.1 inch grid:

    {
      "parts": [{"device": "RESISTOR", "ref": "R1", "x": 1.0, "y": 2.0}],
      "wires": [{"points": [[1.0, 2.0], [2.0, 2.0]]}]
    }

References must be exactly two characters long. Nothing in a record may change size.
"""
import argparse
import json
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


class Design:
    def __init__(self, path):
        self.d = bytearray(open(path, "rb").read())
        d = self.d
        self.head = d.find(MARKER)
        self.tail = d.find(MARKER, self.head + 1)
        if min(self.head, self.tail) < 0:
            raise SystemExit("no ISIS CIRCUIT FILE markers: that base is not a design")
        self.dirpos = d.rfind(b"OBJECT DATA")
        root = d.find(b"ROOT1", self.dirpos)
        self.count_off = root + 12
        self.end_field = self._find_end_field()

    def devices(self):
        """Parts already present in the base design.

        The records this script inserts only say where a part sits and what it is worth; the
        symbol and the model live in the design. Inserting a part the base has never contained
        gave a design ISIS would not open, so this check runs first and the script refuses
        rather than writing a file that looks fine and does not load.
        """
        d = self.d
        names = set()
        for m in re.finditer(rb"COMPONENT VALUE\x00\x00{0,6}\xFF(.)", d, re.DOTALL):
            ln = m.group(1)[0]
            raw = bytes(d[m.end():m.end() + ln])
            if ln and len(raw) == ln and all(32 <= c < 127 for c in raw):
                names.add(raw.decode("latin1"))
        for m in re.finditer(rb"\$[A-Z][A-Z0-9_]{2,24}", d):
            names.add(m.group().decode("latin1"))
        return names

    def _find_end_field(self):
        """The u16 whose value is the object-area end plus 48, found by search.

        In small designs it sits a few bytes before the first marker; on a 55 KB design the
        value at that position was something else entirely, so search the whole header instead
        of a fixed window.
        """
        want = (self.tail + 48) & 0xFFFF
        hits = [o for o in range(512, self.head - 1) if u16(self.d, o) == want]
        if not hits:
            raise SystemExit("no u16 equal to object-area end + 48 in the header")
        return hits[-1]

    def _entry_anchor(self):
        """End of the directory's entry list.

        ISIS names objects it creates itself P2C plus six hex digits; the entry shape is
        [u8 length][name][6 x 00]. A design with no entries at all falls back to the byte
        after the entry count.
        """
        last = None
        for m in re.finditer(rb"\x09P2C[0-9A-Fa-f]{6}", self.d[self.dirpos:]):
            last = m.start() + self.dirpos
        if last is None:
            for m in re.finditer(rb"\x0aP2C[0-9A-Fa-f]{7}", self.d[self.dirpos:]):
                last = m.start() + self.dirpos
        if last is None:
            return self.count_off + 1
        return last + 1 + 9 + 6

    def insert(self, rec, ref=None):
        d = self.d
        old_tail = self.tail
        d[old_tail:old_tail] = rec
        self.tail = old_tail + len(rec)
        # Growing the object area pushes the whole directory back, so the offsets this object
        # remembers have to move with it. Editing the directory at its pre-insertion offsets is
        # how you corrupt the record you just wrote.
        self.dirpos += len(rec)
        self.count_off += len(rec)
        d[old_tail - 1] = 0x00
        struct.pack_into("<H", d, self.end_field, (self.tail + 48) & 0xFFFF)
        off_b = d.find(struct.pack("<I", old_tail), self.dirpos)
        if off_b < 0:
            raise SystemExit("the object-area offset field in the directory is missing")
        struct.pack_into("<I", d, off_b, self.tail)
        if ref is None:
            return
        obj_id = u16(d, self.head + 19)
        struct.pack_into("<H", d, self.head + 19, obj_id + 1)
        count = d[self.count_off]
        d[self.count_off] = count + 1
        ins = self._entry_anchor()
        entry = (struct.pack("<HHH", obj_id, count + 1, 0)
                 + bytes([len(ref.encode())]) + ref.encode() + b"\x00" * 6)
        d[ins:ins] = entry

    def save(self, path):
        open(path, "wb").write(bytes(self.d))


def wire_record(points):
    """Inches in, one WIRE record out. Wires are not named, so they get no directory entry."""
    out = bytearray(b"\x02\x7fWIRE\x00")
    out += b"\x00\x00"
    out += struct.pack("<H", len(points))
    for x, y in points:
        out += struct.pack("<ii", int(round(x * 2540000)), int(round(y * 2540000)))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="base design; new parts are appended to it")
    ap.add_argument("--lib", required=True, help="library built by dsn_templates.py")
    ap.add_argument("--circuit", required=True, help="circuit description json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lib = json.load(open(args.lib, encoding="utf-8"))["parts"]
    spec = json.load(open(args.circuit, encoding="utf-8"))
    des = Design(args.base)

    missing = sorted({p["device"] for p in spec.get("parts", []) if p["device"] not in lib})
    if missing:
        print("not in the library: %s" % ", ".join(missing))
        print("Place the part once in ISIS, save, then rebuild the library over that design.")
        return 2

    have = des.devices()
    absent = sorted({p["device"] for p in spec.get("parts", []) if p["device"] not in have})
    if absent:
        print("not in the base design: %s" % ", ".join(absent))
        print("The symbol and model for a part live in the design, so use a base that already")
        print("contains it - open that design, place the part, and save it as the base.")
        return 4

    for p in spec.get("parts", []):
        tpl = lib[p["device"]]
        rec = bytearray.fromhex(tpl["hex"])
        ref = p["ref"].encode()
        if len(ref) != 2:
            print("references have to be exactly two characters: %s" % p["ref"])
            return 3
        rec[2:4] = ref
        struct.pack_into("<ii", rec, 4,
                         int(round(p["x"] * 2540000)), int(round(p["y"] * 2540000)))
        des.insert(bytes(rec), ref.decode())
        print("part %-6s %-18s at (%5.2f, %5.2f)   %d bytes"
              % (p["ref"], p["device"], p["x"], p["y"], len(rec)))

    for i, w in enumerate(spec.get("wires", []), 1):
        rec = wire_record(w["points"])
        des.insert(rec)
        print("wire W%-5d %d points, %d bytes" % (i, len(w["points"]), len(rec)))

    if args.dry_run:
        print("dry run, nothing written")
        return 0
    des.save(args.out)
    print("wrote %s (%d bytes, %d parts, %d wires)"
          % (args.out, len(des.d), len(spec.get("parts", [])), len(spec.get("wires", []))))
    print("WARNING: files built this way did not load in ISIS 7.08 SP2 when tested. Check the")
    print("window title after opening - if it does not gain the file name, it did not load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
