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

* **the design has to be in Component mode (器件) or nothing happens.** Isis remembers the
  mode between sessions, so a directory left in Selection mode swallows every canvas click and
  placement looks like a broken script. The symptom is indistinguishable from a bad click:
  no error, no ink, no record. `proteus_place.ps1` now clicks the Component Mode button first
  (screen (37,133) for a window at (12,10), 1416x832); the mode is also visible in the status
  bar, which reads 器件 in Component mode and 选择模式 in Selection mode - OCR that if a click
  seems to be going nowhere;

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

### Adding an instance of a device the design already embeds, byte exactly

The cleanest ground truth came from placing the *same* device a second time: open the design,
place another 74LS00, save, and diff the two saves. Three edits, and nothing else:

1. **420 bytes inserted at the object-area end** - the instance record,
   `FF 04 "U3:B" ... COMPONENT ID = 74LS00`, coordinates at offset 6. ISIS names the second
   placement as the next unit of the same physical package: the first was `U3:A`, this one
   `U3:B`.
2. **26 bytes inserted in the directory** - the entry for it:

   ```
   00 11 | 00 04 | 00 00 | 00 | 04 "U3:B" | 02 00 03 00 | 01 41 01 34 | 01 42 01 35 | 01 59 01 36 | 00 x 6
   id=17        seq=4                      ^ unit map:   "A"->4      "B"->5      "Y"->6
   ```

   The first unit's map read `01 00 03 00` with `"A"->1 "B"->2 "Y"->3` - the pin numbers of
   that unit. The `seq` field counts *part* entries only: U1, U2, U3:A, U3:B are 1, 2, 3, 4,
   while the graphics entries (P2C...) stay at zero.
3. **four small fields**: the object-area end at head-4, the object id counter at head+19, a
   second counter at head+21 - both went 16,1 then 17,2 then 18,3 as instances were added - the
   u32 in the directory, and the entry count byte.

Applying exactly those edits by script reproduces ISIS's own file byte for byte, with the
two-byte stamp the only difference (`AX_replica.DSN` vs `AW_pick2.DSN`). That makes file-level
instance creation a solved problem for a device the design already carries, and
`dsn_append.py` now uses these offsets, the entry sequence rule and a pass-through
`entry_tail` for the unit map. What is still open: the naming and counters when the placement
opens a *new* package rather than the next unit of an existing one.

### The third placement, and where the unit map comes from

Placing the same device once more gives the next sample, and it settles two things. The name
runs `U3:A`, `U3:B`, `U3:C` - the same physical package, next unit - so a new package only
starts once that package's units are used up. And the entry's unit map is not arbitrary:

```
unit A:  01 00 03 00 | "A"->1  "B"->2  "Y"->3
unit B:  02 00 03 00 | "A"->4  "B"->5  "Y"->6
unit C:  03 00 03 00 | "A"->10 "B"->9  "Y"->8
```

Those numbers are exactly the `PINOUT` block the design carries (`IP A = 1,4,10,13`,
`IP B = 2,5,9,12`, `OP Y = 3,6,8,11`), read unit by unit - including the reversal in unit C,
which is why the map has to be looked up rather than computed. Across the three samples the
entry's id read 16, 17, 18 and its sequence 3, 4, 5, and the two counters after the marker
paired as 16,1 then 17,2 then 18,3.

So for a device the design already embeds, an instance can be written from the file: clone an
existing instance's record, name it as the next unit, and build its entry from the device's own
PINOUT block. What has not been sampled yet is the first placement of a *new* package, which
needs a fifth unit and therefore a fifth placement.

### The fifth placement, and what is still missing

Two more placements settle the naming. The fourth is `U3:D`, and only the fifth opens a new
package, `U4:A` - so a package is filled unit by unit first. Their entries:

```
U3:D  id 19  seq 6  tail 04 00 03 00 "A"->"13" "B"->"12" "Y"->"11"
U4:A  id 20  seq 7  tail 05 00 03 00 "A"->"1"  "B"->"2"  "Y"->"3"
```

which pins down the last two rules: the tail's first field is the *global* unit counter - 5 for
`U4:A`, not 1 - and the pin numbers follow the new unit, so `U4:A` goes back to 1, 2, 3.

`scripts/dsn_add_instance.py` implements all of it: it finds the device's PINOUT, works out
whether the next instance is the next unit or a new package, builds the record and the entry,
and moves the two counters. Its output matches ISIS's on every field tested - name, id,
sequence, unit counter, pin map, record length - and ISIS still rejects the file, because the
entry does not land where ISIS puts it: over two placements ISIS inserts 65 bytes of entry
where the script writes 59, and its insert sits about 240 bytes earlier in the file than the end
of the entry list the parser finds. So there is a second structure near the directory that the
new entries belong to, and finding it is the next concrete step. The script says as much at the
top of the file.

That paragraph was written after the first attempt. Two fixes since: each pin pair in the entry
is a length-prefixed key *and* a length-prefixed value (`01 41 02 31 30` is "A" then "10"), and a
unit entry ends with three zero bytes rather than five. With those, the script's file comes out
the same size as ISIS's, the records carry the same coordinates, the entries are the same
length, and the diff is down from 970 bytes to 109 in 27 runs, all inside the object area. ISIS
still rejects it, so what is left is structural rather than a field value - most likely the
point at which the new record is inserted or the order objects end up in. The two files to
compare are `BB_pick3.DSN` (before) and `BC_pick5.DSN` (ISIS after five placements).

### Where that ended up

The records turned out to sit at identical offsets in both files, so the object order is right;
the residual is inside the two new records and in their entries. Patching the anchor's copies -
it appears three times in a record, once at +6 and again in the COMPONENT ID and COMPONENT VALUE
blocks, with the later two offset by 0.416 inch in y - took the diff from 109 bytes to 67, which
is where it rests. Two things resist:

a record also stores the point that was clicked rather than the anchor it settles on, and
rewriting that pair turns a rejection into a crash, so it is not the plain coordinate pair it
looks like; and flipping the entry's unit counter to little-endian does the same. Both were
reverted, leaving a file that is the right size and the right shape and is quietly refused.

That is the state to resume from: `scripts/dsn_add_instance.py` carries the same note at the
top, and `BB_pick3.DSN` versus `BC_pick5.DSN` is the pair to diff.

### Closed: the instance writer is byte exact

The last 67 bytes came apart in five pieces, and two of them were the reason touching the file
sometimes turned a rejection into a crash rather than fixing it:

* the anchor is written **three** times in a record - at +6, and again in the COMPONENT ID and
  COMPONENT VALUE blocks with a 0.416 inch offset in y - and all three have to move;
* the point that was **clicked** is written as well, about 380 bytes in. It has to be patched,
  but patching every matching pair rewrites an unrelated field and ISIS crashes on the result;
  patching the first match only is what works;
* the record carries its own object id and unit number at +396, little-endian;
* the entry's unit counter is little-endian, while the id and sequence at the head of the same
  entry are big-endian;
* the record's final byte is the object-area sentinel `FF`. A template that had another record
  after it carries `00` there instead, and ISIS will not have it.

One off-by-one too: the stored unit counter is the header's own value, not one more than it -
that alone accounted for five of the last seven bytes.

With those, the script's file differs from ISIS's by the two-byte volatile stamp and nothing
else, and ISIS loads it. Adding an instance of a device a design already embeds is therefore
solved at the file level, and it composes with the wire writer from [dsn-wires.md](dsn-wires.md):
place parts and route wires without the GUI.

### One gap left, and where it is

An instance written this way really is the part - byte-identical file, ISIS opens it, it draws -
and its pins still do not answer a synthetic click. A 187-point probe at 0.1 inch spacing over
one of them produced nothing, and so did the same probe over the 74LS00 that Pick Devices placed
by hand. Compare that with the probe's control run in a Labcenter sample, where nine points
around a known pin produced exactly one wire: there, the point being clicked is one where a wire
already ends.

So the working hypothesis is that a connection point with a wire on it answers a synthetic
click and a bare pin does not - which matters because it is the difference between "place parts
by script and let the GUI wire them" and "place and wire entirely by script". The way to settle
it is to draw one wire on a fresh part by hand, save, and read the coordinates ISIS chose: those
are that part's pin positions, measured rather than guessed, and after that the wire writer can
be pointed at them.

That test was run. A magnified crop located U4:A's pin stubs - the symbol is even labelled 1, 2
and 3 - and clicking exactly at them still produced no wire, so the hypothesis holds: bare pins
ignore a synthetic click, wired connection points do not.

The wire *writer* is the way round it, but it is not general yet either. Pointed at
`BR_replica5.DSN` it produced a design ISIS crashes on, with the two-byte link fields from the
design it was verified in and again with no link fields at all, so the insertion recipe does not
transfer as written. Its own `--find-links` does find this design's candidates (14487 and 14686),
so the offsets are knowable; what has not been re-verified is the live tail block the recipe
moves, which is the part most likely to differ between designs.

So the state of the two halves is: parts, byte exact and verified; wires, verified in one design
and needing the same ground-truth treatment for the next one. Getting that ground truth means
drawing one wire by hand in a design that already has the new parts, which works as long as the
wire starts and ends on existing connection points - the sample design's own pins are good for
that.

### Wires, second design: done, and the two halves together

That ground truth came out as expected. In `BC_pick5.DSN`, drawing a wire between the sample
design's own pins inserts 82 bytes at the object-area end and touches: the object-area end field,
the directory's offset, **the two link fields at 14487 and 14686** - exactly what
`dsn_add_wire.py --find-links` reports for that design - and four single-byte counters inside the
component records.

Writing the same route with the script, with those two link offsets, produced a file that ISIS
loads and that differs from ISIS's own by 8 bytes: four of those single-byte counters, the entry
count, the end-of-file flag, and the two-byte stamp. Nothing structural. The first attempt at
this had used the link offsets from the design the writer was verified in, which is why it
crashed - those offsets are per design, and `--find-links` is how to get them.

Then the two halves together: starting from `BC_pick5.DSN`, `dsn_add_instance.py` added a sixth
instance (`U4:B`) and `dsn_add_wire.py` wrote a wire, giving 6 instances, 9 wires, 22121 bytes -
and ISIS opened it (`BZ_endtoend.DSN`). So a circuit can be assembled from the file: instances of
any device the design already embeds, plus wires between coordinates you know.

What remains outside that loop is geometric rather than structural: the coordinates a wire has to
end on. For a part the design already had, they come from the wires that are already there; for a
part the script just placed, they have to be measured once per device - a magnified crop reads
the pin stubs well enough - or taken from the device's symbol.

### Wiring a scripted part

That last step was tried with the pin position a magnified crop had given for one of the
scripted instances, `(0.942, -2.270)` for U4:A's input, run through the wire writer back to a pin
the sample design already had. ISIS opened the design, and after saving from inside ISIS the
file holds **one more wire record than before** (raw `WIRE` markers 8 → 9) with the file
normalised to 21606 bytes - so the wire the script wrote is a wire ISIS keeps.

One caution for anyone re-parsing that file: after an ISIS save the records no longer answer the
same "point count at +9" test that works on the file before it is opened (valid count 6 → 0
while raw markers went 8 → 9). Compare against the pre-save file, or re-derive the record
walking, rather than concluding the wires vanished.

So the whole path is open now: instances of every device the design embeds, wires between
coordinates, and a design ISIS loads and re-saves with all of it intact. What is left is
per-device bookkeeping - a table of pin offsets for the devices a circuit needs, measured once
each the way U4:A's was - and the device definitions themselves, which a design has to carry
before any of this applies.

### The pin offsets are in the device definition

That table does not have to be measured by eye. A device's definition block in the header carries
its pins with coordinates. In the 74LS00 block, the small records around the `$PINDEFAULT` and
`$PININVERT` names hold pairs like `(-0.300, 0.100)` and `(-0.300, -0.200)` - the two inputs of
one unit - which match the positions a magnified crop read off a placed instance (0.942 and
(-2.466) in design inches against an anchor at (1.192, -2.292), that is offsets near (-0.25,
0.0) and (-0.25, -0.2)) to within the crop's own accuracy.

The same block also carries the symbol's drawing as a coordinate list and a run of small integers
that look like line commands, so the block is self-describing: bounds at `(-0.3, -0.2)` to
`(0.3, 0.2)`, the outline as pairs, then the pins. Writing a parser for it is the next step, and
it is bounded: the files to work against are `BC_pick5.DSN` (which embeds both NAND2 and
74LS00) and the coordinates a crop already gave for one instance to check the result against.

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

## Power terminals: VCC is the POWER terminal, and it arrives unnamed

There is no `VCC` part in the library. VCC and GND are *terminals*: the terminals mode (终端模式)
lists `DEFAULT, INPUT, OUTPUT, BIDIR, POWER, GROUND, BUS`, and POWER is the positive rail -
Labcenter's own `SAMPLES\Graph Based Simulation\Diode.DSN` stores a placed one as `$TERPOWER`
followed by the name `"VCC"`, and `LIBRARY\PWRRAILS.INI` binds `VCC/VDD` to 5.0 V. So the answer
to "where do I find VCC" is: terminals mode, POWER.

A freshly placed POWER or GROUND terminal has an **empty name**, which is not a cosmetic
problem - an unnamed terminal joins no power net, so pull-ups have nothing to pull up to. The
name lives in the record as a length-prefixed string:

```
[0x09]["$TERPOWER"][0x0D][0x00][0xFF][len][name][anchor x][anchor y]
[0x0A]["$TERGROUND"][0x0D][0x00][0xFF][len][name][anchor x][anchor y]
```

`scripts/dsn_objects.py` reads it back, which is how you check the naming worked:

```
python scripts/dsn_objects.py design.DSN        # parts, terminals with names, wires
```

## Naming a terminal, and the dialog that finally opened

Double click does nothing on a terminal. The route that works is: select it, then `Ctrl+E` -
the same "编辑属性 / Edit Properties" that the right-click menu's first item carries. That opens
`Edit Terminal Label` (#32770), whose label field is an edit **inside a ComboBox** at the top and
whose buttons are 确定/取消 at the bottom right.

`scripts/dialog_fill.py` writes the text and presses the button without touching the keyboard,
which is what makes it immune to the IME:

```
python scripts/dialog_fill.py --pid <isis-pid> --dialog "Edit Terminal Label" --list
python scripts/dialog_fill.py --pid <isis-pid> --dialog "Edit Terminal Label" --text VCC --click-button 确定
```

Sending the text with `WM_SETTEXT` **and** pressing the button with `BM_CLICK` is the pair that
commits; sending `WM_COMMAND IDOK` to the dialog looked like it worked once and left the name
empty on a later run, which is exactly the kind of silent failure that costs an hour. Verified
both ways against the saved file: `$TERPOWER (-1.600,2.600) name='VCC'`.

The right-click menu itself can be photographed - `scripts/capture_hwnd.py --pid P --class #32768`
prints the menu window's own pixels, since a menu is a window of its own and never appears in a
`PrintWindow` of the application:

```
python scripts/capture_hwnd.py --pid P --class #32768 --out menu.png
```

## A second ISIS window steals every click

To experiment without touching the user's sheet, open a copy in a second ISIS instance
(`Start-Process ISIS.EXE '"copy.DSN"'`). Input goes to the window under the pointer, and Windows
refuses `SetForegroundWindow` from a process the user is not interacting with - silently, so
every click lands in the other design and the run looks like "the script did nothing".

`scripts/forcefocus.ps1` does the old attach-to-the-foreground-thread dance and reports
`setforeground=True`; with it, the placement recipe lands dead on:

| step | what | why |
| --- | --- | --- |
| 1 | `forcefocus.ps1 -TargetPid P` | otherwise the clicks go to the other instance |
| 2 | mode button, then the object selector row | the part is only armed from the list |
| 3 | three clicks on the target point | two arm and place; a run that stops at two leaves the part hanging on the pointer |
| 4 | `Ctrl+S`, then parse the file | the file is the only proof the part exists |

Measured accuracy: asked for design (5.200, 1.000), the saved record read (5.192, 1.008).
Terminals place with their own offset - the anchor lands 0.10 in left and 0.20 in above the
point clicked, against 0.308/0.208 for a part.

The mode buttons have to be measured for the window you are driving, and they move with the
window: `scripts/probe_toolbar.ps1` hovers each one and captures the window, and ISIS writes the
tool's name into the status bar. Measured on a 1416x832 window with its top left at (0,20),
hovering x=25: **110 selection, 150 device, 170 junction, 190 wire label, 210 text, 230 bus,
250 subcircuit, 270 terminals, 290 device pins**.

## What a file edit can and cannot do

Two experiments, same day, same build:

* **Renaming a terminal by rewriting the file works.** Inserting the three bytes of `"VCC"`
  into an empty name means shifting every 32-bit field whose value points past the edit - the
  object-area end at `head-4`, the pointers into the model blocks at the end of the file, the
  wire link fields. 21 such fields in a typical design. `scripts/dsn_set_terminal_name.py` does
  it, and ISIS opened the result by name (`vcc - ISIS Professional`). A file with two bytes
  flipped at random still loads, so there is no whole-file checksum to defeat.
* **Appending an object still does not work.** `dsn_add_instance.py` on an ISIS-saved design is
  refused silently, and on an older script-written design it produces the crash shape. The same
  recipe was reported working earlier, so treat any claim that appending works as unverified
  until the file it produced has been opened by name.

## A click that lands in the other window looks exactly like a click that did nothing

With two copies of ISIS open - the user's sheet and a copy to experiment on - every click goes to
whichever window is *foreground*, and while the user is working Windows refuses
`SetForegroundWindow` without complaining. Measured today: the same batch of clicks reported
`foreground=True` for its first three and `False` for the last two, and the file afterwards had
one part instead of the expected two.

So the clicks have to be one process that re-asserts the foreground before *each* click and
prints whether it stuck, which is what `scripts/proteus_click.ps1` does:

```
powershell -File scripts/proteus_click.ps1 -TargetPid P -Clicks "25,143 72,232 1372,221" -Repeat 3
click 1/5 at 25,143  foreground=True
click 2/5 at 72,232  foreground=True
click 3/5 at 1372,221 foreground=True
```

A placement that reports `foreground=False` on any click should be treated as not done, and the
file is what settles it either way. Placement accuracy when the focus does hold: asked for
(5.600, 2.600), the saved record read (5.592, 2.608).

## Saving, and running a menu command, without the keyboard

`Ctrl+S` goes to the foreground window, so a script cannot save the window it is driving while
the user is typing somewhere else - the keystroke either lands in the other document or nowhere.
Menu commands and toolbar buttons can be sent to the window itself instead, and they arrive
regardless of focus:

```
python scripts/menu_command.py --pid P --list                    # 文件(F) 查看(V) 编辑(E) ...
python scripts/menu_command.py --pid P --menu 0 --list           # ids: 308 保存设计, 309 另存为
python scripts/menu_command.py --pid P --menu 0 --item 保存设计   # sends WM_COMMAND 308
```

`scripts/toolbar_press.py` presses a toolbar button by the same command id (the file toolbar's
buttons carry the menu's ids), which is the second focus-free route to the same commands.

**Do not send the pointer-bearing toolbar messages across processes.** `TB_GETBUTTON` and
`TB_GETITEMRECT` want a pointer in the target process' address space; passing one from a helper
process killed a live ISIS instance mid-run today, which then looked like "the save made my
window vanish". `TB_BUTTONCOUNT`, `TB_COMMANDTOINDEX` and `TB_PRESSBUTTON` take integers and are
safe.

## Where a device's pins are

The symbol definition the design carries has the pins with coordinates, and they are the offsets
a placed instance needs - pin point = instance anchor + these numbers:

```
python scripts/dsn_device_pins.py design.DSN --device 74LS00
   $PINDEFAULT  A   pin 1   ( -0.300,  +0.100)
   $PINDEFAULT  B   pin 2   ( -0.300,  -0.100)
   $PININVERT   Y   pin 3   ( +0.300,  +0.000)
```

Two details that cost time: the four bytes in front of a pin record are `[?][0A 00 00]` where the
first byte may or may not be present, so take the coordinates from the *match groups'* own
offsets rather than from a fixed offset; and between a device's `[NAME]+` marker and its
`*PINOUT` keyword sit about seven bytes of binary, so that search needs a wildcard. For devices
whose definition carries `$PINSHORT` records the coordinates come out the same way, but the pin
*names* are not always there - a ground truth from a hand-wired design is the way to check.

## Wiring: both ends have to be connection points, and each instance has its own scroll

Two things made a long stretch of "the script cannot draw a wire" look like a scripting problem
when it was not:

* **A wire is only written when both clicks land on connection points** - a pin, an existing
  wire, or a junction. Clicking a pin and then an empty spot leaves the second end pending and
  writes *nothing*, so a run of such probe wires comes back with an unchanged file, which reads
  exactly like "the clicks are not arriving". Every wire recipe has to end on a pin.
* **A fresh instance of the same design does not necessarily reopen at the same scroll.**
  Placement clicks then land on a different part of the sheet and quietly do nothing. Calibrate
  each instance: place one part at a point whose design coordinate you have assumed, save, and
  read the anchor back out of the file. Twice today that check came back as asked for - clicked
  for design (5.600, 2.600), record held (5.592, 2.608) - and once it came back with no part at
  all, which is the view drifting.

`scripts/proteus_click.ps1` walks the pointer to each point in steps before pressing, because a
press with no preceding motion is not the same event to the application, and takes
`-AbortOnLostFocus` so the sequence stops instead of clicking into whatever window took the
foreground: half a wire or half a placement is worse than none, since the leftover has to be
found and deleted by hand.

For "is this point a pin at all", the check that does not depend on guessing: park the pointer
there, take a screen grab (`grab_foreground.ps1` - a PrintWindow capture never contains the
cursor), crop around the pointer, and ask a vision model whether the cursor is a pencil or a
crosshair. A crosshair means the application did not snap, so the point is not a connection
point. `scripts/hover_scan.ps1` is the same idea in bulk: hover a list of points and keep one
capture per point, then look for the small marker the application draws on a connection point.
