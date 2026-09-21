#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lift part records out of existing .DSN designs into a reusable json library.

ISIS writes one `FF 02 <reference>` record per placed part, and that record carries the part
type, its position and its attribute values. A record cannot be synthesised - only ISIS writes
valid ones - so the library holds copies of records lifted from designs that already contain
the parts you want.

    python dsn_templates.py scan  <file or folder> [...]
    python dsn_templates.py build dsn_lib.json <file or folder> [...]
    python dsn_templates.py show  dsn_lib.json [part name]

One caveat about what comes out: records are split on `FF 02` markers, so the last part in a
design swallows everything that follows it. That is fine for a lookup table, and wrong for
cloning - see references/dsn-templates.md.
"""
import json
import os
import re
import struct
import sys

MARKER = b"ISIS CIRCUIT FILE"
COMP_VALUE = re.compile(rb"COMPONENT VALUE\x00\x00{0,6}\xFF(.)", re.DOTALL)
PART_TOKEN = re.compile(rb"\$[A-Z][A-Z0-9_]{2,24}")


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def object_area(d):
    marks = [m.start() for m in re.finditer(re.escape(MARKER), d)]
    if len(marks) < 2:
        return None
    return marks[0], marks[1]


def device_name(rec):
    """The part's library name, which lives in the COMPONENT VALUE field.

    Simulator primitives such as generators and instruments have no COMPONENT VALUE and are
    named `$NAME` instead, which is why both spellings show up in the listings.
    """
    m = COMP_VALUE.search(rec)
    if m:
        ln = m.group(1)[0]
        raw = rec[m.end():m.end() + ln]
        if ln and len(raw) == ln and all(32 <= c < 127 for c in raw):
            return raw.decode("latin1")
    m = PART_TOKEN.search(rec)
    return m.group().decode("latin1") if m else None


def records(path):
    """Yield (reference, part name, record bytes) for every `FF 02` record in the object area."""
    d = open(path, "rb").read()
    area = object_area(d)
    if area is None:
        return []
    a, b = area
    seg = d[a:b]
    starts = [m.start() for m in re.finditer(rb"\xFF\x02", seg)]
    out = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(seg)
        rec = seg[s:e]
        ref = rec[2:4]
        if not all(32 <= c < 127 for c in ref):
            continue
        name = device_name(rec)
        if not name:
            continue
        out.append((ref.decode("latin1"), name, rec))
    return out


def coords(rec):
    if len(rec) < 12:
        return None
    x, y = struct.unpack_from("<ii", rec, 4)
    return round(x / 2540000.0, 4), round(y / 2540000.0, 4)


def walk(targets):
    files = []
    for t in targets:
        if os.path.isdir(t):
            for root, _d, names in os.walk(t):
                for n in names:
                    if n.lower().endswith(".dsn"):
                        files.append(os.path.join(root, n))
        else:
            files.append(t)
    return files


def cmd_scan(targets):
    seen = {}
    for f in walk(targets):
        try:
            for ref, name, rec in records(f):
                seen.setdefault(name, []).append((os.path.basename(f), ref, len(rec)))
        except OSError:
            continue
    print("%d distinct parts found:" % len(seen))
    for name in sorted(seen):
        sample = seen[name][0]
        print("  %-18s %4d found   first %s ref=%s len=%d"
              % (name, len(seen[name]), sample[0], sample[1], sample[2]))
    return 0


def cmd_build(out, targets):
    lib = {"note": "instance records lifted from existing designs; clone only, never resize",
           "parts": {}, "wire": None}
    for f in walk(targets):
        try:
            for ref, name, rec in records(f):
                slot = lib["parts"].setdefault(name, {"ref": ref, "len": len(rec),
                                                      "source": os.path.basename(f),
                                                      "hex": rec.hex()})
                # prefer a record whose coordinates sit on the 0.001 inch grid: those are the
                # ones placed by hand rather than copied by an earlier script
                c = coords(rec)
                if c and all(abs(v * 1000 - round(v * 1000)) < 0.01 for v in c):
                    slot["source"] = os.path.basename(f)
                    slot["hex"] = rec.hex()
                    slot["ref"] = ref
        except OSError:
            continue
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(lib, fh)
    print("library %s: %d parts, %.1f KB" % (out, len(lib["parts"]),
                                             os.path.getsize(out) / 1024.0))
    return 0


def cmd_show(path, name=None):
    lib = json.load(open(path, encoding="utf-8"))
    names = [name] if name else sorted(lib["parts"])
    for n in names:
        if n not in lib["parts"]:
            print("no such part: %s" % n)
            continue
        p = lib["parts"][n]
        rec = bytes.fromhex(p["hex"])
        print("%-18s ref=%-3s len=%-6d coords=%s source=%s"
              % (n, p["ref"], p["len"], coords(rec), p["source"]))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "scan":
        sys.exit(cmd_scan(a[1:]))
    if a[0] == "build":
        sys.exit(cmd_build(a[1], a[2:]))
    if a[0] == "show":
        sys.exit(cmd_show(a[1], a[2] if len(a) > 2 else None))
    raise SystemExit(__doc__)
