#!/usr/bin/env python3
"""Drive Isis's Pick Devices dialog by messages: type a keyword, check the result list, add it.

The dialog is a normal Windows dialog, so this needs no foreground and no keyboard:

  * `WM_SETTEXT` puts the keyword in the edit box (its control id is read from the control);
  * a `WM_COMMAND` carrying `EN_CHANGE` makes the dialog actually filter - setting the text
    alone does not, which is the sort of thing that makes a script look broken;
  * `LVM_GETITEMCOUNT` / `LVM_GETNEXTITEM` read the result list (both integer-only messages, so
    they are safe to send across processes - unlike the ones that take a pointer);
  * `BM_CLICK` on 确定 adds the device.

    python pick_device.py --pid 1234 --dialog "Pick Devices" --keyword 74LS00
    python pick_device.py --pid 1234 --dialog "Pick Devices" --list
"""
import argparse
import ctypes
import ctypes.wintypes as w
import time
from ctypes import byref

user32 = ctypes.windll.user32
user32.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.SendMessageW.restype = w.LPARAM
# WM_SETTEXT carries a string pointer; the system marshals it for us, but the typed prototype
# above refuses anything that is not an integer, and ctypes caches one function object per
# library, so this needs its own prototype rather than another look-up
_SendProto = ctypes.WINFUNCTYPE(w.LPARAM, w.HWND, w.UINT, w.WPARAM, ctypes.c_void_p)
send_raw = _SendProto(("SendMessageW", ctypes.windll.user32))

WM_SETTEXT = 0x000C
WM_COMMAND = 0x0111
EN_CHANGE = 0x0300
BM_CLICK = 0x00F5
LVM_GETITEMCOUNT = 0x1004
LVM_GETNEXTITEM = 0x100C
LVNI_SELECTED = 0x0002
LVM_GETITEMTEXTW = 0x1073        # takes a pointer - do not send this across processes


def find_dialog(pid, title):
    hits = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        p = ctypes.c_ulong(); user32.GetWindowThreadProcessId(h, byref(p))
        n = user32.GetWindowTextLengthW(h)
        t = ctypes.create_unicode_buffer(n + 2); user32.GetWindowTextW(h, t, n + 2)
        if p.value == pid and user32.IsWindowVisible(h) and title in t.value:
            hits.append((h, t.value))
        return True

    user32.EnumWindows(cb, 0)
    return hits[0] if hits else (None, None)


def children(hwnd):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        c = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, c, 64)
        n = user32.GetWindowTextLengthW(h)
        t = ctypes.create_unicode_buffer(n + 2); user32.GetWindowTextW(h, t, n + 2)
        out.append((h, c.value, t.value, user32.GetDlgCtrlID(h),
                    bool(user32.IsWindowVisible(h))))
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--dialog", default="Pick Devices")
    ap.add_argument("--keyword")
    ap.add_argument("--ok", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    dlg, title = find_dialog(a.pid, a.dialog)
    if not dlg:
        raise SystemExit("dialog %r not found" % a.dialog)
    kids = children(dlg)
    edit = next((k for k in kids if k[1] == "Edit" and k[4]), None)
    view = next((k for k in kids if k[1] == "SysListView32"), None)
    ok = next((k for k in kids if k[1] == "Button" and "确定" in k[2]), None)
    if a.list:
        print("dialog %r  edit=%s view=%s ok=%s" % (title, edit and edit[0],
                                                    view and view[0], ok and ok[0]))
        return
    if not edit:
        raise SystemExit("no keyword edit box")
    send_raw(edit[0], WM_SETTEXT, 0, ctypes.c_wchar_p(a.keyword))
    # the filter only re-runs when the dialog hears about the change
    user32.SendMessageW(dlg, WM_COMMAND,
                        (edit[3] & 0xFFFF) | (EN_CHANGE << 16), edit[0])
    time.sleep(0.8)
    if view:
        count = user32.SendMessageW(view[0], LVM_GETITEMCOUNT, 0, 0)
        sel = user32.SendMessageW(view[0], LVM_GETNEXTITEM, -1, LVNI_SELECTED)
        print("keyword %r -> %d result(s), selected index %s" % (a.keyword, count, sel))
        if count == 0:
            print("nothing matched - not pressing 确定")
            return
    if a.ok:
        if not ok:
            raise SystemExit("no 确定 button")
        user32.SendMessageW(ok[0], BM_CLICK, 0, 0)
        print("pressed 确定")


if __name__ == "__main__":
    main()
