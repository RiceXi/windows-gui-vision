#!/usr/bin/env python3
"""Select a row in Isis's object-selector list by message, and tell the app about it.

A mouse click on the list sometimes does nothing, and then the *previously* armed device is what
gets placed - which looks like "the click lands but the part is wrong". The list is an ordinary
ListBox, so the row can be set with LB_SETCURSEL, and the parent told with the selection-change
notification the application listens for. Messages only, so no foreground is needed.

    python listbox_select.py --pid 1234 --list
    python listbox_select.py --pid 1234 --index 2
"""
import argparse
import ctypes
import ctypes.wintypes as w
from ctypes import byref

user32 = ctypes.windll.user32
user32.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.SendMessageW.restype = w.LPARAM

LB_GETCOUNT = 0x018B
LB_SETCURSEL = 0x0186
LB_GETCURSEL = 0x0188
LB_GETTEXTLEN = 0x018A
WM_COMMAND = 0x0111
LBN_SELCHANGE = 1


def main_window(pid):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        p = ctypes.c_ulong(); user32.GetWindowThreadProcessId(h, byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            r = w.RECT(); user32.GetWindowRect(h, byref(r))
            if r.right - r.left > 800:
                found.append(h)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def listboxes(hwnd):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        c = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, c, 64)
        r = w.RECT(); user32.GetWindowRect(h, byref(r))
        if c.value == "ListBox" and (r.right - r.left) > 60:
            out.append((h, r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--index", type=int)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    main = main_window(a.pid)
    if not main:
        raise SystemExit("no main window")
    lbs = listboxes(main)
    if a.list or a.index is None:
        for i, (h, x, y, ww, hh) in enumerate(lbs):
            print("listbox %d hwnd=%s at %d,%d %dx%d rows=%d cur=%d"
                  % (i, h, x, y, ww, hh,
                     user32.SendMessageW(h, LB_GETCOUNT, 0, 0),
                     user32.SendMessageW(h, LB_GETCURSEL, 0, 0)))
        return

    lb = lbs[0][0]
    n = user32.SendMessageW(lb, LB_GETCOUNT, 0, 0)
    if not 0 <= a.index < n:
        raise SystemExit("index %d out of range (rows=%d)" % (a.index, n))
    user32.SendMessageW(lb, LB_SETCURSEL, a.index, 0)
    parent = user32.GetParent(lb)
    cid = user32.GetDlgCtrlID(lb)
    user32.SendMessageW(parent, WM_COMMAND, (cid & 0xFFFF) | (LBN_SELCHANGE << 16), lb)
    print("selected row %d of %d (cur=%d) in listbox %s"
          % (a.index, n, user32.SendMessageW(lb, LB_GETCURSEL, 0, 0), lb))


if __name__ == "__main__":
    main()
