# The window layout drifts, and every coordinate click goes with it

Found while trying to work out why injected wire gestures never produced a wire while injected
placements did.

## What the measurements say

Reading the coordinate display at the bottom right (crop `1140,782,1416,830`, OCR under Windows
PowerShell 5.1) while hovering a spread of screen points:

| pointer | readout |
| --- | --- |
| (300, 400), (500, 400), (700, 400), (900, 400), (1100, 400), (1300, 400) | +0.0, +0.0 |
| (700, 150), (700, 300), (700, 450), (700, 600), (700, 750) | +0.0, +0.0 |

`+0.0, +0.0` is what Isis shows when the pointer is not over the sheet at all. Every point
sampled along both axes reads the same, so either the drawing is off screen or the display is not
following the pointer - and either way a click sent at a coordinate taken from the mapping in
[coords.md](coords.md) does not land on the drawing.

An ink map of the window says the same thing from the other side. Dividing the 1416x832 window
into 16x8 blocks and counting dark pixels, the layout is not the one the calibration describes:

| what | where the ink is |
| --- | --- |
| mode column | x 0..88, all rows - as expected |
| a right hand panel | x 1327..1416, most rows - not in the recorded layout |
| a large dense block | x ~530..970, y ~520..730 - not in the recorded layout |

The recorded calibration has the canvas at x 164..1415, y 84..478 and no right hand panel. So the
window is arranged differently now (a docked panel on the right, and something large sitting in
the lower middle), and the pointer-to-design mapping that everything else is built on has moved
with it.

## What this explains, and what to do

It explains why placement worked and wiring did not: placement clicks a list row and then the
canvas, and even a click that lands in the wrong place still commits *something* somewhere the
record survives; a wire click has to land **on a connection point**, and with the mapping off it
never does. It also invalidates every pin probe recorded in [dsn-wires.md](dsn-wires.md), which is
consistent with those results being unreproducible.

The repair is to re-calibrate rather than to reason further:

1. `python scripts/calibrate.py --print shot.png --out calib.json` on a fresh capture - it reports
   the current icon column, panel and canvas rectangles, so the drift is visible as a diff against
   the recorded values;
2. hover a point inside the *new* canvas and read the coordinate display; two readings give the
   origin and scale. If the display still reads +0.0, +0.0 inside the canvas, the drawing is off
   screen: zoom to the schematic first (or scroll), then measure.
3. only then re-run the wire gesture. Nothing measured before the mapping is re-established
   should be believed.
