#!/usr/bin/env python3
"""Screenshot one window by handle, whatever class it is - popup menus included.

PrintWindow of the main window never contains a menu: a menu is its own window. This finds
the window you name (by process and window class) and captures that window's own pixels.

    python capture_hwnd.py --pid 1234 --class "#32768" --out menu.png
    python capture_hwnd.py --pid 1234 --class "#32768" --list
"""
import argparse
import ctypes
import ctypes.wintypes as w
from ctypes import byref

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def enum_windows():
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(h, byref(pid))
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(h, cls, 128)
        n = user32.GetWindowTextLengthW(h)
        txt = ctypes.create_unicode_buffer(n + 2)
        user32.GetWindowTextW(h, txt, n + 2)
        r = w.RECT()
        user32.GetWindowRect(h, byref(r))
        out.append(dict(hwnd=h, pid=pid.value, cls=cls.value, title=txt.value,
                        left=r.left, top=r.top, w=r.right - r.left, h=r.bottom - r.top,
                        visible=bool(user32.IsWindowVisible(h))))
        return True

    user32.EnumWindows(cb, 0)
    return out


def capture(hwnd, path):
    r = w.RECT()
    user32.GetWindowRect(hwnd, byref(r))
    width, height = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(hwnd, mem, 0)
    # pull the bits out of the bitmap and hand them to PIL through a .bmp round trip
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG),
                    ("biPlanes", w.WORD), ("biBitCount", w.WORD), ("biCompression", w.DWORD),
                    ("biSizeImage", w.DWORD), ("biXPelsPerMeter", w.LONG),
                    ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                    ("biClrImportant", w.DWORD)]

    hdr = BITMAPINFOHEADER()
    hdr.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    hdr.biWidth = width
    hdr.biHeight = -height          # top-down
    hdr.biPlanes = 1
    hdr.biBitCount = 24
    hdr.biCompression = 0
    stride = ((width * 3 + 3) // 4) * 4
    buf = ctypes.create_string_buffer(stride * height)
    gdi32.GetDIBits(mem, bmp, 0, height, buf, byref(hdr), 0)

    from PIL import Image
    img = Image.frombuffer("RGB", (width, height), buf, "raw", "BGR", stride, 1)
    img.save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    return ok, width, height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--class", dest="cls")
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    wins = [x for x in enum_windows() if (a.pid is None or x["pid"] == a.pid)
            and (a.cls is None or x["cls"] == a.cls)]
    if a.list:
        for x in wins:
            print(x)
        return
    if not wins:
        raise SystemExit("no window matched")
    x = wins[0]
    ok, width, height = capture(x["hwnd"], a.out)
    print("printwindow=%s %dx%d -> %s (class %s, title %r)"
          % (ok, width, height, a.out, x["cls"], x["title"]))


if __name__ == "__main__":
    main()
