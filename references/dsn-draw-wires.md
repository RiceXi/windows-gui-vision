# Wiring a design from a script: the route that works

Measured on this install, September 2026. `scripts/dsn_draw_wires.ps1` takes a design and a list of
wires (each line `x1,y1,x2,y2`, the two ends being pins in design inches), draws them in Isis and
saves.

The file route was tried first and cannot be made to work for wires: a record spliced into the wire
ledger loads, but on save Isis resolves each wire's ends through its own ledger and writes *other*
coordinates there (`(2.5,1.0) (2.8,1.0) (2.8,0.0)` came back as `(0.7,0.8) (2.8,1.0) (0.7,-0.3)`),
and inserts in some positions make a save drop every instance in the design. So wires are drawn by
the application, and the file is only used to state where the pins are and to check the result.

## What a working run needs

**1. The launch notice pressed away.** Until then the main window is disabled and every click is
discarded. `dsn_draw_wires.ps1` does it in-process: a `WM_COMMAND` to the notice's OK button.

**2. The mapping, measured rather than assumed.** At the default zoom the scale is exactly
**100 px per design inch**. The origin is the window position plus **(785, 440)** - this was read
off the status bar: park the pointer, photograph the window, crop the coordinate readout at
`1240,800`-`1416,822`, and read the two numbers (a vision model reads them where Windows OCR does
not). The window itself moves between runs - `(0,20)` in most runs this session, `(12,10)` in an
earlier one - so the script reads `GetWindowRect` and adds that offset every time. A wrong y origin
of 20-40 px is exactly what made earlier attempts click beside every pin.

**3. Input from a child process.** Pointer moves and clicks injected from the script's own
PowerShell process did not reach Isis at all - every attempt produced no wire. The same calls from
a separate `pwsh` process did. `dsn_draw_wires.ps1` therefore writes a two-line click helper to
`%TEMP%\isis_click_helper.ps1` (an ASCII path on purpose) and runs it as a child for every move and
click.

**4. No capture between the two clicks.** A `PrintWindow` grab of the window between the first and
second click stops the wire from happening - the hover state that makes the pencil appear is lost.
This single detail is why several earlier versions looked like "the click does nothing": they
photographed the canvas to check, and the check itself cancelled the wire. Capture before the run
or after it, never in the middle.

**5. A click on the pin, then a click on the far pin.** No mode has to be selected: Isis starts a
wire from any mode when the pointer rests on a connection point (the cursor becomes a pencil).
The plan is a plain hover (about 1.2 s, so the pencil state settles) then a click.

**6. Never click twice in the same place in quick succession.** Two clicks within the double-click
time - a few hundred milliseconds - count as a double-click on the part, and a part's properties
dialog opens. Everything sent afterwards goes into that dialog instead of the canvas, which looks
exactly like "the clicks do nothing" and wastes a lot of time. The two clicks of a wire are far
apart and the pause between them is over a second, and anything that loops over candidate points
(`dsn_probe_pins.ps1`) must press ESC between attempts and check that no dialog is left behind.

**7. Clear the selection before every wire.** A part that has been clicked once is selected and
drawn red, and while that is true Isis will not start a wire from its pins at all - clicking the pin
of a selected part does nothing. This is the trap that makes a run look like "wiring simply does not
work": a click that lands on the body instead of the pin selects the part, and every later attempt
in that run is dead. Both scripts press ESC before each wire or probe for that reason, and the
same ESC closes a properties dialog if one did open.

**8. A pin's interactive point is the outer end of its own stub.** The user's words: 一般的引脚可交互
位置为该线段的末端端点. A wire drawn to a pin ends exactly there, so the endpoint stored in the file
*is* the pin - but the reverse is not true: a wire's intermediate bend is not a pin. Reading pin
positions out of an existing design therefore means taking wire *endpoints*, never the points in
between. This matters because it is easy to mistake a bend for a pin: in this project a wire ran
`... (-3.3,-1.9) (-4.6,-1.9) (-4.6,-1.6) (-4.5,-1.6)`, and pin 9 of that gate is the last point
(-4.5,-1.6), not the bend at (-4.6,-1.9).

**9. A wire is only *finished* by clicking a connection point.** Clicking a pin starts the wire and
clicking another pin ends it. A click out in free space does not end anything - it leaves the wire
pending, and a later ESC cancels it, so the design ends up unchanged. This is why a probe that drew
from a candidate point to a point in clear space produced nothing at all, and why the run's
self-check ("wires in the file 8 -> 8, drew 0") was right to complain. Two consequences:

* to draw a stub that ends in free space, finish it with a double-click there (and nowhere near a
  part, or a properties dialog opens instead);
* to *test* whether a coordinate is a pin, draw from it to a pin that is already known - if the
  coordinate is not a pin, nothing starts and nothing is written.

## Taps: a net with three or more pins

A pin carries exactly one wire, so a net that has to reach three pins needs a node on one of them.
The gesture, in the order that works - measured on the clean canvas design (two parts, no wires):

1. click the **连接点** (junction) tool in the left column. That column's x is about **18**, not 30:
   at 30 the click lands on the edge of the buttons and usually does nothing, which is what made
   earlier attempts look like the tool was broken;
2. click the point on the wire where the node belongs - the node appears together with the wire
   that leaves it;
3. click the 选择模式 button (x about 18, y about 130) to leave the junction tool;
4. click the node, then the far pin, exactly like any other wire.

What Isis writes is the honest check: the tapped wire is **gone**, replaced by two wires that both
end at the node, plus the new branch as a third. In the test the design went from two wires to four
(split pair plus branch), and a save round trip kept all four routes unchanged.

`dsn_draw_wires.ps1` does this when a wire's first point carries a leading `@` (`@x,y;x2,y2`). Its
wire count check reports the tap by going up by two rather than one.

## Evidence

One wire, drawn by the script from U3:C pin 10 to pin 8 on the five gate base:

* 21588 bytes -> **21670 bytes**, and the wire it wrote is
  `(-4.5,-1.4) (-4.6,-1.4) (-4.6,-1.1) (-3.4,-1.1) (-3.4,-1.5) (-3.5,-1.5)`, six points -
  **byte for byte the same as the wire the user drew by hand earlier**, route and length included;
* a save round trip (open, Ctrl+S, close) left 5 instances and 7 wires, with the wire's geometry
  unchanged.

Three wires in one run (pins of U3:C, U3:B and U3:A): 21588 -> **21834** bytes (82 per wire), 5
instances, 9 wires; after a save round trip, still 5 and 9 with the routes intact.

## What is still missing for arbitrary circuits

A table of pin coordinates per device. The coordinates are in the design (the wires' ends are
exactly the pin positions), so they can be learned automatically: draw a short wire from every pin
to a clear point, save, and read the endpoints back out of the file. That is the next piece -
`references/dsn-pin-map.md` has what is known so far, `_re/scratch/count_objs.py` and
`scripts/dsn_walk.py` read a design back.
