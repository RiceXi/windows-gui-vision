# Wiring up the writer: what is left, in order

The rules are all measured now (see `dsn-part-group.md`, `dsn-connection-list.md`,
`dsn-tap-junction.md`, `dsn-hand-wire.md`). This is what the writer still has to do, smallest
first, with the hand-made file to check each step against.

## 1. Put a pin-to-pin wire in the right place

A wire whose two ends are pins of the *same* part hangs in that part's group: insert its record
immediately after the part's 420 byte record, pushing any wires already there further on (newest
first). U3:C's group grows by exactly 34 + 8n. No field in the part's record changes for this
case - checked by diffing the base against `hand_wire.DSN`, where the only differences are the
stamp, the object-area length, five bookkeeping fields, and the wire itself.

Check: base -> `hand_wire.DSN` should match except the stamp and the five fields.

## 2. Add the connection entry for a wire that crosses parts

When the wire's other end is on a *different* part, both parts' records gain the wire's
tail-block offset in a slot that held zero, next to a count that increments. U3:A went from 420
bytes with zeros there to two u32s (72728 and 72670, both tail-block offsets of wires in the
file); U3:D gained one (72794); U3:C's record changed too when the wire from U3:B landed on it.

Still to pin down: which slot gets which wire (the order), and the exact position of the count
relative to the slots. Both are readable from the same three files by comparing slot contents
against the tail-block list, which is what `dsn_walk.py` prints.

## 3. Split on a tap

A node on a wire splits it: the old record is replaced by two, each keeping one outer end and
ending at the tap point, and the third wire joins there. All three are 66 bytes in the example
(four points each). The parts involved get their connection entries as above.

## 4. The one step that still needs the application

A script-written part may name a device whose unit drawings the design does not embed, and then
it is a stand-in. Opening the result in Isis and saving once fetches those definitions and writes
them in (see `dsn-embedded-definitions.md`: the first section grew from 13 KB to 65 KB and gained
55 COMPONENT, 19 PORT, 16 TERMINAL and so on). So the pipeline is: write parts and wires, then one
open-and-save round trip. That round trip needs a person at the launch unless the modal notice
can be dismissed by automation, which is the one automation gap left.

## Validation

For each of the three cases, generate from the same base, then byte-compare against
`hand_wire.DSN` and `hand_wire_2.DSN`. The wire records themselves already match; the connection
entries and the split are what the comparisons will judge.
