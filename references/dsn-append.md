# Adding a component to a .DSN, the version that works

Measured on ISIS 7.08 SP2, build 10468, September 2026. `scripts/dsn_append.py` implements it.

This supersedes the "adding a component" section of [dsn-generate.md](dsn-generate.md). That
section describes what the edit does to the bytes and it is accurate, but the edit it
describes produces files ISIS refuses to load. Four of the five bookkeeping steps were right;
the important one - the insertion point itself - was not.

## The recipe

1. Insert the record at the end of the object area, just before the second `ISIS CIRCUIT FILE`
   marker.
2. The byte before the insertion point becomes `00`.
3. The u32 at head-4 is the new object-area end plus 48.
4. The u32 in the directory that equals the old object-area end - it sits just before `ROOT1` -
   becomes the new one. It is the first occurrence of that value *after* the object area, not
   the one inside a record.
5. Increment the u8 entry count at `ROOT1`+12 and append a directory entry.

Write the record first, then apply steps 3 to 5 at offsets shifted by its length. Doing the
directory edits at their pre-insertion offsets writes over the record you just added, which is
the mistake that produced a file that looked correct and crashed on load.

## How it was pinned down

`new1.DSN` is a design ISIS itself saved after placing one part, and `gen_u3b.DSN` is the same
edit written by the old script: both 18734 bytes, from the same 18372-byte base. Diffing them
gave nine differing bytes, of which:

* two are a volatile stamp (offset 177),
* one is the byte before the insertion point, which ISIS sets to `00`,
* one 4-byte field inside the record and one byte after it, which are the part's snap size,
* two are the object-area end field in the directory,
* one is the directory entry count,
* one is a flag byte at the end of the file.

Applying the bookkeeping and leaving the rest alone is enough. The file then differs from
ISIS's own output in six bytes: the stamp, the two characters of the reference name, the
directory entry's sequence number, and the trailing flag byte. It loads, the part is there,
and ISIS keeps it when it saves. That test is the whole reason this page exists.

## The two constraints

**The base design has to contain that part already.** The record says where a part sits and
what it is worth; the symbol and the model live in the design. Appending a NAND record to a
design that has never held one came back with an empty workspace and no error - the silent
failure shape. Put one instance of every part type you need into the base design first, then
the file route can add as many more of each as you like.

**The record must not carry out-of-line references.** A part placed on a sheet with wires
attached, or with a script in its properties, writes a record containing absolute file offsets
to those other objects. Move that record to another design and ISIS crashes on load with
`access violation in module VGDVCDLL`. Both NAND records in the test base behaved that way: the
381-byte one has a script property and three offsets into the wire area, and cloning it into
its own design failed too.

A record that survives a move is one ISIS wrote for a part with nothing attached - place the
part in a design, do not wire it, do not script it, save. In such a design the last record runs
straight to the object area's `FF` sentinel, so it can be lifted whole: take the bytes from
`FF 02 <ref>` to the byte before the marker and keep the sentinel.

## Telling whether a design loaded

| title | meaning |
| --- | --- |
| `base2 - ISIS Professional` | loaded |
| `ISIS Professional` | rejected, silently |
| `ISIS Professional (未响应)` | crashed; there is also a dialog window |

`scripts/design_loadcheck.ps1 -Path <design>` does this for you: it opens the design, waits,
prints the windows it finds, closes the instance again, and exits 0 for loaded, 1 for rejected,
2 for rejected with a dialog. Use it on every generated file - the silent failure is otherwise
indistinguishable from an empty new design.

## What is still missing: wires

A wire record is

```
02 7F "WIRE" 00 | 00 00 | u16 point count | points | 15 bytes of trailer
```

with the point count at offset 9, points as (int32 x, int32 y) pairs in 10 nm units, and every
object in the file preceded by the eight bytes `FF FF FF 00 FF FF FF 00`. A real wire from the
test design is 42 bytes for two points.

Appending one does not work yet. A clone of the design's own wire with its points moved - with
the trailer, without it, and with the eight-byte prefix - crashed ISIS all three ways. The
trailer almost certainly holds a net id that has to match something in the design, and until
that is decoded, a generated circuit has unconnected parts.

## What this means for building a circuit

Split the work. Place one instance of every part type you need in ISIS, do not wire anything,
save that as the base design, and keep it. Everything after that is scriptable: more instances
of any part already in the base, at coordinates on the 0.1 inch grid, into as many variants as
you want.

The wiring is the part that still needs the GUI, which is also where the GUI is least
painful - clicking from pin to pin is what it is good at, and a misplaced wire is obvious on
screen in a way a corrupted file is not.
