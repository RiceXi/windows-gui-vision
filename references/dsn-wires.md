# Wires in a .DSN

Status, September 2026, ISIS 7.08 SP2: the record layout is decoded, adding one by hand is not
working yet, and adding one through the GUI definitely is.

## What a wire record looks like

```
FF FF FF 00 FF FF FF 00 | 02 7F "WIRE" 00 | 00 00 | u16 point count | points | 15 bytes
    8 byte prefix            9 byte header              count at +9        int32 pairs
```

so a wire costs 34 + 8n bytes for n points, and the point count sits at offset 9 from the
`02`, not at the end of the header. Points are (x, y) int32 pairs in 10 nm units, the same grid
as everything else.

Nearly every wire in Labcenter's samples carries the same prefix and the same 15 trailing
bytes, which is why it looked like a fixed frame for a while. It is not: the trailer holds
style and connectivity fields, and the values seen in one design (`00 1D 00 00 00 00 C0 9E 00
00 00 40 00 00 01`) are not universal.

## What ISIS does when you draw one

Draw a wire between two connection points, save, and compare against a save of the same design
with no edits:

* the file grows by 82 bytes, which is a 6-point wire: 34 + 6 x 8. The autorouter bent it into
  six points, so measure the count rather than assuming two;
* the wire goes into the *wire section* of the object area, before the graphics and the panel,
  not at the end of the object area;
* two earlier wire records change: a 2-byte field in each becomes the file offset of the new
  wire (`0x3690` = 13968 in the test). Something in the file is a chain, and appending without
  repairing it is what makes ISIS crash on load.

That last point is the whole reason six attempts at appending a wire failed - at the end of the
object area, in the middle of the wire section, duplicated, with the prefix, without it, and
with the object id counter bumped. All of them crashed with `access violation in module
VGDVCDLL`. The chain is the missing piece.

## The comparison that produced this

Two saves of the same build, one edit apart:

1. copy the design, open it, save it, close it - that is the baseline, and it is not the same
   bytes as the file you started from, because ISIS normalises on save;
2. copy the design again, open it, draw the wire, save, close;
3. diff the two saved files.

Diffing an ISIS save against the pristine original gives thousands of differences that have
nothing to do with the edit. The earlier mistake in this repository was doing exactly that.

`scripts/proteus_input.ps1` does the input - including closing the notice window that
otherwise eats every canvas click - and `references/coords.md` has the pointer-to-design
mapping that makes the clicks land on the right pins.

## What this means today

Wiring through the GUI is no longer guesswork: the mapping is measured, the notice window is
out of the way, and the click path is verified by diffing the saved design. A circuit can
therefore be built end to end now - parts in bulk by the file route, wires by clicking between
pins.

The file route for wires needs the chain decoded first. The pair `A_base.DSN` / `D_wire.DSN`
in the working directory is the evidence to start from: the new wire's bytes are there, and so
are the two fields that changed to point at it.
