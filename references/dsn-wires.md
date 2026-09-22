# Wires in a .DSN

Status, September 2026, ISIS 7.08 SP2: adding a wire by script now works and the file it
produces loads. `scripts/dsn_add_wire.py` does it. One part of it - locating the two link
fields - still has to be told where they are; everything else is automatic.

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
* the last wire's 15-byte tail block moves to the new wire, and the old wire gets the default
  tail block `00 1D 00 00 00 00 C0 9E 00 00 00 40 00 00 01`;
* two 2-byte link fields become the file offset of the new wire group (`0x3690` = 13968 here).
  Each sits at the end of a run of 4-byte object offsets, one inside a component record and
  one inside a wire record.

The tail block is the part that is easy to get wrong: it is not a constant, it belongs to
whichever wire is last, and it has to travel. Six earlier attempts at appending a wire - at the
end of the object area, inside the wire section, duplicated, with the prefix, without it, and
with the object id counter bumped - all crashed with `access violation in module VGDVCDLL`.

## The recipe, verified

1. find the last wire object, and its 15-byte tail block;
2. replace that block with the default one and insert at the same offset:
   `FF FF FF 00 FF FF FF 00` + `02 7F "WIRE" 00 00 00` + point count + points + the old block;
3. write the insertion offset into the two link fields;
4. add the length inserted to the object-area end field at head-4.

Done that way, the result is byte-for-byte what ISIS itself writes, except for a volatile stamp
and five single-byte fields that it also touches and that do not affect loading. Both halves
were tested separately: with the link fields written (F) ISIS opens the design; with everything
except them (G) it crashes. `scripts/dsn_add_wire.py` reproduces the working version exactly.

And the round trip holds. A design with a script-added wire, opened in ISIS and saved from
inside it, came back with seven wires instead of six and the new one still routed through the
same six points: `(0.7, 0.8) (0.7, 0.9) (0.8, 0.9) (0.8, -0.4) (0.7, -0.4) (0.7, -0.3)`. ISIS
normalises the file on save - 18515 bytes became 18467 - but it kept the wire, which is the
acceptance test that matters.

## The one thing still manual

The two link fields have to be pointed at with `--link <offset>`. Their meaning is not pinned
down yet - they sit at the end of offset lists inside the objects involved, and the value is the
new wire's offset - so the way to find them for a different design is to repeat the measurement:

1. save the design once with no changes, save a copy with one wire drawn by hand;
2. diff the two files;
3. the fields that became the insertion offset are the ones to pass in.

The hypothesis worth testing next is that they belong to the two objects whose pins the wire
connects, in which case they could be located from the wire's endpoints and the whole thing
becomes automatic.

`--find-links` shortens the search. In this design the two fields are the only 2-byte zeros
preceded by a run of three 4-byte offsets that land inside the object area, and it prints
exactly those two. The four 2D graphic objects have similar-looking lists with two offsets
each, so the threshold is what separates them - treat the output as a shortlist and confirm it
against a hand-drawn wire before trusting it on an unfamiliar design.

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

Both halves of a schematic can now be produced by script: components with
[dsn-append.md](dsn-append.md), wires with `dsn_add_wire.py`. Wiring through the GUI also works
and is no longer guesswork - the pointer-to-design mapping is measured
([coords.md](coords.md)), the notice window that swallowed clicks is closed first, and the
clicks are verified by diffing the saved design against a saved baseline.
