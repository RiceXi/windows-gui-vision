# What attaching a wire to a part writes (found, at last)

**Corrected since**: the entries are not a list with a count - they are one slot per pin, at
`record + 407`, `+411`, `+415` for pins 1, 2, 3, each holding the tail block offset of the wire on
that pin. The `count` this page says went from 0 to 3 is the fixed four-byte header
`12 00 03 00`, which the base already had; only the slot contents change. See
[dsn-wire-slots.md](dsn-wire-slots.md).

Two wires drawn by hand - U3:C pin 8 to pin 10, then U3:B pin 6 to U3:C pin 9 - and saved. The
second one is the interesting one: a wire between two *parts*. Diffing it against a byte-exact
reproduction of the first wire shows what had been missing from every scripted wire.

## The part's record gains a connection list

Before the wire, U3:C's record ended with zeros in the two places below. After it:

```
... 00 1d 00 00 00 00 c0 9e 00 00 00 40 00 00 01 |   the default tail
    ff ff ff 00 ff ff ff 00 | 02 7f "WIRE" 00 00 00 | 0a 00 <10 points>   the new wire's record
    ...
    [u32 tail = 0x4bff]  [u32 body = 0x4c71]                                  inside U3:C's record
```

and the count that precedes those offsets went from 0 to 3. That is the connectivity: when a
wire is attached to a part, the **part's own record** gets the offsets of that wire - the same
"three offsets into the wire area" the append notes kept running into, and the reason a wire
written only into the wire section never sticks: the part never learns about it.

## The wire record itself is the shape the writer already produces

`ff ff ff 00 ff ff ff 00` + `02 7f "WIRE" 00 00 00` + u16 point count + points, preceded by the
15-byte block the new wire takes over. That is exactly what `dsn_add_wire.py` writes - so the
splicing was right and the missing half was the connection list above.

## Where the second wire went

It did **not** go at the end of the wire section. It went at the position the *first* wire had
occupied, pushing that one 114 bytes further on: the wires attached to a part grow backwards from
the part's record, newest first. Two wires on the same part therefore do not append in the order
they were drawn.

## A pin takes exactly one wire (hand-confirmed)

The attempt to draw U3:C pin 9 to pin 8 was refused by the application: no green pencil, no
interaction at all. That is the help's rule - *a connection point can connect to precisely one
wire* - reproduced by hand. Consequences for anything generated:

* each pin can carry at most one wire, so a net that needs to reach three pins needs a wire with
  a tap in the middle (wires are connection points along their whole length), not three wires
  meeting at a pin;
* "already wired" is why a second wire from the same pin silently refuses to start, which is also
  what the automated probes were reading as "no pins".
