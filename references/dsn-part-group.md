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
