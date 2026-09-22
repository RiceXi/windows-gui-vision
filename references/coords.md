# Where a design coordinate is on screen

Measured on Proteus ISIS 7.08 SP2 with the window maximized on a 1440x900 screen.

Clicking a pin means clicking a place, and a place in a schematic is a number in the file. The
bridge between the two is the coordinate display: ISIS shows the pointer's position in design
inches at the bottom right of the window. Move the pointer somewhere, capture the window, OCR
that corner, and the application has just told you what that pixel is worth.

```powershell
powershell -File scripts/proteus_input.ps1 -TargetPid <pid> -MoveX 900 -MoveY 300 -Focus
powershell -File scripts/capture_window.ps1 -OutPath c.png -ProcessId <pid>
python scripts/crop.py c.png crops --box 1230,790,1416,826 --prefix coord --scale 6
powershell -File scripts/ocr.ps1 -Path crops\coord00.png
```

Two readings give the whole mapping:

| pointer (screen px) | readout (inches) |
| --- | --- |
| 900, 300 | +1.100, +1.500 |
| 1200, 300 | +4.100, +1.500 |

300 pixels for 3.000 inches, and the sign flips vertically: **100 pixels per inch, y up**. The
readout is restricted to 1 thou, so use round numbers and check the arithmetic rather than
trusting a single reading. In this case:

```
design_x = (screen_x - 790) / 100
design_y = (450 - screen_y) / 100
```

The scale is a property of the display and the zoom level, not of the design, so re-measure it
after changing either. The origin moves with the window, so re-measure that too.

Two details worth knowing before you rely on a click:

ISIS has real time snap, so a pointer within a few pixels of a pin end or a wire is snapped
onto it. That is what makes this accurate enough to be useful: 100 px/in means a 0.1 inch grid
step is 10 pixels, and the snap pulls in the last few pixels of error.

The OCR gets the decimal point wrong often enough to be worth care. "+1100,0" and "+1.100" are
the same reading; the digits are what matter, and the scale check catches a misread quickly.
