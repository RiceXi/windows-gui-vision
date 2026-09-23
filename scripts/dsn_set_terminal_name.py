#!/usr/bin/env python3
"""Set the net name of a terminal inside a saved .DSN, by rewriting the file.

A terminal record is

    [0x09]["$TERPOWER"][0x0D][0x00][0xFF][len][name][anchor x][anchor y]
    [0x0A]["$TERGROUND"][0x0D][0x00][0xFF][len][name][anchor x][anchor y]

and an empty name is a zero length. Changing the name changes the file size, so every 32 bit
field that looks like an offset past the edit is shifted by the same amount - the object area
end at head-4, the pointers into the model blocks at the end, and the wire link fields. That
shift-what-points-past-the-edit rule is the same one the append tool uses.

    python dsn_set_terminal_name.py --design in.DSN --list
    python dsn_set_terminal_name.py --design in.DSN --anchor -1.6,2.6 --name VCC --out out.DSN
"""
import argparse
import re
import struct

UNITS = 2540000.0
MARKER = b"ISIS CIRCUIT FILE"


def terminals(d):
    head = d.find(MARKER)
    tail = d.find(MARKER, head + 1)
    out = []
    for m in re.finditer(b"[\t\n]\\$TER(POWER|GROUND)", d[head:tail]):
        o = head + m.start()
        kind = "$TER" + m.group(1).decode("latin1")
        cat = o + 1 + len(kind) + 3
        nlen = d[cat]
        name = d[cat + 1:cat + 1 + nlen].decode("latin1")
        x, y = struct.unpack_from("<ii", d, cat + 1 + nlen)
        out.append(dict(kind=kind, len_at=cat, name=name,
                        x=x / UNITS, y=y / UNITS, at=o))
    return out


def set_name(d, term, name):
    old = term["name"].encode("latin1")
    new = name.encode("latin1")
    start = term["len_at"]
    end = start + 1 + len(old)
    delta = len(new) - len(old)
    out = bytearray(d[:start]) + bytes([len(new)]) + new + bytearray(d[end:])
    if delta:
        for off in range(0, len(out) - 3):
            v = struct.unpack_from("<I", out, off)[0]
            if start < v <= len(d):
                struct.pack_into("<I", out, off, v + delta)
    return bytes(out), delta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--anchor")
    ap.add_argument("--name")
    ap.add_argument("--out")
    a = ap.parse_args()

    d = open(a.design, "rb").read()
    ts = terminals(d)
    if a.list:
        for i, t in enumerate(ts):
            print("%d  %-12s (%7.3f,%7.3f)  name=%r" % (i, t["kind"], t["x"], t["y"], t["name"]))
        return

    want = None
    if a.anchor:
        ax, ay = (float(v) for v in a.anchor.split(","))
        want = min(ts, key=lambda t: abs(t["x"] - ax) + abs(t["y"] - ay))
    if want is None:
        raise SystemExit("give --anchor x,y")
    if a.name is None:
        raise SystemExit("give --name")
    print("terminal %s at (%.3f,%.3f): %r -> %r"
          % (want["kind"], want["x"], want["y"], want["name"], a.name))
    out, delta = set_name(d, want, a.name)
    path = a.out or a.design
    open(path, "wb").write(out)
    print("wrote %s: %d bytes (%+d)" % (path, len(out), delta))


if __name__ == "__main__":
    main()
