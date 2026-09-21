# Capturing a window

## Four ways, in the order I try them

`capture_window.ps1` uses PrintWindow. The application redraws itself into a bitmap I control,
so other windows on top of it and the mouse cursor are not in the result, and the window does
not have to be focused. This is what you want for evidence. Pick the window by `-TitlePattern`
or `-ProcessId`; `-ClientOnly` drops the frame.

`grab_foreground.ps1` raises the window and copies that rectangle off the composited desktop.
Use it when PrintWindow comes back black. Everything on top of the window is now in the
picture, cursor included.

`screen_capture.ps1` copies the whole desktop. Mostly useful for working out what is actually
in front of you.

Computer Use screenshots (`sky.get_window_state`) are the same screen-region grab, so they
carry the same occlusion problem. Fine for driving, poor for evidence.

## The black bitmap

PrintWindow asks the app to draw itself. Apps whose client area is GPU-composited - Qt Quick,
WebEngine, Electron, a lot of modern toolkits - answer with black. You get a correctly sized
all-black file, which is easy to mistake for a dark theme.

Check the ink instead of the thumbnail:

```
python scripts/region_ascii.py shot.png 0,0,400,300 --thresh 150
```

"no ink" plus a near-black mean is the signature. Proteus 7 is GDI and captures fine;
Proteus 8's design window is composited and does not.

## Two overlays to deal with

The mouse cursor is the obvious one. PrintWindow never draws it, screen grabs sometimes do.
If a screen grab is going to be evidence, park the pointer somewhere uninteresting first.

The less obvious one: graphics apps draw their own crosshair or hover highlight on the
canvas, at wherever the pointer was. That is part of the application's drawing, so PrintWindow
faithfully captures it. In Proteus the object selector and canvas both show it. Move the
pointer off the canvas - clicking the title bar does it - and then capture.

## DPI, and why the numbers repeat

Windows scales applications that do not declare DPI awareness. Two families of capture follow
from that, and mixing them up is the main source of "my click is in the wrong place".

PrintWindow and `GetClientRect` work in the application's own pixel grid. A 1416x832 window
is 1416x832 on any machine, and a button sits at the same y in all of them. This is the space
to measure in.

Computer Use screenshots and `screen_capture.ps1` are physical desktop pixels, so their width
is the logical width times the scale factor - 1.0, 1.25, 1.5 or 2.0 in practice.

The conversion is just `screenshot_width / printwindow_width`. Give `calibrate.py` both files
and it prints the factor; `layout.py click` applies it for you. Do not derive it from
`GetWindowRect` - for a DPI-unaware process that rect is virtualized and the arithmetic comes
out slightly wrong.

## Capturing a set of figures without wasting a day

Capture each canvas once, at the best resolution you can, and crop afterwards. Re-running the
GUI to get each figure is slower and will not give you consistent framing.

Keep a before and after capture around every visible action. `diffshots.py` between them is
the cheapest proof you will ever get that the action landed somewhere.

Name captures after the state they show (`c3_gens_placed.png`), not after the step number.
Sooner or later you will diff against the wrong baseline.

Keep the raw captures. Crops can always be redone; a scene you have to recreate cannot.
