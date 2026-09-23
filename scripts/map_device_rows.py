#!/usr/bin/env python3
"""Measure which y in the device panel actually selects which device.

The device list is drawn by the application itself (the window under those pixels is the main
window, not a child control), so the row rectangles cannot be read out of the window hierarchy and
a click on the visible text does not always land on the row it appears to belong to. The reliable
read-back is the preview pane: it captions the armed device as `[74LS00]`, `[LOGICPROBE]`, ...

    python map_device_rows.py --pid 1234 --x 75 --ys 210,216,222,228
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

PS = [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
      "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
HERE = os.path.dirname(os.path.abspath(__file__))
CLICK = os.path.join(HERE, "proteus_click.ps1")
CAPTURE = os.path.join(os.path.dirname(HERE), "..", "..", "..", "..",
                       r".codex\skills\windows-gui-vision\scripts\capture_window.ps1")
CAPTURE = os.path.abspath(r"C:\Users\yangf\.codex\skills\windows-gui-vision\scripts\capture_window.ps1")
CROP = r"C:\Users\yangf\.codex\skills\windows-gui-vision\scripts\crop.py"
OCR = r"C:\Users\yangf\.codex\skills\windows-gui-vision\scripts\ocr.ps1"
PY = sys.executable


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return (p.stdout or "") + (p.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--x", type=int, default=75)
    ap.add_argument("--ys", required=True)
    ap.add_argument("--xs", help="comma separated x values; default just --x")
    ap.add_argument("--out", default=os.path.join(HERE, "rows"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    # clear any modal dialog first: with one up, every click is discarded
    run(PS + [os.path.join(HERE, "proteus_input.ps1"),
              "-TargetPid", str(a.pid), "-CloseNotices"])

    xs = [int(v) for v in a.xs.split(",")] if a.xs else [a.x]
    for x in xs:
        for y in (int(v) for v in a.ys.split(",")):
            run(PS + [CLICK, "-TargetPid", str(a.pid), "-Clicks", "%d,%d" % (x, y),
                      "-GapMs", "400", "-Topmost"])
            png = os.path.join(a.out, "shot_%d_%d.png" % (x, y))
            run(PS + [CAPTURE, "-OutPath", png, "-ProcessId", str(a.pid)])
            run([PY, CROP, png, a.out, "--box", "30,180,220,330",
                 "--prefix", "cap_%d_%d" % (x, y), "--scale", "3"])
            txt = run(PS + [OCR, "-Path", os.path.join(a.out, "cap_%d_%d00.png" % (x, y)),
                            "-NoBoxes"])
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            caption = next((l for l in reversed(lines) if re.match(r"^\[.*\]$", l)), "")
            print("x=%-4d y=%-4d -> %s" % (x, y, caption or (lines[-1] if lines else "(no text)")))


if __name__ == "__main__":
    main()
