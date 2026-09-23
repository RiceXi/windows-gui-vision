#!/usr/bin/env python3
"""Build a circuit in a running Isis, one small retried step at a time, verified from the file.

Why retries per step and not one long batch: the clicks only land while the target window is
foreground, and the user of the machine may take it back at any moment. A step is two to four
clicks, so the window in which it has to stay foreground is a few seconds; a failed attempt
writes nothing (the click harness aborts on lost focus), and the next attempt a few seconds
later usually gets through. The file decides whether a step actually happened.

Every successful placement also *recalibrates* the screen mapping: the click point and the anchor
the design recorded for it are two halves of the same relation, so the tool never has to trust
the mapping it measured a minute ago - which matters because the sheet scrolls between batches
(measured: origin (780,460) then (610,444) then (520,270) for one instance).

    python proteus_builder.py --design or1.DSN --pid 1234 --page 2 --plan plan.json

plan.json:
    {"place": [ {"row": 1, "at": [620, 420], "name": "gate"},
                {"row": 3, "at": [620, 300], "name": "ra"} ],
     "wire":  [ {"a": {"part": "U1", "pin": "1"}, "b": {"part": "R1", "pin": "2"}} ]}
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsn_netlist as nl
import dsn_pins_table as pintab

PS = [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
      "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
HERE = os.path.dirname(os.path.abspath(__file__))
CLICK = os.path.join(HERE, "proteus_click.ps1")
MENU = os.path.join(HERE, "menu_command.py")
INPUT = os.path.join(HERE, "proteus_input.ps1")
PLACE_OFFSET = pintab.PLACE_ANCHOR_OFFSET["74LS00"]
MODE_DEVICES = (25, 143)
MODE_SELECT = (20, 120)
MODE_TERMINALS = (20, 270)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def click(pid, points, gap=800):
    # A modal dialog left open by an earlier stray double click swallows every later click -
    # "under the pointer" is then an Edit box inside a dialog that happens to belong to the same
    # process, so the guard passes and nothing happens on the canvas. Clearing them first is what
    # turned this around after a long stretch of "the clicks arrive but nothing lands".
    run(PS + [INPUT, "-TargetPid", str(pid), "-CloseNotices"])
    arg = " ".join("%d,%d" % p for p in points)
    out, rc = run(PS + [CLICK, "-TargetPid", str(pid), "-Clicks", arg,
                        "-GapMs", str(gap), "-AbortOnLostFocus", "-Topmost"])
    return out, rc


def save(pid):
    run([sys.executable, MENU, "--pid", str(pid), "--id", "308"])


def page_areas(path, page):
    """(head, tail) of the object area of the given page (1-based), or None."""
    d = open(path, "rb").read()
    marks = [m.start() for m in nl.re.finditer(nl.MARKER, d)]
    if page == 1:
        return marks[0], marks[1] if len(marks) > 1 else len(d)
    idx = 2 * (page - 1)
    if idx + 1 >= len(marks):
        return None
    return marks[idx], marks[idx + 1]


def snapshot(path, page):
    d = open(path, "rb").read()
    area = page_areas(path, page)
    if not area:
        return {}, [], [], {}
    head, tail = area
    return (nl.parts(d, head, tail), nl.wires(d, head, tail),
            nl.terminals(d, head, tail), nl.device_of(d, head, tail))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--page", type=int, default=2)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--tries", type=int, default=25)
    ap.add_argument("--pause", type=float, default=2.0)
    a = ap.parse_args()

    plan = json.load(open(a.plan, encoding="utf-8"))
    scale = 100.0
    origin = None            # (ox, oy) in screen pixels, learnt from placements

    def to_screen(px, py):
        if origin is None:
            raise SystemExit("no mapping yet: place something first")
        return (int(round(origin[0] + scale * px)), int(round(origin[1] - scale * py)))

    for step in plan.get("place", []):
        base_parts, base_wires, _, _ = snapshot(a.design, a.page)
        before = set(base_parts)
        target = tuple(step["at"])
        ok = False
        for attempt in range(a.tries):
            out, rc = click(a.pid, [MODE_DEVICES, (72, 232.5 + 13 * step["row"]),
                                    target, target, target])
            save(a.pid)
            time.sleep(1.2)
            parts, wires, terms, devs = snapshot(a.design, a.page)
            new = [n for n in parts if n not in before]
            if new:
                name = sorted(new)[0]
                anchor = parts[name]
                print("  placed %s at (%.3f,%.3f) after %d attempt(s)"
                      % (name, anchor[0], anchor[1], attempt + 1))
                # Only a device whose click->anchor offset has been measured may move the mapping.
                # For any other device the offset is unknown, and treating it as the 74LS00's
                # would bias every later click by the difference.
                if step.get("calibrate") or origin is None:
                    click_design = (anchor[0] - PLACE_OFFSET[0], anchor[1] - PLACE_OFFSET[1])
                    origin = (target[0] - scale * click_design[0],
                              target[1] + scale * click_design[1])
                    print("    mapping now origin (%.1f,%.1f), scale %.0f" %
                          (origin[0], origin[1], scale))
                else:
                    print("    offset for this device: (%.3f,%.3f) from the click point"
                          % (anchor[0] - (target[0] - origin[0]) / scale,
                             anchor[1] - (origin[1] - target[1]) / scale))
                ok = True
                break
            if rc != 0:
                print("    attempt %d: focus lost (rc=2), retrying" % (attempt + 1))
            else:
                print("    attempt %d: clicks ran but nothing landed" % (attempt + 1))
            time.sleep(a.pause)
        if not ok:
            print("  STEP FAILED: %s" % step.get("name", step))
            return

    for step in plan.get("terminal", []):
        parts0, _, terms0, _ = snapshot(a.design, a.page)
        before = len(terms0)
        target = tuple(step["at"])
        print("  terminal %s (row %d) at %s" % (step["name"], step["row"], target))
        ok = False
        for attempt in range(a.tries):
            out, rc = click(a.pid, [MODE_TERMINALS, (55, 284.5 + 13 * step["row"]),
                                    target, target])
            save(a.pid)
            time.sleep(1.2)
            parts, wires, terms, devs = snapshot(a.design, a.page)
            if len(terms) > before:
                # a terminal's pin is the point that was clicked
                click_design = ((target[0] - origin[0]) / scale, (origin[1] - target[1]) / scale)
                print("    placed %d terminal(s); pin at %s" %
                      (len(terms) - before, click_design))
                ok = True
                break
            if rc != 0:
                print("    attempt %d: focus lost, retrying" % (attempt + 1))
            time.sleep(a.pause)
        if not ok:
            print("  TERMINAL FAILED: %s" % step.get("name"))
            return

    parts, wires, terms, devs = snapshot(a.design, a.page)

    parts, wires, terms, devs = snapshot(a.design, a.page)
    print("parts: %s" % ", ".join("%s(%s)" % (k, devs.get(k, "?")) for k in sorted(parts)))
    print("terminals: %s" % ", ".join("%s" % t[0] for t in terms))

    for step in plan.get("wire", []):
        base_parts, base_wires, _, _ = snapshot(a.design, a.page)
        before = len(base_wires)
        ok = False

        def pin_point(ref):
            if "terminal" in ref:
                for nm, kind, x, y in terms:
                    if nm == ref["terminal"]:
                        return (x, y)
                raise SystemExit("no terminal %r on page %d" % (ref["terminal"], a.page))
            part = ref["part"]
            if part not in parts:
                raise SystemExit("no part %r" % part)
            dev = devs.get(part)
            if dev not in pintab.TABLE or ref["pin"] not in pintab.TABLE[dev]:
                raise SystemExit("no pin %s on %s (%s)" % (ref["pin"], part, dev))
            ox, oy = pintab.pin(dev, ref["pin"])
            return (parts[part][0] + ox, parts[part][1] + oy)

        pa, pb = pin_point(step["a"]), pin_point(step["b"])
        print("  wire %s %s -> %s %s" % (step["a"], pa, step["b"], pb))
        for attempt in range(a.tries):
            out, rc = click(a.pid, [MODE_SELECT, to_screen(*pa), to_screen(*pb)], gap=1100)
            save(a.pid)
            time.sleep(1.2)
            _, wires, _, _ = snapshot(a.design, a.page)
            if len(wires) > before:
                print("    wired after %d attempt(s): wires %d -> %d"
                      % (attempt + 1, before, len(wires)))
                ok = True
                break
            if rc != 0:
                print("    attempt %d: focus lost, retrying" % (attempt + 1))
            time.sleep(a.pause)
        if not ok:
            print("  WIRE FAILED: %s -> %s" % (step["a"], step["b"]))
            break

    # Pin discovery: for a device whose pin offsets are not in the table yet, try candidate
    # offsets by wiring each one to a pin that *is* known - a wire only appears when both ends
    # are on connection points, so the file itself reports which candidate was right.
    for step in plan.get("discover", []):
        part = step["part"]
        if part not in parts:
            print("  DISCOVER skipped: no part %r" % part)
            continue
        anchor = parts[part]
        known = step["against"]           # {"part": "R1", "pin": "1"}
        kp = pin_point(known)
        found = []
        for cand in step["candidates"]:
            before = len(snapshot(a.design, a.page)[1])
            target = (anchor[0] + cand[0], anchor[1] + cand[1])
            for attempt in range(3):
                out, rc = click(a.pid, [MODE_SELECT, to_screen(*target), to_screen(*kp)], gap=1100)
                save(a.pid)
                time.sleep(1.0)
                now = len(snapshot(a.design, a.page)[1])
                if now > before:
                    print("  %s pin found at offset (%+.3f,%+.3f) -> wire %d" %
                          (part, cand[0], cand[1], now))
                    found.append((cand, now))
                    break
        if found:
            print("  candidate pins that worked on %s: %s" % (part, found))
        else:
            print("  no candidate pin worked on %s" % part)

    print("done. final:" )
    parts, wires, terms, devs = snapshot(a.design, a.page)
    print("  %d parts, %d wires, %d terminals" % (len(parts), len(wires), len(terms)))


if __name__ == "__main__":
    main()
