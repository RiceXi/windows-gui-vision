# Building a circuit in a .DSN from a script

This is the workflow the pieces in this folder add up to, verified on ISIS 7.08 SP2. It is for
the case the other `.DSN` documents keep mentioning: a circuit you can describe - a part list and
a netlist - turned into a file ISIS opens, without clicking through the schematic editor.

## What has to be true before you start

The design has to **already embed the device definitions** you need. A part record only says who
is where; the symbol, the pins and the model live in the design. Practical way to get them there:
open the design, press `p` (Pick Devices - see [proteus.md](proteus.md) for the input-language
trap), add each device once, place it, and save. After that the design carries the definition and
you never need the dialog again.

Start from a design saved by *this* installation too. A Labcenter sample carries definitions
under old device identifiers (`NAND2` where the current library says `NAND_2`), and placing a
part from its device list produces a stand-in with no pins.

## The steps

1. **Instances** - `scripts/dsn_add_instance.py --base design.DSN --device 74LS00 --at x,y`
   adds another instance of a device the design already has. It works out whether that means the
   next unit of the same package (`U3:A` to `U3:B`, to `U3:C`, ...) or a new package, builds the
   directory entry including the unit's pin map from the device's own PINOUT text, and the file
   comes out byte-identical to ISIS's own apart from the two-byte stamp. Repeat per instance.
2. **Pin positions** - for a part the design already had, read them from the wires that are
   already there (`scripts/dsn_pins.py` lists the endpoints around each component). For a part
   the script has just placed, measure once per device: capture the window, crop around the
   symbol at 4-5x, and ask a vision model for the tips of the pin stubs, then convert window
   pixels to design inches with [coords.md](coords.md). Verified: the coordinates this gives are
   within the snap distance - ISIS moved a wire written to one of them onto the pin and kept it.
   Keep the result per device in a json table so it is a one-off cost.
3. **Wires** - `scripts/dsn_add_wire.py --base design.DSN --points x,y ... --link <offset>`
   writes a wire. `--link` matters: it takes two 2-byte offsets that are **per design**, and
   `--find-links` prints the candidates for a given design (in the test design: 14487 and 14686).
   Using another design's offsets produces a file ISIS crashes on.
4. **Check** - `scripts/design_loadcheck.ps1` opens the design and reports whether it loaded
   (`exit 0`), was refused quietly (`1`) or brought up a crash dialog (`2`). Run it after every
   generation; then optionally open, save from inside ISIS, and confirm the objects are still
   there.

## What was verified end to end

Starting from a design holding five 74LS00 instances, the scripts added a sixth instance and a
wire and ISIS opened the result: 6 instances, 9 wires, 22121 bytes. The instance edit is
byte-identical to ISIS's own; the wire edit differs from ISIS's by 8 bytes of counters and flags.
A wire written to a measured pin position came back as a wire ISIS kept after saving.

`scripts/dsn_build_circuit.py` does those steps in order from one json file:

```
python scripts/dsn_build_circuit.py --base design.DSN --spec circuit.json --out built.DSN
```

with `circuit.json` holding `parts` (device and anchor) and `wires` (point lists). Run against the
five-instance design with two more instances and a wire between the first one's output and the
second one's input - positions taken from the pin offsets measured earlier, output at anchor plus
`(0.69, -0.075)`, input at anchor plus `(-0.25, 0.025)` - it produced 22557 bytes, ISIS opened it,
and after saving from inside ISIS the file still held all seven instances (`U3:A` through `U4:C`)
and nine wires. That is the whole path: a description of a circuit in, a design ISIS accepts and
keeps out.

## Wiring by pin name

Raw coordinates are tedious to write and easy to get wrong, so the builder can also work from pin
names, using `scripts/pin_tables.json`:

```json
{"parts": [{"device": "74LS00", "label": "g1", "at": [-2.0, 2.0]},
           {"device": "74LS00", "label": "g2", "at": [-0.5, 2.0]}],
 "nets":  [{"name": "n1", "from": ["g1", "Y"], "to": ["g2", "A"]}]}
```

Each pin is resolved to the instance's anchor plus the offset the table holds for that device, and
the net is routed as an orthogonal path bending on the 0.1 inch grid. Run against the
five-instance design that produced 22557 bytes, with `g1.Y` at (-1.310, 1.925) and `g2.A` at
(-0.750, 2.025), and ISIS opened it.

The table has one entry so far, 74LS00, measured the way step 2 describes. Adding a device means
measuring it once and adding six numbers; after that, circuits can be written in terms of gates
and pins rather than coordinates. The routing is a single midpoint bend, which is fine for the
stub in the example and not a replacement for a real router.

## A second wire in one file: what turned out to be wrong

A build with four instances and four nets came back as a crash rather than a design, and the
isolation was clean: instances are fine, one wire is fine, two wires crash. The cause was not the
insertion point, which is what the earlier attempts kept changing. It was that **the insert also
moves every pointer in the file that pointed past it**, and the writer was leaving those stale. A
stale pointer is what the loader dereferences when it crashes, and it is invisible in a walk of
the objects because the object list itself still looks right.

With the relocation in place - a four byte field whose value is the offset of a shared 15 byte
tail block gets the inserted length added - the writer now reproduces Isis's own output byte for
byte on the two ground truths that exist for this design (one wire added: 21670 bytes; a second
one added: 21720 bytes, see [dsn-wires.md](dsn-wires.md)). The second wire also needs a different
shape: Isis hands it the *pending body* of the record in front of the first wire rather than the
last wire's body, which is what `dsn_add_wire.py --mode head` does.

What is still not solved is doing that reliably a third and fourth time, and the way it showed up
is worth recording because the cheap test hid it. A four-instance, four-wire build - the latch
below - passes `design_loadcheck.ps1`: Isis accepts the file and the title names it. Opening it and
saving from inside the application then writes back a design holding **two of the five packages**:
the object area had been read part way and the rest dropped. A partial load looks like a load.

`scripts/dsn_savecheck.ps1` is the test that catches this: open, save from inside the app, close,
compare the reference designators and the wire count. Load-tested constructions:

| construction | wires | load check | save check |
| --- | --- | --- | --- |
| `end` | 7 | yes | full load |
| `end`, `head` | 8 | yes | - |
| `end`, `head`, `end` | 9 | yes | - |
| `end`, `head`, `end0`, `end0` (the latch) | 10 | yes | partial, two packages survive |
| `end`, `end` | 8 | crash | - |

So `dsn_build_circuit.py` stays reliable for instances and for a first wire, and the two-wire
recipe is `end` then `head`. Beyond that the loader is still sensitive to state this model does
not capture, and the honest position is that the file route is verified per design, not in
general - run the save check on anything it produces.

Two of the tools that came out of this are worth using on any new design class: `dsn_walk.py`
prints the wire section (bodies, tail blocks, pointer fields) so the assumptions can be checked
before writing, and `dsn_diff.py` prints the diff between two saves, which is how the two
transformations above were pinned down.

## What is not solved

Reading a device's pin geometry out of its definition block. The block carries the symbol outline
and line commands, and the `$PINDEFAULT` records carry *generic* pin geometry - both devices in
the test design show the same two coordinates there - while the per-pin positions come from the
symbol drawing itself. Parsing that is the obvious next saving, and would replace step 2's
one-off measurements with a lookup.

Placing a part by script into a design that does **not** embed its definition. The definition has
to come from somewhere: Pick Devices in the editor, or a template design that already has it.
