#!/usr/bin/env python3
"""One command that builds a small circuit in a copy of a design and proves it from the file.

The pieces it strings together are all measured elsewhere in this folder:

  1. open a copy in its own Isis instance (so the user's sheet is untouched);
  2. normalise the view with 查看/缩放到整图, because a fresh instance can come back scrolled and
     then placement clicks land off the sheet and do nothing;
  3. calibrate by placing two spare parts at two known screen points and reading their anchors
     back - two points give both the scale and the origin, and they work at any zoom;
  4. wire pins with dsn_pins_table offsets, in selection mode, both ends on pins;
  5. save by menu command id (Ctrl+S cannot be trusted to reach the window), then re-read the
     file: wire count, nets, dangling ends.

Every click batch runs with -AbortOnLostFocus, and each stage is retried a few times, because
the one thing that cannot be fixed from inside the script is the user taking the foreground.

    python proteus_demo_build.py --base c2.DSN --work c7.DSN
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsn_netlist as nl                    # noqa: E402
import dsn_pins_table as pintab             # noqa: E402

ISIS = r"C:\Program Files (x86)\Labcenter Electronics\Proteus 7 Professional\BIN\ISIS.EXE"
PS = [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
      "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
HERE = os.path.dirname(os.path.abspath(__file__))
CLICK = os.path.join(HERE, "proteus_click.ps1")
MENU = os.path.join(HERE, "menu_command.py")
NOTICE = os.path.join(HERE, "proteus_input.ps1")

MODE_DEVICES = (25, 143)
MODE_SELECT = (20, 120)
ROW_74LS00 = (72, 232)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def click(pid, points, gap=900):
    arg = " ".join("%d,%d" % p for p in points)
    out, rc = run(PS + [CLICK, "-TargetPid", str(pid), "-Clicks", arg,
                        "-GapMs", str(gap), "-AbortOnLostFocus"])
    for line in out.strip().splitlines():
        print("    " + line.strip())
    return rc


def menu(pid, index, item):
    out, rc = run([sys.executable, MENU, "--pid", str(pid), "--menu", str(index), "--item", item])
    print("    " + out.strip())
    return rc


def read_parts(path):
    d = open(path, "rb").read()
    head = d.find(nl.MARKER)
    tail = d.find(nl.MARKER, head + 1)
    return nl.parts(d, head, tail), nl.device_of(d, head, tail)


def wire_count(path):
    d = open(path, "rb").read()
    head = d.find(nl.MARKER)
    tail = d.find(nl.MARKER, head + 1)
    return len(nl.wires(d, head, tail))


def launch(work):
    p = subprocess.Popen([ISIS, work])
    time.sleep(16)
    run(PS + [NOTICE, "-TargetPid", str(p.pid), "-CloseNotices"])
    return p


def calibrate(work, pid, before_parts):
    """Two placements give scale and origin. Returns (origin_x, origin_y, scale) or None."""
    probes = [(600, 420), (900, 420)]
    anchors = []
    for pt in probes:
        before = set(before_parts)
        click(pid, [MODE_DEVICES, ROW_74LS00, pt, pt, pt])
        menu(pid, 0, "保存设计")
        time.sleep(1.5)
        parts, devs = read_parts(work)
        new = [n for n in parts if n not in before]
        if not new:
            print("    calibration placement at %s did not land" % (pt,))
            return None
        name = sorted(new)[0]
        anchors.append((pt, parts[name]))
        before_parts[name] = parts[name]
        print("    probe %s -> %s at (%.3f, %.3f)" % (pt, name, parts[name][0], parts[name][1]))

    # screen point -> design point, then back off the measured click->anchor offset
    (p1, a1), (p2, a2) = anchors
    dx_screen = p2[0] - p1[0]
    dx_design = a2[0] - a1[0]
    if abs(dx_design) < 1e-6:
        return None
    scale = dx_screen / dx_design
    oxoff, oyoff = pintab.PLACE_ANCHOR_OFFSET["74LS00"]
    # anchor = (click_design + offset); click_design = ((x - ox)/scale, (oy - y)/scale)
    click1 = (a1[0] - oxoff, a1[1] - oyoff)
    ox = p1[0] - scale * click1[0]
    oy = p1[1] + scale * click1[1]
    print("    scale %.1f px/inch, origin (%.1f, %.1f)" % (scale, ox, oy))
    return ox, oy, scale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--gate", default="U2:A")
    ap.add_argument("--pins", default="A,B")     # which two pins of the gate to tie together
    ap.add_argument("--skip-calibrate", action="store_true")
    a = ap.parse_args()

    shutil.copyfile(a.base, a.work)
    print("work copy: %s (%d bytes)" % (a.work, os.path.getsize(a.work)))
    proc = launch(a.work)
    pid = proc.pid
    print("isis pid %d" % pid)
    try:
        menu(pid, 1, "缩放到整图")
        time.sleep(1.5)
        parts, devs = read_parts(a.work)
        print("parts: %s" % ", ".join("%s(%s)" % (k, devs.get(k, "?")) for k in sorted(parts)))

        if a.skip_calibrate:
            ox, oy, scale = 782.0, 461.0, 100.0
        else:
            got = None
            for attempt in range(3):
                print("  calibration attempt %d" % (attempt + 1))
                got = calibrate(a.work, pid, parts)
                if got:
                    break
            if not got:
                print("calibration failed - the view or the focus is not usable right now")
                return
            ox, oy, scale = got
            parts, devs = read_parts(a.work)

        dev = devs.get(a.gate)
        if dev != "74LS00":
            print("gate %s is %r, not a 74LS00" % (a.gate, dev))
            return
        ax, ay = parts[a.gate]
        pin1, pin2 = a.pins.split(",")

        def to_screen(px, py):
            return (int(round(ox + scale * px)), int(round(oy - scale * py)))

        p1 = to_screen(ax + pintab.pin("74LS00", pin1)[0], ay + pintab.pin("74LS00", pin1)[1])
        p2 = to_screen(ax + pintab.pin("74LS00", pin2)[0], ay + pintab.pin("74LS00", pin2)[1])
        print("  wiring %s.%s %s -> %s.%s %s" % (a.gate, pin1, p1, a.gate, pin2, p2))

        before_wires = wire_count(a.work)
        print("  wires before: %d" % before_wires)
        for attempt in range(3):
            print("  wiring attempt %d" % (attempt + 1))
            rc = click(pid, [MODE_SELECT, p1, p2], gap=1100)
            menu(pid, 0, "保存设计")
            time.sleep(1.5)
            now = wire_count(a.work)
            print("    wires %d -> %d" % (before_wires, now))
            if now > before_wires:
                break

        d = open(a.work, "rb").read()
        head = d.find(nl.MARKER); tail = d.find(nl.MARKER, head + 1)
        ws = nl.wires(d, head, tail)
        print("result: %d wires" % len(ws))
        for w in ws[-3:]:
            print("   %s" % " ".join("(%.3f,%.3f)" % p for p in w[:5]))
        run([sys.executable, os.path.join(HERE, "dsn_netlist.py"), a.work])
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
