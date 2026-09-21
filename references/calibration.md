# Coordinates that still work on someone else's screen

## The problem with pixel constants

The first version of this folder had a table of y coordinates for Proteus's toolbar. It
worked, on my machine, at 200% scaling. Anywhere else it was a list of meaningless numbers.

What fixed it: applications lay themselves out in logical pixels, so a maximized window has
the same geometry on a 1080p screen, a 4K screen and a laptop at 125% - only the number of
physical pixels per logical pixel changes. So measure widgets once in the logical grid, keep
them in a json file, and convert to input coordinates at run time using a scale factor you
measure rather than assume.

## Measure both spaces

```
powershell -File scripts/capture_window.ps1 -OutPath pw.png -ProcessId <pid>
```

and, for the physical side, whatever your input tool hands back - for Computer Use,
`sky.get_window_state({window})` and save `screenshots[0]`.

## Let the detector find the geometry

```
python scripts/calibrate.py --print pw.png --screen shot.png --out calib.json
```

It reports the dominant background colour and the canvas rectangle, the icon column (the
narrow left strip with the most distinct ink bands, with every band centre and the pitch),
the list rows (the longest evenly spaced run of text rows in the side panel, with first row
and pitch), and the scale factor if you gave it both captures.

If the defaults misfire, the knobs are `--icon-dark` and `--text-dark` (raise them for pale
themes, defaults are 190 and 200), `--toolbar-strip 0.004,0.018` to pin the icon column by
hand, and `--panel-top` for where the side panel starts.

Sanity checks worth doing once: the icon pitch should be constant to a pixel or two, the list
pitch should match the row height you can see, and the canvas should not start at the left
edge of the window. If the list in your capture is empty, you get `null` for the rows - that
is the state of the window, not a bug, so capture one with a populated list.

## Name the widgets once

The detector says where the buttons are; it cannot know what they do. Either index into
`toolbar.buttons_y` if you know the order, or probe: click a candidate, capture, and read the
title of the panel it switched to. Write the mapping down and it is good forever, for that
app version.

```
python scripts/layout.py init layout.json --from calib.json --app "Proteus ISIS 7"
python scripts/layout.py set  layout.json generators_button 14,346 --note "mode toolbar"
python scripts/layout.py row  layout.json 7
```

`row` returns the centre of list row 7 from the calibrated first row and pitch, so a list of
twenty items costs one anchor rather than twenty.

## Turn an anchor into a click

```
python scripts/layout.py click layout.json generators_button --print-width 1416 --shot-width 2804
# generators_button: logical (14, 346) x scale 1.9802 -> input (28, 685)
```

Pass `--scale` if you know it, both widths if you have both captures, or nothing to reuse the
scale stored in the calibration. `--offset dx,dy` shifts the aim in logical pixels, which is
handy for "a bit to the right of this anchor", and `--json` gives you the numbers for a
script.

## Two things that still catch me

A window that is not maximized has different geometry. Maximize first, or at least calibrate
in the state you plan to drive it in.

For a DPI-unaware process the rect Windows reports is virtualized and does not match
physical/scale. Use the two captures to get the factor; do not do arithmetic on the rect.

## Checking that this actually holds

`scripts/selftest_scaling.py` resamples one capture, calibrates each size, and checks that
every measured distance scales with the image. Real output for a maximized Proteus ISIS 7
window:

```
scale   img       icon pitch  list pitch  icon x      verdict
0.75    1062x624  17          -           18          proportional (not detected: list)
1.00    1416x832  22          13          25          proportional
1.25    1770x1040 27          16          31          proportional
1.50    2124x1248 33          20          37          proportional
2.00    2832x1664 43          26          50          proportional
```

Everything tracks the scale to within a couple of pixels. The one blank is honest rather than
broken: at 0.75 the row text blurs into the background and the detector returns nothing
instead of inventing a pitch. If a row in that table says MISMATCH, capture bigger before
calibrating - it does not mean the app moved.
