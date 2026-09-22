# The notice at (573, 358) is modal, and closing it disables Isis

This is the root cause behind a long run of "the gesture does nothing" results.

## What it is and what it does

Launching Isis opens a second top-level window of the process: 294x136, titled `ISIS Professional`
like the main window, positioned at screen (573, 358) - over the middle of the canvas.

It does not go away on its own. After a launch, three minutes with no injected input, it is still
there. That matters because while it is up the main window is **modal-disabled**:

* the coordinate display at the bottom right reads `+0.0, +0.0` at every pointer position,
  including positions inside the drawing area - the main window is not tracking the pointer;
* clicks do nothing at all. Clicking the Zoom-to-Schematic toolbar position changed neither the
  ink layout of the window nor anything else - the ink map before and after was byte-identical.

Everything injected while that dialog is up is silently discarded.

## Why closing it is worse than leaving it

`proteus_input.ps1 -CloseNotices` dismisses it by posting `WM_CLOSE` to every visible window of
the process narrower than 700 px. The dialog disappears from the window list - which is why the
close *looks* like it worked - but the main window appears to stay disabled, so every later click
is still thrown away. That is the state most of this session's failed experiments ran in.

## What to do instead

Dismiss it the way a person does: **click its own button**, then verify

1. the window list shows only the main window, and
2. hovering a point in the drawing area makes the coordinate display read a real design
   coordinate instead of `+0.0, +0.0`.

Point 2 is the test that matters, and it is cheap: one hover and one OCR of the bottom right
corner. Until it passes, nothing measured through the GUI means anything.

The dialog's button has not been located yet: `{ENTER}` to the focused dialog did not dismiss it,
and three guesses along its bottom edge did not either. Capturing the dialog's own rectangle with
`screen_capture.ps1` and reading it with `ocr.ps1` is the way to find the button - the first
attempt at that returned empty, so the rectangle needs widening until the text comes back.

## Consequence for everything else in this folder

Any GUI result recorded while this dialog was up must be treated as unmeasured: the pin probes,
the wire-gesture controls, and the placement evidence all date from sessions in this state. The
file-level results (byte-exact instance appends, whole-load checks, the pin-map entry, the
pointer-relocation rule) stand, because they never depended on a click landing.

## It does not accept synthetic input (measured)

`IsWindowEnabled` on the main window returns **False** while the notice is up, which is the
confirmation that this is a modal state rather than a slow load. The notice now has a dismiss
helper - `scripts/proteus_dismiss_notice.ps1` - and none of what it tried worked:

| attempt | result |
| --- | --- |
| `{ENTER}`, `{SPACE}`, `{ESC}`, `~`, `Alt+F4` to the foreground | notice still open, main window still disabled |
| clicking along its bottom edge, every 24 px | notice still open |
| `ShowWindow(SW_SHOW)` then `BringWindowToTop` then `SetWindowPos(HWND_TOPMOST)` then `SetForegroundWindow` | notice still open, main window still disabled |

A screen capture of the notice's own rectangle shows the **main window's canvas**, not a dialog -
so the notice is behind the main window, and clicks aimed at its rectangle land on the disabled
main window instead. `SetForegroundWindow` is refused to a background process, which is why
raising it that way does not help either.

## The next thing to measure, and it is cheap

Before any more attempts at the button: launch Isis, touch nothing, and poll
`IsWindowEnabled(main)` once a second for a couple of minutes. If it flips to true on its own the
window is a slow load and the answer is simply to wait; if it stays false, then a modal dialog
really is holding the process, its own window is not the 294x136 one, and the enumeration that
looks for "a window narrower than the main one" is looking in the wrong place.
