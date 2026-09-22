---
name: windows-gui-vision
description: Drive and read Windows desktop apps when you cannot see images. Gives window-exact screenshots that ignore occluding windows and the mouse cursor, image reading through a vision API or Windows OCR, pixel measurement for the things vision gets wrong, a way to map app widgets to click coordinates that survives a different DPI or monitor, and a routine for turning a GUI session into screenshot evidence inside a document. Use it for Windows GUI automation, for producing screenshot evidence, and for working out why a capture or a click went wrong.
metadata:
  short-description: See and drive Windows GUI apps
---

# windows-gui-vision

One loop, and everything here serves it:

capture the right pixels -> read them -> act -> prove the action landed.

Reach for this when you have no image input, when you need screenshot evidence of what a GUI
actually showed, or when captures keep coming back with the wrong window in them.

## Before anything else

```
python scripts/verify_env.py
```

It checks the interpreter, the Python packages, the vision API key, PowerShell, and that the
pixel helpers run. If something is missing see [references/setup.md](references/setup.md),
which also covers copying this folder to another machine.

## Working order

Find the window first. `scripts/wins.ps1 -Filter '*Notepad*'` lists handles, process ids,
titles, rects in logical pixels and whether the window is maximized. Maximize the target
before doing anything on a canvas.

Then capture its own pixels:

```
powershell -File scripts/capture_window.ps1 -OutPath shot.png -ProcessId <pid>
```

That is PrintWindow, so windows on top of the target and the mouse cursor are simply not in
the image, and the target does not need to be focused. If you get a black bitmap, the client
area is GPU-composited; use `scripts/grab_foreground.ps1` and move the pointer somewhere
harmless first.

Reading the capture comes next, and the cheap tool is usually the right one:

| you want to know | use |
| --- | --- |
| roughly what is this, and is it selected | `scripts/see.py` |
| exactly what does this text say | `scripts/ocr.ps1` |
| exactly where is this widget | `scripts/clusters.py`, `scripts/colorfind.py` |
| is there ink here, where does this line end | `scripts/region_ascii.py` |
| did my action change anything | `scripts/diffshots.py` |

Then act, and observe again. Element indexes, screenshot ids and coordinates belong to the
observation that produced them and nothing else.

Then check. Two captures through `diffshots.py`, or look for the ink you expected with
`clusters.py`. What a click returns tells you nothing about whether it did anything.

## Coordinates that survive a resolution change

Applications lay themselves out in logical pixels. The layout is therefore identical on a
1080p laptop and a 4K monitor at 200%, and only the screenshot-to-input scale factor changes.

```
python scripts/calibrate.py --print window.png --screen screenshot.png --out calib.json
python scripts/layout.py init layout.json --from calib.json --app "My App"
python scripts/layout.py click layout.json generators_button --print-width 1416 --shot-width 2804
```

`calibrate.py` finds the canvas rectangle, the icon column with its button pitch, and the
list rows with their pitch. `layout.py` keeps the named anchors in logical pixels and applies
the measured scale when you ask where to click. How the detection works, and what to do when
it finds too much, is in [references/calibration.md](references/calibration.md).

## Things I keep having to relearn

Vision is good at "what is this" and bad at coordinates, small text and inventories. Ask it
about one tight crop, ask a yes/no question, and check anything numeric against OCR or a
measurement. A single confident answer about whether a figure is complete is worth nothing.

A click that does nothing usually means the wrong window, a dialog you did not notice, or a
stale observation. It is rarely the coordinate. Capture and look before clicking again.

Modal dialogs often cannot be enumerated as windows at all. Try the keyboard first - `Return`
for the default button, `Escape` to cancel, remembering that some apps make the destructive
button the default. And switch to an English keyboard layout before sending single-letter
accelerators, because a Chinese or Japanese IME eats them and the menu never opens.

Cropping is where figures go wrong, not capturing. Run `scripts/edgecheck.py` over the final
crops; ink on the rim means you cut through the thing you were photographing.

An application that ignores the file you opened looks exactly like one that loaded it and
showed you an empty canvas, and it looks like a hang if you keep waiting. When you launch an
app with a document, find the thing in its window title that proves the document arrived - for
ISIS 7 that is the file name before `- ISIS Professional` - and check it before you go on.

Keep the working files out of the folder you are delivering. Captures, crops, calibration
json and scratch scripts belong in a sibling working directory.

## Reference

| file | contents |
| --- | --- |
| [setup.md](references/setup.md) | dependencies, environment variables, moving the folder to another machine |
| [capture.md](references/capture.md) | PrintWindow and its black-bitmap failure, screen grabs, cursor, DPI |
| [vision.md](references/vision.md) | what to ask a vision model, what not to, and how to check its answers |
| [pixels.md](references/pixels.md) | clusters, colour search, ASCII region dumps, edge checks, diffs, crops |
| [calibration.md](references/calibration.md) | logical vs screenshot space, calibrate.py, layout.py, labelling widgets |
| [interaction.md](references/interaction.md) | clicking, typing, IMEs, modal dialogs, canvas placement |
| [coords.md](references/coords.md) | turning a design coordinate into a screen pixel, via the application's own readout |
| [docx-report.md](references/docx-report.md) | getting captures into a Word deliverable and proving they are right |
| [proteus.md](references/proteus.md) | Proteus ISIS/ARES: modes, object lists, bundled samples, its own traps |
| [dsn-format.md](references/dsn-format.md) | Proteus `.DSN` layout, and which byte edits survive a load |
| [dsn-generate.md](references/dsn-generate.md) | what an edit does to a `.DSN`, and the version of it that failed |
| [dsn-append.md](references/dsn-append.md) | adding a component to a `.DSN` from a script, verified, and what is still missing |
| [dsn-wires.md](references/dsn-wires.md) | adding a wire by script: the tail block, the link fields, and the verified recipe |
| [dsn-build-circuit.md](references/dsn-build-circuit.md) | the whole workflow: definitions, instances, pin positions, wires, and the check after each |
| [dsn-templates.md](references/dsn-templates.md) | lifting part records out of existing designs into a json library |

`scripts/dsn_templates.py` builds that library and `scripts/dsn_add_component.py` is the
original single-part edit. `scripts/dsn_append.py` is the one that produces designs ISIS
accepts, and `scripts/design_loadcheck.ps1` is how you find out whether a generated design
really loaded.
