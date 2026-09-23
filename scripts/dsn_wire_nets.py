#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wire a list of nets into a design, one wire per net and a tap for every pin after the second.

    python dsn_wire_nets.py --design clean.DSN --nets nets.json [--script <dsn_draw_wires.ps1>]

`nets.json` is a list of nets, each a list of pins given as design-inch coordinates:

    {"nets": [[[2.8,0.8],[1.8,-1.3]],
              [[1.8,0.7],[2.8,-1.2],[1.8,-1.1]]]}

It runs in two passes, because that is what the application allows:

  pass 1  draw one wire per net between its first two pins. Isis routes a straight request
          orthogonally on its own, so the route is not known in advance;
  read    the design back and take a vertex of each net's wire as the node position;
  pass 2  for every further pin of a net: place a junction at that vertex and draw from the node
          to the pin - `dsn_draw_wires.ps1` does that when the first point is written with a
          leading @.

Both passes are single runs of the drawing script (each about half a minute), and the wire count
in the file is checked after each: a tap has to raise it by two (the tapped wire becomes two) and a
plain wire by one.
"""
import argparse
import json
import os
import re
import struct
import subprocess
import sys
import tempfile

UNITS = 2540000.0
PREFIX = bytes.fromhex("ffffff00ffffff00")


def read_wires(path):
    d = open(path, "rb").read()
    head = d.find(b"ISIS CIRCUIT FILE")
    tail = d.find(b"ISIS CIRCUIT FILE", head + 1)
    out = []
    for m in re.finditer(rb"\x02\x7fWIRE\x00", d[head:tail]):
        o = head + m.start()
        if d[o - 8:o] != PREFIX:
            continue
        n = struct.unpack_from("<H", d, o + 9)[0]
        # the body of the *last* wire in the area runs to the area's end, so only the points have
        # to be inside - requiring the 15 byte body as well silently dropped that wire
        if n > 64 or o + 11 + 8 * n > tail:
            continue
        pts = [struct.unpack_from("<ii", d, o + 11 + 8 * i) for i in range(n)]
        out.append([(round(x / UNITS, 3), round(y / UNITS, 3)) for x, y in pts])
    return out


def run_pass(script, design, lines, label):
    fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="wires_")
    os.close(fd)
    with open(list_path, "w", encoding="ascii") as fh:
        fh.write("# %s\n" % label)
        for line in lines:
            fh.write(line + "\n")
    before = len(read_wires(design))
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
           "-Path", design, "-WireList", list_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.splitlines():
        if "drew" in line or "WARNING" in line or "window at" in line:
            print("   " + line.strip())
    after = len(read_wires(design))
    print("  %s: wires %d -> %d" % (label, before, after))
    os.unlink(list_path)
    return before, after


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--nets", required=True)
    ap.add_argument("--script", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "dsn_draw_wires.ps1"))
    args = ap.parse_args()

    nets = json.load(open(args.nets, encoding="utf-8"))["nets"]
    if any(len(n) < 2 for n in nets):
        raise SystemExit("every net needs at least two pins")

    # pass 1: one plain wire per net
    print("pass 1: %d net(s)" % len(nets))
    lines = ["%s,%s,%s,%s" % (n[0][0], n[0][1], n[1][0], n[1][1]) for n in nets]
    start_count = len(read_wires(args.design))
    run_pass(args.script, args.design, lines, "plain wires")
    have = len(read_wires(args.design))
    if have - start_count < len(nets):
        print("WARNING: only %d of %d nets got their first wire" % (have - start_count, len(nets)))

    # read the routes back: a net's node goes on a vertex of the wire that carries it
    wires = read_wires(args.design)
    fresh = wires[len(wires) - (have - start_count):] if have - start_count > 0 else []
    nodes = []
    for net, wire in zip([n for n in nets], fresh):
        # the node must not sit right next to a pin: clicking within a few pixels of one is read as
        # clicking the pin, and in junction mode that does nothing at all. Take the vertex nearest
        # the middle of the route instead.
        if len(wire) > 2:
            mid = (len(wire) - 1) / 2.0
            pick = wire[int(round(mid))]
        else:
            pick = ((wire[0][0] + wire[1][0]) / 2.0, (wire[0][1] + wire[1][1]) / 2.0)
        nodes.append(pick)
    print("  nodes chosen: %s" % ["(%.2f,%.2f)" % p for p in nodes])

    # pass 2: a tap per extra pin, retried at neighbouring vertices until the file agrees
    extra = [(i, n[2:]) for i, n in enumerate(nets) if len(n) > 2]
    if extra:
        print("pass 2: %d tap(s)" % sum(len(p) for _, p in extra))
        for i, pins in extra:
            for p in pins:
                wire = fresh[i] if i < len(fresh) else []
                # candidate node positions, best first: the vertex nearest the middle of the route,
                # then its neighbours. A junction click that lands beside the wire does nothing, so
                # each try is judged by the file: a successful tap turns one wire into two and adds
                # the branch, i.e. the wire count goes up by two.
                mid = (len(wire) - 1) / 2.0
                order = sorted(range(len(wire)), key=lambda k: abs(k - mid))
                ok = False
                for k in order[:3]:
                    node = wire[k]
                    before = len(read_wires(args.design))
                    line = "@%s,%s;%s,%s" % (node[0], node[1], p[0], p[1])
                    run_pass(args.script, args.design, [line], "tap at (%.2f,%.2f)" % node)
                    after = len(read_wires(args.design))
                    if after - before >= 2:
                        print("  tap accepted at (%.2f,%.2f): wires %d -> %d" % (node[0], node[1],
                                                                                before, after))
                        ok = True
                        break
                    print("  tap at (%.2f,%.2f) did not take (wires %d -> %d), trying the next vertex"
                          % (node[0], node[1], before, after))
                if not ok:
                    print("WARNING: could not tap the net for pin (%s,%s)" % (p[0], p[1]))

    print("done: %s now has %d wire(s)" % (args.design, len(read_wires(args.design))))


if __name__ == "__main__":
    sys.exit(main())
