#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Byte diff of two .DSN files, printed as changed regions with context.

This is the tool the wire format was worked out with: save the same design twice, once with
the edit you want to understand and once without, then diff the two saves. Diffing an edit
against the pristine original instead is the mistake that makes this look hopeless - Isis
rewrites more than you think when it saves, so the comparison has to be save against save.

    python dsn_diff.py base.DSN edited.DSN [context bytes]
"""
import difflib
import sys


def hexs(b):
    return " ".join("%02x" % c for c in b)


def show(a, b, ctx=16, name_a="A", name_b="B"):
    print("%s=%s (%d)  %s=%s (%d)  delta=%+d"
          % (name_a, name_a, len(a), name_b, name_b, len(b), len(b) - len(a)))
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        print("--- %s A[%d:%d] (%d bytes) -> B[%d:%d] (%d bytes)"
              % (tag, i1, i2, i2 - i1, j1, j2, j2 - j1))
        print("  A ctx: %s" % hexs(a[max(0, i1 - ctx):i1]))
        if i2 > i1:
            print("  A old: %s" % hexs(a[i1:i2]))
        if j2 > j1:
            print("  B new: %s" % hexs(b[j1:j2]))
        print("  B ctx: %s" % hexs(b[j2:j2 + ctx]))


def main():
    a = open(sys.argv[1], "rb").read()
    b = open(sys.argv[2], "rb").read()
    ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    show(a, b, ctx, sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
