#!/usr/bin/env python3
"""Run a menu command by message, so it does not depend on focus or on the keyboard.

Keystrokes go to whichever window the user's session has focused, and a second application
instance opened for a comparison will not get them no matter what SetForegroundWindow says.
A menu command sent as WM_COMMAND to the window itself always arrives.

    python menu_command.py --pid 1234 --list              # top level menus
    python menu_command.py --pid 1234 --list --menu 0     # items of the first menu, with ids
    python menu_command.py --pid 1234 --menu 0 --item 保存
"""
import argparse
import ctypes
import ctypes.wintypes as w
from ctypes import byref

user32 = ctypes.windll.user32
WM_COMMAND = 0x0111
MIIM_ID = 0x00000002
MIIM_STRING = 0x00000040


class MENUITEMINFO(ctypes.Structure):
    _fields_ = [("cbSize", w.UINT), ("fMask", w.UINT), ("fType", w.UINT),
                ("fState", w.UINT), ("wID", w.UINT), ("hSubMenu", w.HMENU),
                ("hbmpChecked", w.HBITMAP), ("hbmpUnchecked", w.HBITMAP),
                ("dwItemData", ctypes.c_void_p), ("dwTypeData", ctypes.c_wchar_p),
                ("cch", w.UINT), ("hbmpItem", w.HBITMAP)]


def main_window(pid):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        p = ctypes.c_ulong(); user32.GetWindowThreadProcessId(h, byref(p))
        if p.value != pid or not user32.IsWindowVisible(h):
            return True
        r = w.RECT(); user32.GetWindowRect(h, byref(r))
        if r.right - r.left > 800:
            found.append(h)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def item_text(hmenu, index):
    buf = ctypes.create_unicode_buffer(256)
    n = user32.GetMenuStringW(hmenu, index, buf, 256, 0x00000400)  # MF_BYPOSITION
    return buf.value if n else ""


def item_id(hmenu, index):
    info = MENUITEMINFO()
    info.cbSize = ctypes.sizeof(MENUITEMINFO)
    info.fMask = MIIM_ID
    user32.GetMenuItemInfoW(hmenu, index, True, byref(info))
    return info.wID


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--menu", type=int)
    ap.add_argument("--item")
    ap.add_argument("--id", type=int,
                    help="send WM_COMMAND with this id directly - safer than matching a "
                         "localised menu string, which a non-UTF-8 console mangles")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    hwnd = main_window(a.pid)
    if hwnd is None:
        raise SystemExit("no main window for pid %d" % a.pid)
    menubar = user32.GetMenu(hwnd)
    if a.id is not None:
        user32.SendMessageW(hwnd, WM_COMMAND, a.id, 0)
        print("sent WM_COMMAND %d" % a.id)
        return
    if a.menu is None:
        for i in range(user32.GetMenuItemCount(menubar)):
            print("%2d  %s" % (i, item_text(menubar, i).replace("&", "")))
        return

    sub = user32.GetSubMenu(menubar, a.menu)
    if a.list or not a.item:
        for i in range(user32.GetMenuItemCount(sub)):
            text = item_text(sub, i).replace("&", "").replace("\t", "  ")
            print("%2d  id=%-6d %s" % (i, item_id(sub, i), text))
        return

    for i in range(user32.GetMenuItemCount(sub)):
        text = item_text(sub, i).replace("&", "")
        if a.item in text:
            cid = item_id(sub, i)
            user32.SendMessageW(hwnd, WM_COMMAND, cid, 0)
            print("sent WM_COMMAND %d for %r" % (cid, text))
            return
    raise SystemExit("no item matching %r; try --list" % a.item)


if __name__ == "__main__":
    main()
