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

## What is not solved

Reading a device's pin geometry out of its definition block. The block carries the symbol outline
and line commands, and the `$PINDEFAULT` records carry *generic* pin geometry - both devices in
the test design show the same two coordinates there - while the per-pin positions come from the
symbol drawing itself. Parsing that is the obvious next saving, and would replace step 2's
one-off measurements with a lookup.

Placing a part by script into a design that does **not** embed its definition. The definition has
to come from somewhere: Pick Devices in the editor, or a template design that already has it.
