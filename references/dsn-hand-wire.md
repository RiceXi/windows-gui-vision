# The hand-drawn wire, and what it settles

**Corrected since**: the splice position is not `~19373`. A wire attached to a part goes at the
last byte of that part's 420 byte record - `next object marker - 1`, which is 19455 for U3:C in
the five instance base, and the writer was one byte late until that was measured. The five fields
at 16137, 16191, 16387, 16575 and 16839 are still recomputed by Isis and still not modelled; see
[dsn-wire-slots.md](dsn-wire-slots.md).

One wire drawn by hand in the application - between pin 8 (Y) and pin 10 (A) of U3:C, in the
instances-only base - and saved. That is the ground truth this folder had been missing, and it
answers two open questions at once.

## What Isis wrote

Base 21588 bytes, result 21670: +82, a six point wire, routed
(-4.50,-1.40) (-4.60,-1.40) (-4.60,-1.10) (-3.40,-1.10) (-3.40,-1.50) (-3.50,-1.50).

The diff against the base is small and specific:

| offset | change |
| --- | --- |
| 177 | the stamp Isis rewrites every save |
| 13215 | the object-area length field, +82 |
| 16137, 16191, 16387, 16575, 16839 | five 2-byte bookkeeping fields, recomputed by Isis |
| ~19373 | the new wire record, spliced in |

The wire did **not** go into the wire section where the wire-to-wire inserts went. It went after
the record of the part it connects - U3:C lives off at (-4.5, -1.4) on the sheet, and the wire
lands beside it. That is the rule that was missing: a wire attaches itself next to the object it
connects, so a pin-to-pin wire and a wire-to-wire wire do not insert in the same place.

## Reproduction

`scripts/dsn_add_wire.py`'s splicing, applied at that same position with the same six points,
reproduces the hand-made file **byte for byte except the stamp and those five bookkeeping
fields** - the wire record, its position, its points, the tail block moving, and the object-area
length all match. So the write mechanics are right; what the writer still does not do is recompute
the five derived fields (which is also why its earlier outputs differed from Isis's by "five
single-byte fields" in the wire-section cases - the same category).

## The bigger answer: appended parts are wireable

The wire connects two pins of **U3:C, a part the script appended to the design**, and the
application kept it. So a part written into the file by `dsn_add_instance.py` does have working
connection points at its pins.

Which means the run of "appended parts have no pins" results in
[dsn-wires.md](dsn-wires.md) were wrong - they were taken through a GUI that was disabled by the
modal notice at launch and never registered a click at all, so they measured nothing. The file
route produces parts that can be wired; the earlier conclusion is retracted.
