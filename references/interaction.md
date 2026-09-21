# Clicking and typing

## In order of preference

Keyboard. Menus, dialogs and toolbars almost always have accelerators - `Alt+F` then a letter,
`Ctrl+S`, `Return` for the default button, `Escape` to back out. Keyboard actions do not care
about layout, resolution or what is on top of the window.

Element index from an accessibility tree, if the app exposes one. They belong to the
observation that produced them, so re-observe before each click rather than reusing an index
from two steps ago.

Coordinates from a calibrated layout ([calibration.md](calibration.md)), or read off a
`ruler.py` zoom for a one-off.

## The IME will eat your accelerators

With a Chinese or Japanese input method active, single-letter accelerators go to the IME and
the menu item never fires. `Alt+F` opens the File menu, `o` does nothing, and the click you
send next lands on the canvas. Switch to a plain English layout first. If you cannot switch
it yourself - the Windows-key shortcut that does it is off limits for automation - prefer
shortcuts that survive, and check with a capture that the dialog you expected actually
appeared.

This one cost me about an hour on a file dialog, during which I concluded several times that
the app had frozen.

## Canvas apps: the first click does nothing

In editors that place objects - EDA, CAD, diagramming - selecting an item in a library list
and then clicking the canvas once frequently does nothing visible. The first click moves the
preview to the pointer. Three clicks are what you need: list item, a nearby free point, then
the target.

Objects drawn as rectangles are the other way round: press at one corner and click the
opposite corner. Two clicks at the same point give you a zero-size object, which looks
exactly like a failed click.

Watch out for the object's anchor. In Proteus a symbol's anchor is its top-left, so a wide
part such as a logic analyser extends two or three grid squares to the right and below the
point you clicked. Size your crop windows accordingly, or leave clearance when placing.

Switching modes sometimes resizes or scrolls the canvas. Do not reuse coordinates measured in
a different mode.

## Dialogs

Application modal dialogs are often not enumerable as top-level windows and cannot be
clicked by element index - you get "element not available in cached app state". Keyboard
first: `Return` takes the default button, `Escape` cancels. Check which one is default before
you press it, because in some apps the default discards your work; Proteus's "save your
changes?" prompt makes 取消 abort the whole action you were trying to perform.

Some dialogs show up in Computer Use as extra screenshot regions rather than as windows. If
so, their pixels are in that region's own coordinate space.

A dialog you have not noticed silently eats every click that follows. If two actions in a row
do nothing, capture and look before doing anything else. And after dismissing one, re-observe:
its text can still be in the accessibility tree you already fetched.

## Typing

Type literal text for paths and names. Never paste from the clipboard unless you control what
is on it.

File dialogs usually preselect the file name stem, so typing replaces it - but if focus is
somewhere else your text is appended to whatever was there, and the result is an invalid
name plus an error dialog. Typing a full path into the name box is a legitimate trick for
saving straight into a project folder; verify the file appeared on disk rather than trusting
the title bar.

Keep typed strings short. A long string in the wrong box is how you end up with a modal error
you did not expect in a screenshot.

## Prove it landed

Canvas actions commit silently. After anything that is supposed to place an object, draw a
wire or change a value:

```
python scripts/diffshots.py before.png after.png --region <what should have changed>
```

Change in the wrong place - a side panel, the status bar, a toolbar - means the action did
not do what you think. And when the app writes a file, parse the file. A saved project is
better evidence than any screenshot: it is what I ended up using to check that thirteen
generators had really been placed, after a screenshot had told me they had when they had not.
