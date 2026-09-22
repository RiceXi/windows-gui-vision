# Writing a wire that stays connected: the splice point and the pin slots

This is the current, measured model of what Isis writes when you draw a wire between two pins, and
it is what `scripts/dsn_add_wire.py --after-part ... --pin ...` now does. Two hand-drawn files
settled it (`hand_wire.DSN` - three hand edits on the five instance base - and `hand_wire_2.DSN`,
the same design after four more), and the writer's output was compared against them byte by byte.

## Where the wire record goes

**But see [dsn-wire-load-test.md](dsn-wire-load-test.md) first, because that position does not
load.** A wire spliced in beside a part's own record - the shape Isis writes when you draw onto a
pin - makes the loader fail with an access violation, because the objects are indexed by the
second section and Isis rewrites that index on every save. The shape a script has to write is the
wire section at the end of the object area: `--mode end`, then `head`, then `end0`, then `end`
for each wire after that, with the pin slots filled as below.

An instance's record is 420 bytes as the instance list counts them, but the wire is spliced in at
the **last byte of that span**, one byte before the next object's `ff 04 <ref>` marker:

```
U3:C record 19036..19454 | byte 19455 | U3:D record starts 19456
                              ^ the wire is spliced here
```

and what is written there is the default tail block followed by the wire record and then the
fifteen bytes that used to sit at that position:

```
00 1d 00 00 00 00 c0 9e 00 00 00 40 00 00 01      the tail block
ff ff ff 00 ff ff ff 00 | 02 7f "WIRE" 00 00 00 | 0a 00 | ten points
00 ff 04 "U3:D" ...                                the bytes that were there
```

So the record grows by `34 + 8n` bytes, and every pointer in the file that named a tail block at or
after the splice moves with it. Inserting one byte later - at the marker instead of before it -
produces a file the loader reads one object short, which is the "loads but loses objects" shape
seen earlier.

Writing the wire at the end of the object area (the wire section, as `--mode end|head` does) is a
different, also valid shape: that is where Isis puts wires it splits at a tap.

## The connection is a per-pin slot

A part's record ends with four four-byte slots at `record + 403 + 4i`. They are indexed by **pin**,
in the same order the part's pin map lists them, one-based: pin 1 owns `+407`, pin 2 owns `+411`,
pin 3 owns `+415`. Slot 0 at `+403` stays zero. Each slot holds the offset of the tail block of
the wire attached to that pin, and it is written on both parts of a wire that crosses parts.

| record | slot 1 | slot 2 | slot 3 |
| --- | --- | --- | --- |
| U3:C, after three hand edits | 20434 (pin 10, A) | 19455 (pin 9, B) | 20500 (pin 8, Y) |
| U3:A, after `hand_wire_2` | - | - | 72670 (pin 3, Y) |
| U3:A, same file | 72728 (pin 1, A) | - | - |
| U3:D, same file | - | 72794 (pin 12, the unit's second pin) | - |
| U4:A, same file | - | - | 72612 (pin 3, Y) |

Read that against the pin maps (`A, B, Y` for a 74LS00 unit, physical numbers 1/2/3 for unit A,
4/5/6 for B, 10/9/8 for C, 13/12/11 for D) and every entry lands on the pin whose wire it is.
The slots are not a session cache and not a hash: the same wire keeps the same slot across two
saves of the file even though its offset moved by 51931 bytes when the definitions were embedded.

The earlier note that "the count before the offsets went from 0 to 3" was a misread of a four-byte
header (`12 00 03 00`) that the base already carried: only the slots themselves change.

## What the writer still does not write

Five u16 fields - at 16137, 16191, 16387, 16575 and 16839 in the five instance base - grow when
Isis saves a file with new wires (`+92, +27, +27, +27, +27` for the four wires of `hand_wire.DSN`).
They are not the object counts (the loader does not stop early without them), the writer leaves
them alone, and the one open question is whether a save round trip is what makes them matter. They
are the only bytes, besides the two-byte stamp, that differ between the writer's output and Isis's
own for the first hand edit.

## How this was checked

`_re/scratch/verify_wire.py` pulls the ten-point wire out of `hand_wire.DSN`, writes it onto the
base with the writer, and compares:

```
spliced wire + its tail block      IDENTICAL (129 bytes)
everything from U3:D to U4:A       IDENTICAL except the byte at 20409
bytes after it that did not shift  none
U3:C slot 2 at 19447: writer=19455  hand=19455
U3:B slot 3 at 19031: writer=19455  hand=19455
```

and the whole-file difference is only the stamp, the object-area length, the five counters above,
the three slots the later hand edits filled, and the region from 20410 on where those later edits
live. A tap is not needed to build a net: segments that share an endpoint connect, and
`hand_wire_2.DSN` shows three wires meeting at `(2.80, 0.00)` with one pin slot each.
