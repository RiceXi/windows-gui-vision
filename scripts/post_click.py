#!/usr/bin/env python3
"""Click inside a window by posting mouse messages to it, with no foreground at all.

This is the answer to the one thing that cannot be fixed from a script: a second application
window that cannot take the foreground because the user is working. Posted messages go into the
window's own queue, so nothing needs to be on top and nothing steals the user's focus.

The catch is that not every application honours posted mouse messages - some read the real
cursor position instead - so the result always has to be checked in the file or on screen.

    python post_click.py --pid 1234 --list
    python post_click.py --pid 1234 --points "25,143 72,232" --client
"""
import argparse
import ctypes
import ctypes.wintypes as w
import time
from ctypes import byref

user32 = ctypes.windll.user32
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001


def main_window(pid):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        p = ctypes.c_ulong(); user32.GetWindowThreadProcessId(h, byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            r = w.RECT(); user32.GetWindowRect(h, byref(r))
            if r.right - r.left > 800:
                found.append((h, r.left, r.top))
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def client_origin(hwnd):
    pt = w.POINT(0, 0)
    user32.ClientToScreen(hwnd, byref(pt))
    return pt.x, pt.y


def post_click(hwnd, x, y, delay=0.25):
    lp = (y << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
    time.sleep(delay)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.06)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--points", help="x,y pairs, in client coordinates with --client")
    ap.add_argument("--client", action="store_true", default=True)
    ap.add_argument("--gap", type=float, default=0.9)
    a = ap.parse_args()

    got = main_window(a.pid)
    if not got:
        raise SystemExit("no main window for pid %d" % a.pid)
    hwnd, left, top = got
    cx, cy = client_origin(hwnd)
    print("window %s at %d,%d, client origin %d,%d" % (hwnd, left, top, cx, cy))
    if not a.points:
        return
    for chunk in a.points.split():
        x, y = (int(v) for v in chunk.split(","))
        px, py = x - cx, y - cy          # the points are given in screen pixels
        post_click(hwnd, px, py)
        print("posted click at screen %d,%d (client %d,%d)" % (x, y, px, py))
        time.sleep(a.gap)


if __name__ == "__main__":
    main()
