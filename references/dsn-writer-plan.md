# Wiring up the writer: what is left, in order

The rules are all measured now (see `dsn-part-group.md`, `dsn-connection-list.md`,
`dsn-tap-junction.md`, `dsn-hand-wire.md`). This is what the writer still has to do, smallest
first, with the hand-made file to check each step against.

## 1. Put a pin-to-pin wire in the right place - done

A wire whose two ends are pins of the *same* part hangs in that part's group: insert its record
at the last byte of the part's 420 byte record - one byte before the next object's marker, not at
the marker. U3:C's group grows by exactly 34 + 8n, and every pointer naming a tail block at or
after the splice moves with it.

Check (passed): `_re/scratch/verify_wire.py` reproduces the hand-drawn ten point wire byte for
byte, at the right offset, with the rest of the file shifted by exactly 114 bytes.

## 2. Add the connection entry - done, and the rule is simpler than it looked

When the wire's other end is on a *different* part, both parts' records gain the wire's
tail-block offset. The slots are **per pin**: pin 1 owns `record + 407`, pin 2 `+411`, pin 3
`+415` (the four byte header at `+396` and the first slot at `+403` stay as they are). Read the
hand-drawn file with that mapping and every entry lands on the pin of the wire it names - U3:C
pin 10 / pin 9 / pin 8 in slots 1 / 2 / 3, U3:D pin 12 in slot 2, U4:A pin 3 in slot 3.

There is no count field to update: the `12 00 03 00` header the old notes called one is a fixed
part of the record and does not change. `dsn_add_wire.py --after-part U3:C --pin 2 --link-part
U3:B --link-pin 3` writes both halves. See [dsn-wire-slots.md](dsn-wire-slots.md).

## 3. Split on a tap - not needed for generated nets

A node on a wire splits it: the old record is replaced by two, each keeping one outer end and
ending at the tap point, and the third wire joins there. All three are 66 bytes in the example
(four points each). The parts involved get their connection entries as above.

Isis writes those three into the wire section at the end of the object area, not into the part's
group. A generator can skip the whole problem: an endpoint shared by two segments is a connection,
so a net with three or more pins is written as segments that meet at a point - `hand_wire_2.DSN`
has exactly that shape at `(2.80, 0.00)`, three wires, one pin slot each, no split.

## 4. The one step that still needs the application

A script-written part may name a device whose unit drawings the design does not embed, and then
it is a stand-in. Opening the result in Isis and saving once fetches those definitions and writes
them in (see `dsn-embedded-definitions.md`: the first section grew from 13 KB to 65 KB and gained
55 COMPONENT, 19 PORT, 16 TERMINAL and so on). So the pipeline is: write parts and wires, then one
open-and-save round trip. That round trip needs a person at the launch unless the modal notice
can be dismissed by automation, which is the one automation gap left.

## Still open

Five u16 counters (16137, 16191, 16387, 16575, 16839 in this base) are recomputed by Isis on every
save and the writer leaves them stale. Everything else in the file now matches Isis's own output
for the first hand edit. Whether those five matter for a design with several new wires is the
question the save round trip answers: `wiretest.DSN` (five wires, one shared endpoint) is the test
file, and `scripts/dsn_savecheck.ps1` is the check - open, save from inside the application, and
confirm that every instance and wire is still there.
