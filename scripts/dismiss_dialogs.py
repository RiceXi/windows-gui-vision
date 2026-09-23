#!/usr/bin/env python3
"""Close any modal dialog of an application by pressing its OK/默认 button *by message*.

Why by message and not WM_CLOSE: this build pops an activation notice (and the component editor)
as modal dialogs, and while one is up the main window is disabled - every later menu command and
every click is silently dropped, which is indistinguishable from "the automation does nothing".
WM_CLOSE can leave the application in a state where its commands are still ignored; pressing the
real button is what the user would do.

    python dismiss_dialogs.py --pid 1234           # close everything, report what was closed
    python dismiss_dialogs.py --pid 1234 --list    # just show them
    python dismiss_dialogs.py --pid 1234 --check   # exit 0 if the main window is enabled
"""
import argparse
import ctypes
import ctypes.wintypes as w
import time
from ctypes import byref

user32 = ctypes.windll.user32
user32.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.SendMessageW.restype = w.LPARAM
WM_COMMAND = 0x0111
BM_CLICK = 0x00F5
IDOK = 1

PREFERRED = ("确定", "OK", "是", "Yes", "关闭", "Close", "取消", "Cancel")


def windows(pid):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        p = ctypes.c_ulong(); user32.GetWindowThreadProcessId(h, byref(p))
        c = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, c, 64)
        n = user32.GetWindowTextLengthW(h)
        t = ctypes.create_unicode_buffer(n + 2); user32.GetWindowTextW(h, t, n + 2)
        r = w.RECT(); user32.GetWindowRect(h, byref(r))
        out.append(dict(hwnd=h, pid=p.value, cls=c.value, title=t.value,
                        w=r.right - r.left, h=r.bottom - r.top,
                        visible=bool(user32.IsWindowVisible(h))))
        return True

    user32.EnumWindows(cb, 0)
    return [x for x in out if x["pid"] == pid]


def children(hwnd):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        c = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, c, 64)
        n = user32.GetWindowTextLengthW(h)
        t = ctypes.create_unicode_buffer(n + 2); user32.GetWindowTextW(h, t, n + 2)
        out.append(dict(hwnd=h, cls=c.value, title=t.value,
                        visible=bool(user32.IsWindowVisible(h))))
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return out


def main_window(pid):
    best = None
    for x in windows(pid):
        if x["visible"] and x["w"] > 800:
            best = x
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    main_win = main_window(a.pid)
    if a.check:
        if not main_win:
            print("no main window")
            return 2
        enabled = bool(user32.IsWindowEnabled(main_win["hwnd"]))
        print("main window enabled=%s" % enabled)
        return 0 if enabled else 1

    dialogs = [x for x in windows(a.pid) if x["cls"] == "#32770" and x["visible"]]
    if a.list:
        for x in dialogs:
            print("dialog %r %dx%d at %d,%d" % (x["title"], x["w"], x["h"], 0, 0))
        print("main enabled:", bool(main_win and user32.IsWindowEnabled(main_win["hwnd"])))
        return 0

    for x in dialogs:
        kids = children(x["hwnd"])
        buttons = [k for k in kids if k["cls"] == "Button" and k["visible"]]
        target = None
        for pref in PREFERRED:
            for b in buttons:
                if pref in b["title"]:
                    target = b
                    break
            if target:
                break
        if target:
            user32.SendMessageW(target["hwnd"], BM_CLICK, 0, 0)
            print("pressed %r on dialog %r" % (target["title"], x["title"]))
        else:
            user32.SendMessageW(x["hwnd"], WM_COMMAND, IDOK, 0)
            print("sent IDOK to dialog %r (no labelled button)" % x["title"])
        time.sleep(0.6)
    if dialogs:
        time.sleep(0.6)
        left = [x for x in windows(a.pid) if x["cls"] == "#32770" and x["visible"]]
        print("dialogs left: %d" % len(left))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
