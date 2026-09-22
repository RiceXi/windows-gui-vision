# Proteus notes

Measured on a Chinese-language Proteus 7.8 install (`ISIS.EXE`, `ARES.EXE`). Menu items are
given in Chinese with the English in brackets where it matters; the English builds use the
same layout.

## Capture

ISIS 7 and ARES 7 are GDI applications, so PrintWindow gives you the window's own pixels and
never the cursor. Dialogs come out fine too.

Proteus 8's design window is GPU-composited and captures as solid black. Its home page is a
web view and captures normally. If you need screenshots out of Proteus, 7 is the easier
target.

One quirk worth knowing before you trust a label: this build renders some text objects as the
literal placeholder `<TEXT>` when a font resource is missing. Labcenter's own sample designs
do it too. The symbols themselves draw correctly, so identify a part by its symbol shape, or
by parsing the saved `.DSN`, rather than by reading its caption.

## Layout

Do not hard-code toolbar coordinates - that is what made the first version of this folder
useless on any other machine. Calibrate instead:

```
powershell -File scripts/capture_window.ps1 -OutPath pw.png -ProcessId <isis-pid>
python scripts/calibrate.py --print pw.png --out calib.json
python scripts/layout.py init layout.json --from calib.json --app "Proteus ISIS 7"
```

On a maximized ISIS 7 window the detector lands near these values, which is a useful check
that it found the right things. They are logical pixels, so they are the same at any DPI:

| anchor | value |
| --- | --- |
| mode toolbar icon column | x = 15, button pitch about 22 px |
| object selector list | first row y about 211, pitch about 13 px, click column x about 100 |
| canvas | starts around x 164, y 85 |
| preview pane | about x 43..141, y 94..185 |

If the detector reports far more bands than you expect it has picked up the menu bar and the
window border as well. The button pitch is the reliable signal, and the first regular run of
bands is the mode toolbar.

## What the modes contain

The mode buttons are a single column on the left; the object selector's title and contents
change with the mode. Verified contents:

| mode | list title | items |
| --- | --- | --- |
| 元件模式 | DEVICES | whatever Pick Devices added |
| 终端模式 | TERMINALS | DEFAULT, INPUT, OUTPUT, BIDIR, POWER, GROUND, BUS |
| 器件引脚模式 | PINS | pin types |
| 图表模式 | GRAPHS | ANALOGUE, DIGITAL, MIXED, FREQUENCY, TRANSFER, NOISE, DISTORTION, FOURIER, AUDIO, INTERACTIVE, CONFORMANCE, DC SWEEP, AC SWEEP |
| 激励源模式 | GENERATORS | DC, SINE, PULSE, EXP, SFFM, PWLIN, FILE, AUDIO, DSTATE, DEDGE, DPULSE, DCLOCK, DPATTERN, SCRIPTABLE |
| 虚拟仪器模式 | INSTRUMENTS | OSCILLOSCOPE, LOGIC ANALYSER, COUNTER TIMER, VIRTUAL TERMINAL, SPI DEBUGGER, I2C DEBUGGER, SIGNAL GENERATOR, PATTERN GENERATOR, DC VOLTMETER, DC AMMETER, AC VOLTMETER, AC AMMETER |
| 图纸连接器模式 | PORTS | sheet ports |
| 2D 图形 / 标记 | GRAPHIC STYLES / MARKERS | drawing styles and markers |

Generators and instruments are simulator primitives and are deliberately hidden from Pick
Devices. The mode buttons are the only way to reach them, which is why the toolbar matters.

## Placing things

Components, generators and instruments take three clicks: the list row, a nearby free point,
then the target. One click on the canvas only moves the preview, and it is easy to conclude
the placement failed when it has not started.

`scripts/proteus_place.ps1` does it from a design coordinate. Measured details, all of which
cost time to find:

* the row has to be hit in the text, not the panel. At window coordinates, a click near
  (60..80, 212) lands on the buttons above the list and opens Pick Devices or the Devices
  Libraries Manager instead; row 0 is at about (72, 220) with a 13 pixel pitch below it;
* each click must come from its own process with about a second between them. Two clicks issued
  in one process, 700 ms apart, were ignored; the same two clicks from separate short-lived
  processes placed the part every time;
* the point clicked and the coordinate ISIS stores are not the same point. Clicking design
  (3.600, -1.500) stored the part at (3.292, -1.292) - 0.308 inch left and 0.208 inch above.
  The tool asks for the coordinate you want and clicks at the compensating point;
* asked for (3.600, -1.500) and (2.000, 1.000), it produced (3.592, -1.492) and (1.992, 1.008):
  within 0.01 inch. Both parts were drawn - ink subtraction found 702 pixels where the base
  design has none.
* the target has to be empty canvas. Aimed at (2.000, -1.000) in a design that has graphic
  objects there, the clicks selected one of them instead and opened its editor - the placement
  silently did nothing and a dialog called 编辑瞬态图表 appeared. Check the ink afterwards
  rather than assuming.

What is not solved: where those new parts' pins are. A grid probe over one of them found no
connection points at all, and the pin offset that the design's older parts of the same device
answer to did not work on it. Until that is measured, a newly placed part can be positioned but
not scripted-wired.

`scripts/proteus_probe_pins.ps1` is the instrument for that question, and it is worth knowing it
works before trusting a negative answer from it. It walks a grid of points, clicking each and
then clicking a pin known to work, and pressing Escape after each pass; a wire appears in the
saved design only if the candidate was a connection point.

Run against a pin that is known good, 9 candidates around (0.7, 0.8), it produced exactly one
wire and it ran through the expected route - so the method is sound. Run against a part the
script had just placed, with 60 candidates spread over its symbol including the ends of its
lead lines, it produced none. The reading is that those parts do not answer at their pins, which
makes the placement itself the suspect: three clicks place a symbol that draws and is stored,
but the pins do not come with it.

Two controls keep that reading honest. The same design, same session, same clicks at a pin that
is known good, still produces a wire - so the mode and the mapping are fine when the probe says
no. And the pin positions are not guesswork: a magnified crop put the drawn pin stubs of the new
part at design (1.400, -0.800), (1.400, -1.000) and (2.400, -0.900), and clicking exactly those
two left ones did not start a wire either.

So a part placed by script draws and saves, but does not answer where its own symbol shows its
pins. Here is what that turned out to be.

### The placed instance names a device the design does not define

Placed by hand, with mouse movement between the clicks and a second between each, the result is
the same: the part draws (378 pixels of ink), the file grows by 362 bytes, and its pins still do
not answer a 75-point probe at three pixel spacing around the tips the drawing shows.

The records explain why. In the original design every part carries
`COMPONENT ID = NAND2`, while the instance the placement writes carries
`COMPONENT ID = NAND_2`. Those are different identifiers: the design embeds a definition for
`NAND2`, and the current library places `NAND_2`. What gets drawn is a stand-in for a device the
design cannot resolve, which is why the symbol looks like a plain triangle and why it has no
connection points. The 362 bytes that were added are the instance record and its directory
entry - no definition came with it.

So placing parts from a Labcenter-authored design cannot work, however carefully the clicks are
timed: the design's device list names the current library device while its embedded definitions
use the older identifier. Two ways out, both to be tried next:

* start a fresh design in this installation and add the devices with Pick Devices, so the list
  entry, the instance and the embedded definition all carry the same identifier;
* or use Pick Devices on an older design to add the device again, which embeds the definition
  that goes with the current library.

### Starting from a fresh design, what works so far

Following that first road, step by step, on this install:

1. launching `ISIS.EXE` with no argument opens `UNTITLED`, and its DEVICES list is empty;
2. the accelerator for Pick Devices is the letter `p`, and it only arrives if the window's
   input language is English. Sending `p` with a Chinese IME in place produced a 53x33
   `CiceroUIWndFrame` instead of the dialog. `PostMessage(hwnd, WM_INPUTLANGCHANGEREQUEST,
   0, LoadKeyboardLayout("00000409", 1))` fixes it for that window;
3. in Pick Devices, the keyword box is at window (150, 45), results start at (194, 77) with a
   pitch near 14 pixels, and typing a name then pressing Return accepts the highlighted device.
   Searching `74LS00` and confirming put `74S00` in the design's DEVICES list;
4. File, Save As with `%f` then `a`, typing the path without an extension and pressing Return
   wrote the design - `fresh1.DSN`, 6925 bytes, title changing to `fresh1 - ISIS Professional`.

What does not work yet: placing that device into the fresh design. Clicking its row selects it -
the preview pane changes by ~900 pixels of ink - but the two canvas clicks then change nothing
and the selection reverts, so the file stays at 6925 bytes with no parts in it. The same two
clicks place a part in the older design, so it is not the click injection or the coordinates.
Next: try a different spot and a different gap between the clicks, and watch the preview pane
between them rather than only before and after.

Followed up, step by step, with captures between each one:

| step | what changed |
| --- | --- |
| click the device row | list 124 px, preview pane 896 px - the device is selected |
| move the pointer onto the canvas | canvas 45 px - the symbol follows the pointer |
| one left click | canvas 148 px, then the canvas returns to its previous state |
| move the pointer away | canvas 45 px back - the ghost leaves with it |

The design is empty afterwards: a diff of the final capture against the empty design comes to
zero pixels, and the file is still 6925 bytes with no part records. The status bar is the useful
clue here. Before the click it reads `显示当前加载的元件` (showing the currently loaded
component); with the pointer over the sheet it reads
`COMPONENT U1:A, Value=74S00, Module=<NONE>, Device=74S00, Pinout=[74S00]`. So the device is
loaded and held, and the click is not dropping it - nothing about the design changed.

That `U1:A` is worth a second look: 74LS00 is a four-unit device, and the unit is part of the
name. The next thing to try is a single-unit part - a resistor - to see whether the unit is what
the drop is waiting on.

Tested, and it is not the unit: a resistor from Pick Devices behaves the same way - loaded, the
symbol follows the pointer, and the click does not drop it. Four ways of dropping were tried
against a fresh design and none of them changed the file at all (6925 bytes, no part records):

* one left click on the sheet;
* two left clicks a second apart;
* click, move the pointer slightly, then Return;
* move onto the sheet and press Return without clicking.

Each attempt leaves between 148 and 193 pixels of ink on the canvas that the empty design does
not have - the ghost of the loaded device, drawn where it was left - and the sheet area is not
the issue: the border was located at window x 288..1278, y 99..786 and both click points are
well inside it.

The next variable is the mode. Placing is a component-mode action, and the help is explicit
that a design left in selection mode ignores them; the mode buttons are the icon column on the
left, and which one is active can be read from the pressed state. Check that before trying the
drag variant (press, move, release), which is the one drop method not yet tried.

The mode buttons are higher up than they look. The icon column starts at window y 57 with the
selection tool and y 71 with component mode, on a pitch near 13 pixels - the icons run out
around y 180, where the panel's list begins. The earlier clicks at y 89..197 were below the
icons and hit the panel instead, which is why eight of them left the selector showing DEVICES
without changing anything.

Clicking component mode at (28, 84), selecting the device and clicking the sheet still leaves an
empty design - 6925 bytes, no part records - so the mode is not what the drop is waiting on
either. At this point the drop has been tried four ways, in both modes, on a two-unit device and
a one-unit device, with the sheet area confirmed and the pointer verified as loaded.

### Where this stands (paused mid-investigation)

Two things were still open when this was put down, and both have a saved artifact to start from.

**Placing into a fresh design.** Tried and failed: one click, two clicks a second apart,
click-then-Return, Return alone, and a press-move-release drag; in selection mode and in
component mode; with 74S00 (four-unit) and with RES (single-unit, confirmed present in the
selector as a second row); with the Pick Devices dialog closed and open. Every attempt leaves
`fresh1.DSN` at 6925 bytes with no part records. The same click injection places parts in an
older, sample-derived design, which is why this is filed as an interaction question rather than
a broken tool.

A related trap worth remembering: Ctrl+S writes nothing when the design has not changed, so a
file whose size and timestamp never move is telling you that the edit never happened - not that
the save failed.

**Making an appended part render.** The instance record's `COMPONENT ID` differs between the
sample design (`NAND2`) and the current library (`NAND_2`), which was the leading explanation
for appended parts drawing as a bare reference designator. Rewriting that field in a donor
record - 347 bytes to 346, `\xFF\x06NAND_2` to `\xFF\x05NAND2`, everything else untouched -
produces a design ISIS opens (`AN_idfix.DSN`), but the ink subtraction still finds only 343
pixels against the base, a label and nothing else. So the graphics are not keyed on that field
either, and the search continues from there.

### What a design embeds, and why appended parts were phantoms

Diffing a design before and after placing a device that Pick Devices had just added shows what
the application writes, and it is more than an instance:

* a **739-byte definition block** in the header, holding the device name and a `02 7F COMPONENT`
  object - the symbol;
* a **PINOUT block**, plain text: `PINOUT 74LS00 / ELEMENTS=4 / PINS=14 / IP A = 1,4,10,13 /
  IP B = 2,5,9,12 / OP Y = 3,6,8,11 / PP (VCC) = 14 / PP (GND) = 7 / PINSWAP=A,B /
  GATESWAP=TRUE`;
* the instance record, `FF 04 U3:A ...` with `COMPONENT ID = 74LS00` and the coordinates at
  offset 6 rather than the 4 of an older two-character reference.

That is the explanation for the phantom parts: an appended record only says *who and where*,
and a design can only draw a part whose definition it embeds. Appending a record for a device
the design has never held cannot work, whatever else is patched.

Placing into a design that already has the definition does work: the placed 74LS00 adds 1347
bytes and 563 pixels of ink at the coordinates asked for.

### The directory entry carries a unit and pin map

Cloning that instance - same record, reference `U3:A` to `U4:A`, coordinates moved - gives a
design ISIS opens, but the clone draws as a label again. The difference is in the directory:
ISIS's entry for the multi-unit part reads

```
00 10 | 00 03 | 00 00 | 00 | 04 "U3:A" | 01 00 03 00 01 41 01 31 01 42 01 32 01 59 01 33 | 00 x 6
                                          ^ two fields          ^ "A"->"1"  "B"->"2"  "Y"->"3"
```

and the appended entry, written with the five zero bytes most objects get, has none of it. This
is what `dsn_append.py`'s `entry_tail` parameter is for. Passing the map through did not by
itself make the clone load, so the id and sequence fields in that entry are still suspect - the
ground truth is two entries in one file, `AQ_pick.DSN` (ISIS's own) and `AU_entry.DSN` (ours,
rejected on load).

One more measurement for whoever picks this up: probing the drawn 74LS00 at the edges of its
ink bounding box found no connection points, so its pins are not at the ends of that box.

Chart frames and other rectangles want two different points - one corner, then the opposite
one. Two clicks at the same point give a zero-size frame.

The anchor is the symbol's top-left, not its centre. A logic analyser or pattern generator
extends two or three grid squares right and down from where you clicked, which is why my
first attempt at a figure set had them clipped on the right.

Instruments and probes draw a long dotted leader line down the sheet. A crop that includes it
comes out tall and thin and looks like a mistake; crop to the symbol.

## Simulation

`F12` toggles interactive simulation and the title gains （仿真中……）. For graph-based
simulation, place a GRAPHS object, select it, and press `space`.

Most launches show a notice dialog with no usable accessibility text. Press `Return` to
dismiss it, or it will be sitting in the middle of every screenshot you take afterwards.

## Saving and opening

A new design opens as `UNTITLED`. 文件 → 另存为 (`Alt+F`, `a`) preselects the file name stem,
so typing a full path without the extension and pressing `Return` saves there. A bare name
goes to the install's `BIN\` folder, or to the per-user VirtualStore copy of it under
`AppData\Local\VirtualStore\Program Files (x86)\...`, which sandboxed shells cannot read.

文件 → 新建设计 (`Alt+F`, `n`) asks 保存当前设计的改动? first, with 是/否/取消. 取消 aborts the
entire new-design action, so answer 否 (`n`) to discard and carry on. This one wasted hours:
the dialog kept appearing, I kept cancelling it, and every placement after that landed on the
old canvas instead of a new one.

文件 → 打开 (`Alt+F`, `o`) keeps the previous text in the file name box and appends to it,
which produces 文件名无效. Press `Ctrl+A` first, or skip the dialog entirely:

```
Start-Process ISIS.EXE -ArgumentList '"C:\...\Design.DSN"'
```

When you open a design that way, check that it actually loaded before doing anything else. The
title bar gains the design's file name: `base2 - ISIS Professional` means loaded, plain
`ISIS Professional` means it did not, and a `(未响应)` suffix means it crashed. A design ISIS
will not load fails either silently or with a small dialog that has the same title as the main
window, so the title bar is the cheap check.

## Wires

Click a pin to start a wire, click the destination pin to finish. Pins are at the ends of the
lead lines, which `region_ascii.py` will show you. Click a few pixels off and you select the
part instead; if the symbol goes solid, you hit the body rather than the pin. Afterwards,
compile the netlist or check with a capture that both ends show a connection dot.

The snapping is forgiving enough to script against. Measured: a click 0.03 inch - three pixels
at 100 px/in - off both axes still connected, and the wire ISIS wrote has its endpoints exactly
on the pins, `(0.700, 0.800)` and `(0.700, -0.300)`. So a script does not need exact pin
coordinates, only the right neighbourhood, and the result is verifiable without looking at the
screen: parse the saved design and check where the wire's endpoints ended up.

`scripts/dsn_pins.py` lists the candidates for a part: it takes the endpoints of the wires
around each component and reports them as offsets from the component's anchor. Points shared by
two instances of the same part are its pins; the rest are wire bends. Wire a part once by hand,
read the offsets, and you can place and wire more copies of it by script.

The offsets belong to the *record*, not to the part name. A record carries the instance's
orientation, and a clone keeps it, so offsets measured on one instance transfer to every clone
of that same record. They do not transfer to instances that were placed separately - measured
once: a NAND record lifted from a design with no wires, placed at a new position, did not
connect at the pin offset that another NAND in the base design uses. That is why the donor
sheet approach works and guessing does not: place one instance per part type with the record you
intend to clone, wire it once, and measure.

## Sample designs, which are the fastest way to a waveform

Under `SAMPLES\` in the install directory:

`Generator Scripts\` has Sine Wave, Triangle Wave, Noise Generator, Piecewise Linear Waveform,
Serial Data Generator, SPI Memory Stimulus and QPSK Modulation. They are pre-wired, so running
one gets you a real curve on screen in a couple of minutes. `Graph Based Simulation\` has
Fourier, Mixed, Transfer, Sweep, Lpf, 741noise, Resistor, Diode, Vco, Zin and Zout, named
after the analysis they demonstrate. `Interactive Simulation\Animated Circuits\` puts every
virtual instrument on one sheet. `HELP\` has the manuals: ISIS.chm, LISA.chm for the analysis
types, Instruments.chm for the virtual instruments.

These files are also where you find example instances of parts if you are generating designs
by writing `.DSN` files - see [dsn-generate.md](dsn-generate.md).

## Driving it without fighting it

Activate the ISIS window before any Computer Use capture. Otherwise the Codex or ChatGPT
window is composited into the same screen region and you end up reading chat text as if it
were a dialog.

Extra screenshot regions reported for the ISIS window are usually other windows rather than
dialogs. OCR them before acting on them.

Switch to an English keyboard layout before sending single-letter accelerators. A Chinese IME
swallows them.

Editing a `.DSN` is a good way to read a design, and it works for changes that keep every
record the same size - moving a part, renaming it to an equally long name. Adding objects that
way does not work on 7.08 SP2; see [dsn-generate.md](dsn-generate.md) for the tests. Building a
schematic means driving the GUI, and the saved design is then the evidence trail: a saved
design tells you what is really there, where a screenshot only tells you what was drawn.
