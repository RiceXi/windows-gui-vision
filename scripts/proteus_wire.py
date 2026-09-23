#!/usr/bin/env python3
"""Wire pins in a *running* Isis, and prove it from the file afterwards.

    python proteus_wire.py --design copy.DSN --pid 1234 --plan plan.txt --click <proteus_click.ps1>
    python proteus_wire.py ... --dry-run

plan.txt is one connection per line:

    U2:A.A  VCC            # a gate input to the VCC terminal
    U2:A.Y  U1.P           # the gate output to the logic probe

Pin offsets come from dsn_pins_table.py (measured from hand-wired designs); a terminal uses the
name it carries in the file (VCC, GND).

Two rules the application enforces and this tool exists to satisfy: a wire is only written when
*both* clicks land on connection points, and the screen mapping has to be known for the window
that is actually in front. The mapping is therefore calibrated first - one spare part placed at a
known point, saved, and read back - and every click sequence is run with -AbortOnLostFocus so a
focus change stops the run instead of drawing half a wire.
"""
import argparse
import os
import re
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsn_netlist as nl           # noqa: E402
import dsn_pins_table as pins      # noqa: E402
import dsn_objects as objs         # noqa: E402

POWERSHELL = [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
              "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]


def read_state(design):
    d = open(design, "rb").read()
    head = d.find(nl.MARKER)
    tail = d.find(nl.MARKER, head + 1)
    return d, head, tail


def spare_anchor(design, before_size):
    """The anchor of the part added by the calibration placement, or None."""
    d = open(design, "rb").read()
    if len(d) <= before_size:
        return None
    head = d.find(nl.MARKER)
    tail = d.find(nl.MARKER, head + 1)
    found = nl.parts(d, head, tail)
    return found


def click(script, pid, points, gap=1000):
    arg = " ".join("%d,%d" % p for p in points)
    cmd = POWERSHELL + [script, "-TargetPid", str(pid), "-Clicks", arg,
                        "-GapMs", str(gap), "-AbortOnLostFocus"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.splitlines():
        print("   " + line.strip())
    return proc.returncode


def save(design, pid, menu_script):
    cmd = [sys.executable, menu_script, "--pid", str(pid), "--menu", "0", "--item", "保存设计"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print("   " + (proc.stdout or proc.stderr or "").strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--click", required=True, help="path to proteus_click.ps1")
    ap.add_argument("--menu", required=True, help="path to menu_command.py")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-calibration", action="store_true")
    a = ap.parse_args()

    d, head, tail = read_state(a.design)
    parts = nl.parts(d, head, tail)
    devs = nl.device_of(d, head, tail)
    terms = {name: (x, y) for name, kind, x, y in nl.terminals(d, head, tail)}
    print("parts: %s" % ", ".join("%s(%s)" % (k, devs.get(k, "?")) for k in sorted(parts)))
    print("terminals: %s" % ", ".join(sorted(terms)))

    conns = []
    for line in open(a.plan, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if not line:
            continue
        left, right = re.split(r"\s+", line)[:2]

        def where(ref):
            if ref in terms:
                return terms[ref]
            part, _, pin_name = ref.rpartition(".")
            if part not in parts:
                raise SystemExit("no part %r in the design (have: %s)" % (part, sorted(parts)))
            dev = devs.get(part)
            if dev not in pins.TABLE or pin_name not in pins.TABLE[dev]:
                raise SystemExit("no pin %s on %s (%s)" % (pin_name, part, dev))
            ox, oy = pins.pin(dev, pin_name)
            x, y = parts[part]
            return (round(x + ox, 3), round(y + oy, 3))

        conns.append((left, where(left), right, where(right)))

    print("connections:")
    for left, p1, right, p2 in conns:
        print("   %-12s %s <-> %-12s %s" % (left, p1, right, p2))

    # calibrate: place a spare part and read the anchor back
    if not a.skip_calibration:
        before = os.path.getsize(a.design)
        print("calibrating: placing a spare 74LS00 at the canvas centre")
        if not a.dry_run:
            rc = click(a.click, a.pid, [(25, 143), (72, 232), (700, 450)] * 1 + [(700, 450)] * 2)
            save(a.design, a.pid, a.menu)
            found = spare_anchor(a.design, before)
            if not found:
                raise SystemExit("calibration failed: nothing was placed (check the view and focus)")
            new = [n for n in found if n not in parts]
            if not new:
                raise SystemExit("calibration failed: no new part in the saved file")
            ax, ay = found[new[0]]
            # click point -> anchor: measured offset for a 74LS00
            ox = 700 - 100 * (ax - pins.PLACE_ANCHOR_OFFSET["74LS00"][0])
            oy = 450 + 100 * (ay - pins.PLACE_ANCHOR_OFFSET["74LS00"][1])
            print("   placed %s at (%0.3f,%0.3f) -> mapping origin (%0.1f,%0.1f)"
                  % (new[0], ax, ay, ox, oy))
        else:
            ox, oy = 782.0, 461.0
            print("   dry run, assuming origin (%0.1f,%0.1f)" % (ox, oy))
    else:
        ox, oy = 782.0, 461.0

    def to_screen(p):
        return (int(round(ox + 100 * p[0])), int(round(oy - 100 * p[1])))

    points = []
    for left, p1, right, p2 in conns:
        points += [to_screen(p1), to_screen(p2)]
    print("click sequence: %s" % " ".join("%d,%d" % p for p in points))
    if a.dry_run:
        return

    rc = click(a.click, a.pid, points)
    if rc != 0:
        print("click run aborted (rc=%d) - focus was lost; nothing to verify" % rc)
        return
    save(a.design, a.pid, a.menu)
    d2, h2, t2 = read_state(a.design)
    print("after: %d wires (was %d)" % (len(nl.wires(d2, h2, t2)), len(nl.wires(d, head, tail))))


if __name__ == "__main__":
    main()
