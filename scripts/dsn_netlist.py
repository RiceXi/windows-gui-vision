#!/usr/bin/env python3
"""Read the connections out of a saved .DSN: nets, what is on them, and what is dangling.

The file already holds everything needed to answer "did the wire land on the pin":

* each part instance is a record with a name and an anchor;
* each terminal ($TERPOWER / $TERGROUND) carries its net name - VCC, GND, +5V... - which is
  what makes a power net a power net rather than an anonymous wire;
* each wire is a polyline of design-inch points.

Two wires are on the same net when they share a point that is an endpoint of one of them, or a
vertex of both (a tap). A point that belongs to only one wire end is dangling - which is exactly
the shape of "I clicked a pin, then clicked empty space": the pin end is real, the other end
belongs to nothing.

    python dsn_netlist.py design.DSN
    python dsn_netlist.py design.DSN --near 3.592,0.908 --radius 0.6
"""
import argparse
import re
import struct

UNITS = 2540000.0
MARKER = b"ISIS CIRCUIT FILE"
EPS = 0.002                     # 0.002 inch = a fifth of a pixel at 100 px/in


def read(path):
    d = open(path, "rb").read()
    head = d.find(MARKER)
    tail = d.find(MARKER, head + 1)
    return d, head, tail


def parts(d, head, tail):
    """Instance names and anchors.

    A device definition and an instance carry the same kind of record, so the name is what tells
    them apart: an instance is a reference designator - `U1`, `SW1`, `R1` or a unit of one,
    `U2:A`. Device names in this file are words or hyphenated part numbers (`RES`, `10k`,
    `SW-SPST`, `LOGICPROBE`, `TLE2425`) and none of those match.
    """
    out = {}
    # [0xFF][length][name][anchor x][anchor y]. The length byte is what makes this exact: a
    # greedy match runs past the name into the anchor bytes and reads it as "U2:A`7".
    i = head
    while i < tail - 2:
        if d[i] != 0xFF:
            i += 1
            continue
        ln = d[i + 1]
        if not 2 <= ln <= 8:
            i += 1
            continue
        name = d[i + 2:i + 2 + ln]
        if not all(32 <= c < 127 for c in name):
            i += 1
            continue
        name = name.decode("latin1")
        if not re.match(r"^[A-Za-z]{1,3}\d+(:[A-Z])?$", name):
            i += 1
            continue
        x, y = struct.unpack_from("<ii", d, i + 2 + ln)
        if abs(x) < 60 * UNITS and abs(y) < 60 * UNITS:
            out[name] = (x / UNITS, y / UNITS)
        i += 2 + ln
    return out


def terminals(d, head, tail):
    out = []
    for m in re.finditer(b"[\t\n]\\$TER(POWER|GROUND)", d[head:tail]):
        o = head + m.start()
        kind = "$TER" + m.group(1).decode("latin1")
        cat = o + 1 + len(kind) + 3
        nlen = d[cat]
        name = d[cat + 1:cat + 1 + nlen].decode("latin1", "replace")
        x, y = struct.unpack_from("<ii", d, cat + 1 + nlen)
        out.append((name or "(unnamed)", kind, x / UNITS, y / UNITS))
    return out


def wires(d, head, tail):
    out = []
    for m in re.finditer(rb"\x02\x7fWIRE\x00", d[head:tail]):
        o = head + m.start()
        n = struct.unpack_from("<H", d, o + 9)[0]
        if n > 64 or o + 11 + 8 * n > len(d):
            continue
        pts = [(struct.unpack_from("<ii", d, o + 11 + 8 * i)[0] / UNITS,
                struct.unpack_from("<ii", d, o + 11 + 8 * i)[1] / UNITS) for i in range(n)]
        out.append(pts)
    return out


def same(a, b):
    return abs(a[0] - b[0]) < EPS and abs(a[1] - b[1]) < EPS


def device_of(d, head, tail):
    """{instance name: device name} read from each record's own COMPONENT ID block."""
    out = {}
    starts = []
    i = head
    while i < tail - 2:
        if d[i] != 0xFF:
            i += 1
            continue
        ln = d[i + 1]
        if not 2 <= ln <= 8:
            i += 1
            continue
        raw = d[i + 2:i + 2 + ln]
        if not all(32 <= c < 127 for c in raw):
            i += 1
            continue
        name = raw.decode("latin1")
        if not re.match(r"^[A-Za-z]{1,3}\d+(:[A-Z])?$", name):
            i += 1
            continue
        starts.append((i, name))
        i += 2 + ln
    # a record runs from its name to the next record's name, so the COMPONENT ID found in that
    # span belongs to this instance and not to the one after it
    for k, (o, name) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else tail
        blk = d.find(b"COMPONENT ID", o, end)
        if blk < 0:
            continue
        # the device name can run past the next record's start, so do not clamp the window to
        # the record boundary - that cut "TLE2425" in half and made the match fail. And read the
        # name by its length byte: a greedy match swallows the first byte of the next field
        # ("74LS00`") and then fails the length check.
        m = re.search(rb"\xff([\x02-\x14])", d[blk:blk + 80])
        if m:
            dev_len = m.group(1)[0]
            dev_raw = d[blk + m.end():blk + m.end() + dev_len]
            if len(dev_raw) == dev_len and all(32 <= c < 127 for c in dev_raw):
                out[name] = dev_raw.decode("latin1")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--near")
    ap.add_argument("--radius", type=float, default=0.8)
    ap.add_argument("--pins", action="store_true",
                    help="wire-end offsets around each part, grouped by device type")
    a = ap.parse_args()

    d, head, tail = read(a.design)
    ws = wires(d, head, tail)
    ps = parts(d, head, tail)
    ts = terminals(d, head, tail)

    # union-find over wires: two wires join when an end of one sits on the other
    parent = list(range(len(ws)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i, wi in enumerate(ws):
        for j, wj in enumerate(ws):
            if i >= j:
                continue
            joined = any(same(p, q) for p in (wi[0], wi[-1]) for q in wj)
            if joined:
                union(i, j)

    nets = {}
    for i, wi in enumerate(ws):
        nets.setdefault(find(i), []).append(i)

    print("== %s: %d wires, %d parts, %d terminals" % (a.design, len(ws), len(ps), len(ts)))
    for k, idx in sorted(nets.items(), key=lambda kv: -len(kv[1])):
        pts = []
        for i in idx:
            pts += ws[i]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        labels = [n for (n, kind, x, y) in ts if any(same((x, y), p) for p in pts)]
        print("  net %s: %d wire(s), %d point(s), x %.2f..%.2f y %.2f..%.2f%s"
              % (("[" + ",".join(labels) + "]") if labels else "",
                 len(idx), len(pts), min(xs), max(xs), min(ys), max(ys),
                 "  <-- power" if labels else ""))

    # dangling ends: an end that is on no other wire's point at all
    # a wire end is *placed* when it sits on a known device pin or on another wire; anything else
    # is a loose end, which is what "clicked a pin then clicked empty space" leaves behind
    try:
        import dsn_pins_table as _pins
    except Exception:
        _pins = None
    devs = device_of(d, head, tail)

    def on_a_pin(end):
        if _pins is None:
            return None
        for pname, (px, py) in ps.items():
            dev = devs.get(pname)
            if dev not in _pins.TABLE:
                continue
            for label, (ox, oy) in _pins.TABLE[dev].items():
                if same(end, (px + ox, py + oy)):
                    return "%s.%s" % (pname, label)
        return None

    print("  loose wire ends (not on any wire):")
    n_dangling = 0
    for i, wi in enumerate(ws):
        for end in (wi[0], wi[-1]):
            others = [p for j, wj in enumerate(ws) if j != i for p in wj]
            if not any(same(end, p) for p in others):
                n_dangling += 1
                pin = on_a_pin(end)
                near = [(nm, round((end[0] - x) ** 2 + (end[1] - y) ** 2, 3))
                        for nm, (x, y) in ps.items()
                        if abs(end[0] - x) < 1.0 and abs(end[1] - y) < 1.0]
                near += [(nm, round((end[0] - x) ** 2 + (end[1] - y) ** 2, 3))
                         for nm, kind, x, y in ts
                         if abs(end[0] - x) < 1.5 and abs(end[1] - y) < 1.5]
                near.sort(key=lambda t: t[1])
                print("    (%.3f,%.3f)  %s  nearest: %s"
                      % (end[0], end[1],
                         ("ON PIN %s" % pin) if pin else "not on a known pin",
                         ", ".join(nm for nm, _ in near[:3]) or "-"))
    if n_dangling == 0:
        print("    none")

    if a.near:
        x, y = (float(v) for v in a.near.split(","))
        print("  wire ends within %.2f inch of (%.3f,%.3f):" % (a.radius, x, y))
        for i, wi in enumerate(ws):
            for end in (wi[0], wi[-1]):
                if abs(end[0] - x) < a.radius and abs(end[1] - y) < a.radius:
                    print("    wire %d end (%+.3f,%+.3f) offset (%+.3f,%+.3f)"
                          % (i, end[0], end[1], end[0] - x, end[1] - y))

    if a.pins:
        print("  wire ends around each part (candidate pins), by device:")
        dev = device_of(d, head, tail)
        by_dev = {}
        for name, (px, py) in sorted(ps.items()):
            ends = []
            for wi in ws:
                for end in (wi[0], wi[-1]):
                    if abs(end[0] - px) < 1.0 and abs(end[1] - py) < 1.0:
                        ends.append((round(end[0] - px, 3), round(end[1] - py, 3)))
            print("    %-8s %-12s anchor (%+.3f,%+.3f)  ends %s"
                  % (dev.get(name, "?"), name, px, py, ends or "-"))
            by_dev.setdefault(dev.get(name, "?"), []).append(set(ends))
        print("  offsets seen on every instance of a device (those are pins):")
        for dname, sets in by_dev.items():
            if len(sets) < 2:
                continue
            common = set.intersection(*sets) if sets else set()
            for off in sorted(common):
                print("    %-12s %s" % (dname, off))


if __name__ == "__main__":
    main()
