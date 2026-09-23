#!/usr/bin/env python3
"""List the pins a device's definition block carries, in design inches from the symbol origin.

Each pin in a symbol definition is a record like

    00 01 0A 00 00 [int32 x][int32 y] 00 00 00 00 "$PINDEFAULT" 00 "A" 00 "1"

with the pin name and number as length-prefixed strings right after it, and the whole cluster
sits in front of the `[NAME]+` marker of the device it belongs to. The coordinates are the ones a
placed instance needs: pin screen point = instance anchor + these offsets, which is what makes a
netlist of coordinates possible.

    python dsn_device_pins.py design.DSN
    python dsn_device_pins.py design.DSN --device 74LS00
"""
import argparse
import re
import struct

UNITS = 2540000.0


def devices(d):
    """{name: [(pin, number, x, y), ...]} for every device defined in the design's header."""
    head = d.find(b"ISIS CIRCUIT FILE")
    out = {}
    pending = []
    marker = re.compile(rb"\[([A-Za-z0-9_+\-]+)\]\+.{0,12}\*PINOUT", re.S)
    for m in re.finditer(rb"(\x01)?\x0a\x00\x00(.{4})(.{4})", d[:head], re.S):
        # the run of bytes just before a pin name block: [.. 0A 00 00][x][y]
        tail = d[m.end():m.end() + 40]
        names = re.match(
            rb".{0,8}\x00(\$PIN[A-Z]+)\x00([\x20-\x7e]{1,4})\x00([\x20-\x7e]{1,6})\x00", tail)
        short = re.match(rb".{0,8}\x00(\$PINSHORT)\x00?", tail)
        if not names and not short:
            continue
        if names:
            kind = names.group(1).decode("latin1")
            pin, num = names.group(2).decode("latin1"), names.group(3).decode("latin1")
        else:
            # a short pin carries its name right after the marker, one byte of length first
            kind, pin, num = "$PINSHORT", tail[11:20].decode("latin1", "replace"), ""
        # the two captured four byte groups are x and y; their own offsets keep this right
        # whether or not the optional 0x01 is present
        x, y = struct.unpack_from("<ii", d, m.start(2))
        # a device's pins are in front of its [NAME]+ marker, so the next marker names them
        nxt = marker.search(d, m.end())
        if nxt:
            name = nxt.group(1).decode("latin1")
            out.setdefault(name, []).append((kind, pin.strip(), num.strip(), x / UNITS, y / UNITS))
            pending.append(name)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--device")
    a = ap.parse_args()
    d = open(a.design, "rb").read()
    for name, pins in devices(d).items():
        if a.device and name != a.device:
            continue
        print("== %s" % name)
        for kind, pin, num, x, y in pins:
            print("   %-12s %-5s pin %-3s (%+7.3f, %+7.3f)" % (kind, pin, num, x, y))


if __name__ == "__main__":
    main()
