#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-check for the windows-gui-vision skill.

Verifies the interpreter, the Python packages the scripts need, the vision API
key, the PowerShell helpers, and that the pixel helpers actually run.

    python verify_env.py [--skill-dir <dir>] [--no-network]

Exit code 0 = ready, 1 = something is missing (the message says what).
"""
import argparse
import importlib
import os
import shutil
import subprocess
import sys
import tempfile

OK = "OK  "
BAD = "FAIL"
WARN = "WARN"


def check_python():
    if sys.version_info < (3, 8):
        return BAD, "Python %d.%d found, need 3.8+" % sys.version_info[:2]
    return OK, "Python %d.%d.%d" % sys.version_info[:3]


def check_module(name, import_name=None):
    try:
        mod = importlib.import_module(import_name or name)
        ver = getattr(mod, "__version__", "?")
        return OK, "%s %s" % (name, ver)
    except Exception as exc:  # noqa: BLE001
        return BAD, "%s missing (%s) -> pip install %s" % (name, exc, name)


def check_powershell():
    for exe in ("powershell.exe", "pwsh.exe"):
        hit = shutil.which(exe)
        if hit:
            return OK, "%s -> %s" % (exe, hit)
    return BAD, "neither powershell.exe nor pwsh.exe on PATH"


def check_key(no_network):
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        return WARN, "DEEPSEEK_API_KEY not set: see.py (vision) will not work, " \
                     "OCR and pixel tools still do"
    if no_network:
        return OK, "DEEPSEEK_API_KEY present (len %d), network test skipped" % len(key)
    return OK, "DEEPSEEK_API_KEY present (len %d)" % len(key)


def check_scripts(skill_dir):
    need = ["see.py", "ocr.ps1", "capture_window.ps1", "screen_capture.ps1",
            "grab_foreground.ps1", "wins.ps1", "region_ascii.py", "clusters.py",
            "edgecheck.py", "colorfind.py", "crop.py", "montage.py", "ruler.py",
            "diffshots.py", "calibrate.py", "layout.py", "selftest_scaling.py",
            "dsn_add_component.py"]
    missing = [n for n in need if not os.path.exists(os.path.join(skill_dir, "scripts", n))]
    if missing:
        return BAD, "missing scripts: %s" % ", ".join(missing)
    return OK, "all %d scripts present" % len(need)


def smoke_pixels(skill_dir):
    """Generate a tiny image and run region_ascii.py + edgecheck.py on it."""
    try:
        from PIL import Image, ImageDraw
        work = tempfile.mkdtemp(prefix="wgv_")
        path = os.path.join(work, "smoke.png")
        im = Image.new("RGB", (240, 160), (224, 224, 208))
        d = ImageDraw.Draw(im)
        d.rectangle([60, 50, 180, 110], outline=(0, 0, 192), width=3)
        d.line([60, 80, 180, 80], fill=(0, 0, 0), width=2)
        im.save(path)
        py = sys.executable
        r1 = subprocess.run([py, os.path.join(skill_dir, "scripts", "region_ascii.py"),
                             path, "0,0,240,160"], capture_output=True, text=True)
        r2 = subprocess.run([py, os.path.join(skill_dir, "scripts", "edgecheck.py"), path],
                            capture_output=True, text=True)
        if r1.returncode or r2.returncode:
            return BAD, "pixel helpers failed: %s%s" % (r1.stderr[-300:], r2.stderr[-300:])
        return OK, "region_ascii.py + edgecheck.py ran on a synthetic image"
    except Exception as exc:  # noqa: BLE001
        return BAD, "smoke test error: %s" % exc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--no-network", action="store_true")
    args = ap.parse_args()

    rows = [
        ("python", check_python()),
        ("Pillow", check_module("PIL", "PIL.Image")),
        ("numpy", check_module("numpy")),
        ("python-docx", check_module("docx", "docx")),
        ("powershell", check_powershell()),
        ("vision key", check_key(args.no_network)),
        ("scripts", check_scripts(args.skill_dir)),
        ("pixel smoke test", smoke_pixels(args.skill_dir)),
    ]
    width = max(len(name) for name, _ in rows)
    bad = 0
    for name, (state, msg) in rows:
        if state == BAD:
            bad += 1
        print("%-4s %-*s %s" % (state, width, name, msg))
    print()
    print("skill dir:", args.skill_dir)
    if bad:
        print("%d check(s) failed." % bad)
        return 1
    print("ready: capture -> read -> act -> verify all available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
