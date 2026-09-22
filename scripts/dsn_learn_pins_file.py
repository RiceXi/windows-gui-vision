#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Learn a device's pin offsets from designs that already have wires on them.

No clicking: a part's record ends with four slots, one per pin (slot 1 is the part's first pin, and
so on), and each non-zero slot holds the tail-block offset of the wire attached to that pin. The
wire's own points are in the file, so the endpoint that sits on the pin is the pin position, and
subtracting the instance's own anchor gives a symbol-relative offset that can be reused for any
other instance of the same device.

    python dsn_learn_pins_file.py design1.DSN design2.DSN ... > pinmap.json

The result is checked by hand against what is already known for the 74LS00 units in this project
(unit A: A at (-0.5,+0.1), Y at (+0.5,0.0) relative to the anchor).
"""
import json
import re
import struct
import sys

U = 2540000.0
PREFIX = bytes.fromhex("ffffff00ffffff00")
BIG = 1.6           # a pin has to be within this many inches of the instance's anchor


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def i32(b, o):
    return struct.unpack_from("<i", b, o)[0]


def wires(d, head, tail):
    out = []
    for m in re.finditer(rb"\x02\x7fWIRE\x00", d[head:tail]):
        o = head + m.start()
        if d[o - 8:o] != PREFIX:
            continue
        n = u16(d, o + 9)
        if n > 64 or o + 11 + 8 * n + 15 > tail:
            continue
        pts = [struct.unpack_from("<ii", d, o + 11 + 8 * i) for i in range(n)]
        out.append(dict(obj=o, n=n, points=pts, body=o + 11 + 8 * n))
    return out


def learn(path):
    d = open(path, "rb").read()
    head = d.find(b"ISIS CIRCUIT FILE")
    tail = d.find(b"ISIS CIRCUIT FILE", head + 1)
    if min(head, tail) < 0:
        return {}
    ws = wires(d, head, tail)
    # a slot holds the offset of the 15 byte tail block that sits immediately in front of the
    # wire's own prefix, i.e. wire.object - 8 - 15
    by_tail = {}
    for w in ws:
        by_tail[w["obj"] - 23] = w
    out = {}
    for m in re.finditer(rb"\xff\x04([0-9A-Za-z]+:[A-D])", d[head:tail]):
        start = head + m.start()
        ref = m.group(1).decode()
        device = ""
        mm = re.search(rb"\xff\x06([ -~]{2,24})", d[start:start + 380])
        if mm:
            device = mm.group(1).decode()
        anchor = (i32(d, start + 384) / U, i32(d, start + 388) / U)
        # Slots at +407, +411, +415 are pin 1, 2, 3; the fourth four-byte word (+419) is the start
        # of the next object, not a pin. A single wire can appear in two slots - that happens when
        # its two ends are pins of the *same* part - so the ends are collected first and handed out
        # in pin order afterwards.
        attached = []
        for i in range(1, 4):
            slot = u32(d, start + 403 + 4 * i)
            if slot == 0:
                continue
            w = by_tail.get(slot)
            if w is None:
                # some saves put the wire's own body offset in the slot instead
                cand = [w2 for w2 in ws if slot == w2["body"]]
                w = cand[0] if cand else None
            if w is None:
                continue
            attached.append((i, [(x / U, y / U) for x, y in w["points"]]))

        # The interactive point of a pin is the end of its own short stub, and a wire that reaches a
        # pin ends exactly there. One wire can carry two pins of the same part (an input and the
        # output of one gate), so what counts is every end of every attached wire that sits within
        # the symbol; those ends are handed out in the symbol's pin order, left column first.
        ends = {}
        for i, pts in attached:
            for p in (pts[0], pts[-1]):
                if abs(p[0] - anchor[0]) <= BIG and abs(p[1] - anchor[1]) <= BIG:
                    ends.setdefault((round(p[0], 3), round(p[1], 3)), set()).add(i)
        slots_used = sorted(set(i for i, _ in attached))
        ordered = sorted(ends.keys(), key=lambda p: (p[0], -p[1]))
        pins = []
        for idx, (ex, ey) in enumerate(ordered):
            slot_i = slots_used[idx] if idx < len(slots_used) else slots_used[-1]
            pts = attached[0][1]
            off = [round(ex - anchor[0], 3), round(ey - anchor[1], 3)]
            if abs(off[0]) > BIG or abs(off[1]) > BIG:
                continue
            pins.append(dict(pin=slot_i, offset=off, at=[ex, ey],
                             ends=[[round(pts[0][0], 3), round(pts[0][1], 3)],
                                   [round(pts[-1][0], 3), round(pts[-1][1], 3)]]))
        if pins:
            out.setdefault(device, {})[ref] = dict(anchor=[round(anchor[0], 3), round(anchor[1], 3)],
                                                   pins=pins)
    return out


def main():
    learned = {}
    for path in sys.argv[1:]:
        got = learn(path)
        for device, refs in got.items():
            learned.setdefault(device, {}).update(refs)
    json.dump(learned, sys.stdout, indent=1, sort_keys=True)
    sys.stderr.write("devices: %s\n" % ", ".join(sorted(learned)))


if __name__ == "__main__":
    main()
