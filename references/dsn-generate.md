# Adding objects to a .DSN from a script

Status after re-testing in September 2026 on ISIS 7.08 SP2, build 10468: **adding a record does
not work.** Files built by inserting part records failed to load, whichever design the record
came from and whichever part it was. Editing a record without changing its size still works.

The tests are at the bottom of this file and are worth reading before the recipe, because the
recipe is the thing that keeps looking correct and does not produce a design you can open.
What is still reliable here is the byte layout, the list of fields that track the object area,
and the round-trip discipline for checking an edit.

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

That load test does not reproduce on this build, and I cannot tell you which of the two
observations is wrong - see the re-test at the bottom. Treat the byte-level result above as
solid and the load result as unconfirmed.

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

## What failed when I re-tested it

Four files, one install, each opened with
`Start-Process ISIS.EXE -ArgumentList '"<path>"'` and left alone for 25 to 45 seconds:

| file | edit | result |
| --- | --- | --- |
| `base2_nudge.DSN` | moved one part's x by 0.5 in, no change in size | loads, title gains the file name |
| `build_nand.DSN` | two NAND records inserted, lifted from a different design | crash dialog |
| `build_nand_same.DSN` | the same two records, lifted from the base design itself | crash dialog |
| `gen_u3b.DSN` | one record inserted by the earlier version of this recipe | never loads, no dialog |

The template's origin is not the variable, and neither is the part. An empty design plus a
single resistor and no wires failed the same way. The one thing every failing file has in
common is that it is a different size from the design it came from.

Two failure shapes, both worth recognising:

The crash dialog is a small top-level window with the same title as the main window, roughly
message-box sized, sitting somewhere in the middle of the screen. If you only read the big
window's title bar you will not see it. Its text is
`access violation in module VGDVCDLL ... ISIS Professional 处于不稳定的状态`.

The silent shape looks like the application simply did nothing: ISIS opens an empty workspace
and never shows a dialog. This is what I described as a hang in the earlier version of this
file. It was a load that never completed, and waiting longer does not help.

### Telling whether a design loaded

Pass the path on the command line, wait about 20 seconds, read the window title:

| title | meaning |
| --- | --- |
| `base2 - ISIS Professional` | loaded |
| `ISIS Professional` | did not load |
| `ISIS Professional (未响应)` | crashed; the dialog is a second window, and a ghost one owned by pid 8 shows up as well |

This costs nothing and it catches the silent case, which is the one that otherwise ruins an
afternoon. A title with no file name next to it is never good news.

`scripts/design_loadcheck.ps1 -Path <design>` does exactly this and reports the three cases:
exit 0 loaded, 1 rejected silently, 2 rejected with a dialog. It closes the instance again
unless you pass `-KeepOpen`, and it is safe to point at a copy you do not mind losing.

### The path is not the problem

An obvious suspect is the Chinese characters in the folder name, since ISIS 7 predates
unicode paths. It does not hold up: `base2.DSN` loaded from `C:\Users\yangf\dsn_smoke\` and from
`C:\Users\yangf\dsn_smoke\中文测试\` with the same result, and the generated files crashed from
both. Test the path separately before blaming it.

## What that leaves

Reading a design holds up, and so does editing one without changing its size: the coordinate
patch loads and the part sits where the patch puts it, and the same-length rename from earlier
round-tripped through a save from inside ISIS. Adding a wire is in the failing group with
adding a part, which fits - both grow the object area.

Something validates the size of the object area and I have not found it. The candidate is the
tail of the file: the second `OBJECT DATA` section and the name list after it, whose entries
carry two-byte ids rather than record offsets. Until that is decoded, the file route is for
reading and for same-size edits.

For building a schematic, drive the GUI. It is slower for one design and it is the only thing
that produced designs ISIS would open - see [proteus.md](proteus.md) for the placement
sequence, which takes three clicks per part and is worth getting right before trying to script
it.
