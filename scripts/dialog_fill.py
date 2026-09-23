#!/usr/bin/env python3
"""Type into a modal dialog's first edit box and press its default button.

Keyboard input would go through the IME and the active window; this talks to the controls
directly instead, which is what makes it reliable and language-independent:

    python dialog_fill.py --pid 1234 --dialog "Edit Terminal Label" --text "VCC" --ok
    python dialog_fill.py --pid 1234 --dialog "Edit Terminal Label" --list

WM_SETTEXT is sent to the first Edit child; --ok sends WM_COMMAND with IDOK, which is what the
default button does, so a dialog with an unusual button layout still gets the ordinary result.
"""
import argparse
import ctypes
import ctypes.wintypes as w
from ctypes import byref

user32 = ctypes.windll.user32
WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_COMMAND = 0x0111
BM_CLICK = 0x00F5


def windows(pid=None, cls=None, title=None):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(h, byref(p))
        c = ctypes.create_unicode_buffer(128); user32.GetClassNameW(h, c, 128)
        n = user32.GetWindowTextLengthW(h)
        t = ctypes.create_unicode_buffer(n + 2); user32.GetWindowTextW(h, t, n + 2)
        if (pid is None or p.value == pid) and (cls is None or c.value == cls) \
                and (title is None or title in t.value):
            out.append(dict(hwnd=h, pid=p.value, cls=c.value, title=t.value,
                            visible=bool(user32.IsWindowVisible(h))))
        return True

    user32.EnumWindows(cb, 0)
    return out


def children(hwnd):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        c = ctypes.create_unicode_buffer(128); user32.GetClassNameW(h, c, 128)
        n = user32.GetWindowTextLengthW(h)
        t = ctypes.create_unicode_buffer(n + 2); user32.GetWindowTextW(h, t, n + 2)
        r = w.RECT(); user32.GetWindowRect(h, byref(r))
        out.append(dict(hwnd=h, cls=c.value, title=t.value,
                        visible=bool(user32.IsWindowVisible(h)),
                        x=r.left, y=r.top, w=r.right - r.left, h=r.bottom - r.top))
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return out


def text_of(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    b = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(hwnd, b, n + 2)
    return b.value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--dialog", default="")
    ap.add_argument("--class", dest="cls", default="#32770")
    ap.add_argument("--text")
    ap.add_argument("--ok", action="store_true")
    ap.add_argument("--click-button")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    wins = windows(a.pid, a.cls, a.dialog)
    if not wins:
        raise SystemExit("no dialog matched")
    dlg = wins[0]["hwnd"]
    kids = children(dlg)
    if a.list:
        print("dialog %r" % wins[0]["title"])
        for k in kids:
            print("   %-16s %-34r vis=%-5s at %4d,%-4d %3dx%-3d hwnd=%s"
                  % (k["cls"], k["title"], k["visible"], k["x"], k["y"], k["w"], k["h"],
                     k["hwnd"]))
        return

    if a.text is not None:
        # dialogs in ISIS keep a hidden descriptor "Edit" beside the real one, so prefer the
        # visible control; the label field itself sits inside a ComboBox.
        edit = next((k for k in kids if k["cls"] == "Edit" and k["visible"]), None) \
            or next((k for k in kids if k["cls"] == "Edit"), None)
        if edit is None:
            raise SystemExit("no Edit control in the dialog")
        print("edit hwnd %s was %r" % (edit["hwnd"], text_of(edit["hwnd"])))
        user32.SendMessageW(edit["hwnd"], WM_SETTEXT, 0, ctypes.c_wchar_p(a.text))
        print("set to %r" % text_of(edit["hwnd"]))

    if a.click_button:
        btn = next((k for k in kids
                    if k["cls"] == "Button" and a.click_button in k["title"]), None)
        if btn is None:
            raise SystemExit("no button matching %r; try --list" % a.click_button)
        user32.SendMessageW(btn["hwnd"], BM_CLICK, 0, 0)
        print("clicked %r" % btn["title"])
    elif a.ok:
        user32.SendMessageW(dlg, WM_COMMAND, 1, 0)
        print("sent IDOK")


if __name__ == "__main__":
    main()
