# Adding objects to a .DSN from a script

Status, so you know what you are getting: adding a component works and is verified. Generating
a whole wired circuit does not, yet. The gap is explained at the bottom.

## What adding one component actually changes

Four things, plus a count:

1. A record appended at the end of the object area, which means immediately before the second
   `ISIS CIRCUIT FILE` marker. It starts with `FF 02 <two-character reference>` and carries the
   part's coordinates as two int32s in 10 nm units, followed by its `COMPONENT ID`,
   `COMPONENT VALUE`, `SUBCKT NAME` and `PROPERTIES` sub-blocks. A two-input NAND gate comes to
   347 bytes.
2. A directory entry appended after the second `OBJECT DATA` section:
   `[u16 id][u16 sequence][u16 0][u8 name length][name][6 x 00]`, in object order.
3. The next-id counter - a u16 at the first `ISIS CIRCUIT FILE` marker plus 19 - incremented
   by one. Its previous value is the id used in the new directory entry.
4. Two fields that track the end of the object area: a u16 near offset 12319 whose value is
   the object-area end plus 48, and a u32 in the directory equal to the object-area end. Both
   grow by the length of the record.

And a fifth, easy to forget: the one-byte entry count at `ROOT1` plus 12. The byte immediately
before the insertion point gets set to `00`.

Insert first, then apply the directory edits with every post-insertion offset shifted by the
record length. Writing the directory at its pre-insertion offsets is how you corrupt the
record you just added.

## Measured result

Starting from an 18372-byte design, inserting a 347-byte record gave 18734 bytes, four records
became five, and the next-id counter went from 16 to 17.

Compare the generated file against the one ISIS writes when you add the same part by hand, and
exactly six bytes differ:

```
off   177, 178   timestamp / checksum
off 17242        "9" vs "3"   the reference name U9 vs the template's U3
off 17806        directory entry sequence field
off 17812        "9" vs "3"   the same reference name, second copy
off 18670        flag byte at the end of the file
```

Two of those six are the rename you asked for, two are a volatile stamp, and the last two are
the cosmetic fields described below. Nothing else differs.

Open the generated file in ISIS and it loads without complaint. Save it from inside ISIS and
the added record is still there: five records, the reference name kept, the next-id counter
still 17. Note that ISIS rewrites parts of the surrounding file when it saves, so byte-diffing
*after* a save only means something if both files went through the same save history. Compare
the generated file against a hand-made one *before* either is opened.

## You need one record per part

The record is part-specific, and only ISIS can write one. Two ways to get it:

Let ISIS place the part once, save, and lift the `FF 02 <ref>` record that ends just before the
second `ISIS CIRCUIT FILE` marker. Or take it out of a bundled sample design that already uses
that part - that is much faster, and it is where I would start next time, because Labcenter's
samples already contain most of the parts you would want: all the virtual instruments, most of
the generators, many of the analysis charts.

Then clone it: same length, swap the two-character reference, and change the coordinate
int32s. Do not change the length of anything inside the record. Renaming a part to a longer or
shorter name makes ISIS hang, and the same goes for anything else that changes a record's
size.

## Two fields you can leave alone

The `sequence` u16 in the directory entry, and one flag byte near the end of the file, differ
from ISIS's own output. Nothing appears to validate them, and designs with them left as they
are load and render correctly.

## Anchors used by the recipe

| anchor | meaning |
| --- | --- |
| first `ISIS CIRCUIT FILE` | start of the object-area section header |
| that marker + 19 | u16 next-id counter |
| second `ISIS CIRCUIT FILE` | end of the object area; records go here |
| last `OBJECT DATA` | start of the directory |
| `ROOT1` + 12 in the directory | u8 entry count |

The absolute offsets (12319, and the object-area end) are for a design of around 18 KB. Derive
them per file rather than copying the numbers.

## What is missing for a complete circuit

Three things, in the order they would bite you:

Wires. The format is known - `00 00`, a u16 point count, then the points - but a wire has to
start and end on a pin, which means knowing every part's pin offsets in the same 10 nm grid.
Those were extracted for 36 parts into a table, and they look right, but nobody has built a
connected design from them yet.

Part coverage. You need a template record for every part in the design, and there is no way to
synthesise one, so coverage is limited by which samples contain the parts.

Verification. Placing parts and wires and then checking the netlist is compiled without errors
is the acceptance test that matters, and it has not been done end to end.

For a one-off report, the GUI is faster. For "make me forty variants of this circuit", the
file route is worth finishing, and the round-trip test above - script writes, ISIS opens and
saves, parse the result, diff against ISIS's own output - is the way to know you got it right.
