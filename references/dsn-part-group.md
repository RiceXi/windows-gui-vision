# A part's wires live in its own record group

Reading the same records out of the base, the one-wire file and the multi-wire file shows what
attaching wires does to a part.

| record | base | after one wire | after more |
| --- | --- | --- | --- |
| U3:A (nothing attached) | 420 bytes | 420 | 420, plus two u32 offsets appear |
| U3:C | 420 | **534** | 534 |
| U3:D | 420 | 420 | 420, plus one u32 offset |
| U4:A | 420 | **667** | **972** |

Two things are going on.

**The wire records are written inside the part's span.** U3:C grows by exactly 114 bytes when the
ten point wire from U3:B pin 6 lands on its pin 9 - 34 + 8x10, the wire itself. U4:A grows by 247
and then 552 more as wires are attached to it. So a part's record is not a fixed 420 byte block;
it is the head of a group that carries the records of the wires hanging off it.

**The part's record gains offsets to those wires.** In U3:A, two u32s appear where the base had
zeros, and both are tail-block offsets of wires in the file (0x11c18 = 72728, 0x11bde = 72670).
U3:D gains one, 0x11c5a = 72794. Those are the connection entries - the "three offsets into the
wire area" the append notes kept finding - and they sit inside the record, next to the count
fields that went from zero.

## What the writer has to do

For each wire it writes: append the wire record to the group of the part it attaches to, and add
the wire's tail-block offset to that part's connection list. A wire between two parts touches both
groups; a tap splits the tapped wire and adds the new piece to the group of the part it comes
from. Every one of those steps now has a hand-made example to check against.

## What the 83 bytes are (measured, and a correction)

The first cut of `--after-part` took the record to end just before the next instance record. That
lands at 19456 in the base, while the position that reproduces the hand-drawn file is 19373, 83
bytes earlier - and those bytes are not padding:

```
19280  {PACKAGE=DIL14}\n 90 08 59 ff ... 04 00 30 00 ... ff 01 "Default Font" ...
19344  PROPERTIES\0\0\0\0\0 35 00 00 00 | {MODFILE=74NAND2.MDF}\n{PACKAGE=DIL14}\n...
```

so 19355 is a length field (0x35 = 53) introducing the properties text, and 19373 falls *inside*
that text, at the "M" of `74NAND2.MDF`.

That is odd enough to be worth doubting myself about, and it should be: it means the wire's
15-byte body block is taken from the middle of a property string. But the reproduction that used
exactly that position matched the hand-drawn file byte for byte apart from the stamp and the five
bookkeeping fields, so the position is right even though the reading of *why* is not.

Which means the anchor is still unexplained: it is not "the end of the record", and it is not a
field boundary obvious at a glance. The next measurement is to read the same region in the
hand-drawn file and see what the wire's body block actually contains there, which will say whether
the record is really being spliced mid-string or whether the earlier position estimate was off by
the same 83 bytes for a reason.
