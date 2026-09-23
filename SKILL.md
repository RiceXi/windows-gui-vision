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
| [dsn-wire-slots.md](references/dsn-wire-slots.md) | **the current wire rule**: splice point, the per-pin connection slots, and the byte check behind them |
| [dsn-wire-load-test.md](references/dsn-wire-load-test.md) | **which written wires the loader accepts**: the shape sequence that loads, and the positions that crash |
| [dsn-draw-wires.md](references/dsn-draw-wires.md) | **the wiring route that works**: draw in the application from a coordinate list, and the four details it needs |
| [dsn-writer-plan.md](references/dsn-writer-plan.md) | what of the writer is done, what is left, smallest first |
| [dsn-part-group.md](references/dsn-part-group.md) | a part's record and the wires it owns, measured section by section |
| [dsn-hand-wire.md](references/dsn-hand-wire.md), [dsn-connection-list.md](references/dsn-connection-list.md), [dsn-tap-junction.md](references/dsn-tap-junction.md) | the hand-drawn ground truths these rules came from |
| [dsn-pin-map.md](references/dsn-pin-map.md) | the pin map a placed part carries, and which unit gets which physical pins |
| [dsn-embedded-definitions.md](references/dsn-embedded-definitions.md) | why a scripted part is a stand-in until the design is opened and saved once |
| [dsn-build-circuit.md](references/dsn-build-circuit.md) | the whole workflow - definitions, instances, pin positions, wires, the check after each, and the end-to-end run |
| [dsn-templates.md](references/dsn-templates.md) | lifting part records out of existing designs into a json library |
| [proteus-modal-notice.md](references/proteus-modal-notice.md) | the launch dialog that disables the main window, and what does not dismiss it |
| [proteus-toolbar.md](references/proteus-toolbar.md) | the left mode toolbar's buttons, named from the status bar, and the two checks for "am I on a pin" |
| [proteus-view-drift.md](references/proteus-view-drift.md) | why the same design does not always come back at the same scroll position |

`scripts/dsn_templates.py` builds that library and `scripts/dsn_add_component.py` is the
original single-part edit. `scripts/dsn_append.py` is the one that produces designs ISIS
accepts, and `scripts/design_loadcheck.ps1` is how you find out whether a generated design
really loaded.

To build a circuit from a description, `scripts/dsn_build_circuit.py` runs the two editors in
order - instances first, then wires - and the write-up at
[dsn-build-circuit.md](references/dsn-build-circuit.md) says what has to be true of the base
design before it can.

For the wire half, read [dsn-wire-load-test.md](references/dsn-wire-load-test.md) before trying
anything: a wire written into the file loads, but the application resolves a wire's ends through
its own ledger, so on save it puts *other* coordinates there. The measured state is that the file
route is trustworthy for instances (`dsn_add_instance.py`) and not yet for wires - wires have to
be drawn in the application for their geometry to be real. `scripts/dsn_rec_diff.py` compares two
designs part by part, which is how the `.DSN` layout was read.

The application side works from a script too: `scripts/proteus_dismiss_notice.ps1` presses OK on
the launch notice by message, so the main window stops being disabled and clicks reach it;
`_re/scratch/isis_save_roundtrip.ps1` opens a design, saves it and closes it; and
`scripts/dsn_draw_wires.ps1` draws a list of wires on the canvas, which is how wires get into a
design at all - see [dsn-draw-wires.md](references/dsn-draw-wires.md). The acceptance test for
anything generated is a save round trip followed by counting instances and wires in the saved file
- a design can load, show its name in the title, and still come back with objects missing.

Five more, all measured rather than guessed: `scripts/forcefocus.ps1` brings a window to the
front for real, which is what makes clicks land when a second copy of the application is open
behind the user's own; `scripts/mouse.ps1` sends one real click, a double click or a right click
from a single process; `scripts/wintop.ps1` floats a window above the rest; `scripts/dialog_fill.py`
fills a dialog's edit box and presses its button by message, which sidesteps the keyboard and the
IME; and `scripts/capture_hwnd.py` photographs a window by class, which is the only way to read a
popup menu. On the design side, `scripts/dsn_objects.py` lists what a saved file really holds -
parts with anchors, terminals with their net names, wires with their points -
`scripts/dsn_set_terminal_name.py` renames a terminal by rewriting the file, and
`scripts/probe_toolbar.ps1` names the mode toolbar buttons for the window in front of you, since
they move with it.
