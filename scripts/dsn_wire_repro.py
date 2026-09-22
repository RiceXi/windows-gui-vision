#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduce one hand-drawn wire with the writer, and say exactly how the file differs.

    python dsn_wire_repro.py --base base.DSN --hand hand.DSN --at 19478 \
        --ref U3:C --pin 2 --link-ref U3:B --link-pin 3 --out check.DSN

`--at` is the offset of the wire's `02 7f WIRE 00` in the hand-drawn file; its points and its
length come from there, so nothing about the wire is typed in twice. `--pin` is the pin of
`--ref` the wire lands on, counted from 1 in the order the part's pin map lists them.

What it reports, and the right answer for each:

  the spliced wire            IDENTICAL - the tail block, the record and the bytes it displaced
  the shift on every later byte   none - everything after the splice moved by the record's length
  the pin slots               equal in both files, and equal to the wire's tail offset
  every byte that still differs   the two byte stamp, the object-area length, Isis's five
                              counters, and whatever later hand edits did (nothing else)

Ground truth for the five instance 74LS00 base: the ten point wire at 19478 in `hand_wire.DSN`
is the first of three hand edits, and the check above passes on it.
"""
import argparse
import struct
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import dsn_add_wire as W  # noqa: E402


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--hand", required=True)
    ap.add_argument("--at", type=int, required=True, help="offset of the wire in the hand file")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--pin", type=int, required=True)
    ap.add_argument("--link-ref")
    ap.add_argument("--link-pin", type=int)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    base = open(a.base, "rb").read()
    hand = open(a.hand, "rb").read()
    n = struct.unpack_from("<H", hand, a.at + 9)[0]
    pts = [struct.unpack_from("<ii", hand, a.at + 11 + 8 * i) for i in range(n)]
    pts = [(x / W.UNITS, y / W.UNITS) for x, y in pts]

    info = W.add_wire(base, pts, after_part=a.ref, pin=a.pin, link_part=a.link_ref,
                      link_pin=a.link_pin, out=a.out)
    got = info["data"]
    at = info["inserted_at"]
    length = 34 + 8 * n
    print("wire: %d points, %d bytes, spliced at %d, delta %d" % (n, length, at, info["inserted"]))

    # 1. the spliced wire itself
    lo, hi = at, at + 15 + length
    bad = [i for i in range(lo, hi) if got[i] != hand[i]]
    print("  spliced wire + tail block   %s"
          % ("IDENTICAL (%d bytes)" % (hi - lo) if not bad else "differs at %s" % bad[:8]))

    # 2. the shift it puts on everything after it
    nxt = at + 15 + length
    limit = min(len(hand), len(base) + info["inserted"])
    bad = [i for i in range(nxt, limit) if got[i] != hand[i]]
    first = bad[0] if bad else None
    print("  later bytes shifted by %-4d first difference at %s" % (info["inserted"], first))

    # 3. the pin slots
    head = got.find(W.MARKER)
    tail = got.find(W.MARKER, head + 1)
    for ref, pin in [(a.ref, a.pin)] + ([(a.link_ref, a.link_pin)] if a.link_ref else []):
        start, _ = W.part_span(got, head, tail, ref)
        off = W.pin_slot(got, start, pin)
        print("  %s pin %d slot at %d: writer=%d hand=%d"
              % (ref, pin, off, u32(got, off), u32(hand, off)))

    # 4. everything that still differs
    print("  bytes that still differ:")
    runs, start = [], None
    for i in range(177, min(len(got), len(hand))):
        if got[i] != hand[i]:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, min(len(got), len(hand))))
    for lo, hi in runs:
        print("    %d..%d (%d bytes)" % (lo, hi - 1, hi - lo))
        if hi - lo > 4:
            break
    tail_start = None
    for lo, hi in runs:
        if hi - lo > 4:
            tail_start = lo
            break
    if tail_start is not None:
        print("    (%d further differences from %d on: past this offset the hand file has the"
              % (sum(1 for lo, hi in runs if lo >= tail_start), tail_start))
        print("     objects its later edits added, so the two files are no longer in step)")


if __name__ == "__main__":
    main()
