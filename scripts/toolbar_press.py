#!/usr/bin/env python3
"""List and press a toolbar button by command id - the focus-free way to run a command.

The file toolbar is a ToolbarWindow32 child of the main window. Each button carries the same
command id the menu does, so pressing it is equivalent to choosing the menu item, and it needs
neither the keyboard nor the foreground window.

    python toolbar_press.py --pid 1234 --list
    python toolbar_press.py --pid 1234 --press 308
"""
import argparse
import ctypes
import ctypes.wintypes as w
from ctypes import byref

user32 = ctypes.windll.user32
user32.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.SendMessageW.restype = w.LPARAM
TB_BUTTONCOUNT = 0x0418
TB_GETBUTTON = 0x0417
TB_PRESSBUTTON = 0x0403
TB_GETITEMRECT = 0x041D
TB_GETBUTTONTEXTW = 0x044B


class TBBUTTON(ctypes.Structure):
    _fields_ = [("iBitmap", ctypes.c_int), ("idCommand", ctypes.c_int),
                ("fsState", ctypes.c_ubyte), ("fsStyle", ctypes.c_ubyte),
                ("bReserved", ctypes.c_ubyte * 2), ("dwData", ctypes.c_void_p),
                ("iString", ctypes.c_void_p)]


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


def toolbars(main):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        c = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, c, 64)
        if c.value == "ToolbarWindow32":
            r = w.RECT(); user32.GetWindowRect(h, byref(r))
            out.append((h, r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumChildWindows(main, cb, 0)
    return out


def toolbar_named(main, title):
    """The ToolbarWindow32 inside the wrapper window that carries this title.

    Isis wraps each toolbar in a small LX_ISIS_NoDC window whose text names it - 'File Toolbar',
    'Edit Toolbar', 'View Toolbar', 'Design Toolbar' - which is the only way to tell them apart
    from the outside.
    """
    holder = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def find(h, l):
        n = user32.GetWindowTextLengthW(h)
        b = ctypes.create_unicode_buffer(n + 2); user32.GetWindowTextW(h, b, n + 2)
        if b.value == title:
            holder.append(h)
        return True

    user32.EnumChildWindows(main, find, 0)
    if not holder:
        return None
    tb = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def child(h, l):
        c = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, c, 64)
        if c.value == "ToolbarWindow32":
            tb.append(h)
        return True

    user32.EnumChildWindows(holder[0], child, 0)
    return tb[0] if tb else None


def buttons(tb):
    n = user32.SendMessageW(tb, TB_BUTTONCOUNT, 0, 0)
    out = []
    for i in range(n):
        buf = ctypes.create_string_buffer(ctypes.sizeof(TBBUTTON))
        # TB_GETBUTTON wants the struct in the target process' memory when the toolbar belongs
        # to another process; this only works because we are the same bitness and the app lets
        # us - checked, it returns sane ids
        if not user32.SendMessageW(tb, TB_GETBUTTON, i, ctypes.addressof(buf)):
            continue
        b = TBBUTTON.from_buffer(buf)
        rect = w.RECT()
        user32.SendMessageW(tb, TB_GETITEMRECT, i, ctypes.addressof(rect))
        out.append((i, b.idCommand, b.fsState, rect))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--press", type=int)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--toolbar", type=int, default=0)
    ap.add_argument("--named", default="File Toolbar")
    a = ap.parse_args()

    main_hwnd = main_window(a.pid)
    if main_hwnd is None:
        raise SystemExit("no main window")
    tbs = toolbars(main_hwnd)
    if a.list or a.press is None:
        for ti, (tb, x, y, ww, hh) in enumerate(tbs):
            print("toolbar %d hwnd=%s at %d,%d %dx%d" % (ti, tb, x, y, ww, hh))
            for i, cid, state, rect in buttons(tb):
                print("   button %-2d command %-8d state=%-3d rel rect %3d,%-3d %3dx%-3d"
                      % (i, cid, state, rect.left, rect.top,
                         rect.right - rect.left, rect.bottom - rect.top))
        return

    tb = toolbar_named(main_hwnd, a.named) or tbs[a.toolbar][0]
    hit = [b for b in buttons(tb) if b[1] == a.press]
    if not hit:
        raise SystemExit("no button with command %d on toolbar %d" % (a.press, a.toolbar))
    user32.SendMessageW(tb, TB_PRESSBUTTON, a.press, 1)
    user32.SendMessageW(tb, TB_PRESSBUTTON, a.press, 0)
    print("pressed command %d on toolbar %d" % (a.press, a.toolbar))


if __name__ == "__main__":
    main()
