# Tapping into a wire: Isis splits it, there is no junction object

Third hand-drawn edit: a node placed in the middle of the wire between U3:C pin 10 and pin 8, and
that node connected to U3:B pin 4. File 21784 -> 21949 bytes.

## What it did to the wires

The tapped wire - six points, from (-4.50,-1.40) to (-3.50,-1.50) - is **gone**, replaced by two
wires that both end at the tap point (-4.00,-1.10):

| wire | points |
| --- | --- |
| old | (-4.50,-1.40) (-4.60,-1.40) (-4.60,-1.10) (-3.40,-1.10) (-3.40,-1.50) (-3.50,-1.50) |
| new A | (-4.50,-1.40) (-4.60,-1.40) (-4.60,-1.10) **(-4.00,-1.10)** |
| new B | (-3.50,-1.50) (-3.40,-1.50) (-3.40,-1.10) **(-4.00,-1.10)** |

and a third record follows them at 20589 carrying the tap wire itself, from U3:B pin 4 to the same
point. Each of the three is 66 bytes - a four point wire (34 + 8x4).

So there is **no junction object**: tapping a wire means *splitting* it at the tap point, leaving
two wires that meet there, and adding the new wire to that point. A generator that wants a net
with three or more pins has to do the same split; a pin cannot carry two wires (hand-confirmed
earlier), so this is the only way a real net is expressed in the file.

The three connection lists follow the same pattern as the previous edits: each of the parts
involved records the offsets of the wires attached to it.

## What a generated net therefore looks like

For a net joining pins P1, P2, P3:

1. one wire between two of them, routed;
2. the third pin's wire routed to a point on the first wire, and the first wire split at that
   point into two;
3. connection entries for every part touched, in the parts' own records.

Each step is now backed by a hand-made example in this folder's history, and the wire records
themselves are the same shape `dsn_add_wire.py` already writes.
