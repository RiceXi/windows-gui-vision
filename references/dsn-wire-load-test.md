# Which written wires the loader accepts, measured

`scripts/design_loadcheck.ps1` on the five instance base (`BC_pick5.DSN`, 21588 bytes), September
2026. Every file below is that base plus the wires named, and every wire also carried its pin
slots unless the row says otherwise.

| file | wires and the shape each was written with | result |
| --- | --- | --- |
| `x1_end.DSN` | one wire, wire section, `end` | **loads** |
| `x2_group_new.DSN` | one wire, in U3:A's group, at `marker - 1` | crash |
| `x3_group_old.DSN` | one wire, in U3:A's group, at `marker` | crash |
| `x4_group_slot.DSN` | as x2, plus U3:A's pin slot | crash |
| `x5_group_c.DSN` | one wire, in U3:C's group, no slot | crash |
| `x6_group_c_slot.DSN` | as x5, plus the slots for U3:C pin 2 and U3:B pin 3 | **loads** (twice) |
| `y1.DSN` | one wire, wire section, `end`, slot for U3:A pin 3 | **loads** |
| `y2.DSN` | two wires, `end` then `head`, slots | **loads** |
| `y3.DSN` / `y0.DSN` | three wires, `end head end` (y0 without slots) | crash |
| `z_end0.DSN` | three wires, `end head end0`, slots | **loads** |
| `z_end0_noslot.DSN` | the same three without slots | **loads** |
| `z_head.DSN` | three wires, `end head head` | crash |
| `seq_end-head-end0-end.DSN` | four wires, `end head end0 end` | **loads** |
| `seq_...-head.DSN` | four wires, `end head end0 head` | crash |
| `seq_...-end0.DSN` | four wires, `end head end0 end0` | **loads** |
| `seq_...-end.end.DSN` | six wires, `end head end0 end end end` | **loads** |
| ten wires, `end head end0` then `end` six times | **loads** |

## What that says

**The wire section is where a script should write.** A record spliced in at a tail block inside
the wire chain loads, with or without connection entries, which is why the original recipe
(`--mode end`) worked. A record spliced in beside a part's own record - the position Isis itself
uses for a wire drawn onto a pin - is **not accepted** when the second section's index has not
been rewritten, which is what Isis does on every save and what a script cannot yet do. The one
passing case at that position (x6) is not trustworthy: its twin differing by nothing but the
connection entries crashed twice.

**The shape of the third wire matters.** `end` twice, or `head` at the wrong moment, crashes;
the sequence that holds is `end`, `head`, `end0`, and `end` for every wire after that. Measured
to ten wires. `end0` differs from `end` only in whether the default tail block ends up before or
after the new record:

```
end    d[at:at+15] = DEFAULT_TAIL + rec          tail first, then the record
end0   d[at:at+15] = DEFAULT_TAIL, d[at:at] = rec   the record first, then the tail
head   take the pending body in front of the first wire, give that record a plain tail
```

`dsn_add_wire.py --mode` picks between them, and `_re/scratch/seq.py` reproduces any sequence.

**A pin slot is still what makes the wire a connection.** The slots load fine (y1, y2, z_end0,
the six and ten wire files) and they are filled from `--pin REF:INDEX`, one per pin the wire
lands on.

## What a generator should do

1. Instances by `dsn_add_instance.py` - byte identical to Isis's own, and they load.
2. Wires by `dsn_add_wire.py --mode end|head|end0` in the sequence above, one `--pin REF:INDEX`
   per end that lands on a pin.
3. One open-and-save round trip in the application. That is what embeds the device definitions
   for a scripted part, and it is also what rewrites the second section's index - after it, the
   design is an ordinary one and the next batch of wires starts the sequence again.

Keep a pristine copy of what the script wrote: after the round trip the file is no longer the
thing you can compare against.

## The round trip is the only acceptance test (and the news is not good)

The title check above (`design_loadcheck.ps1`) is not enough on its own, and this is the measurement
that says so. The same files, opened, saved from inside the application, closed, and then counted:

| file | bytes | after the round trip | instances | wires |
| --- | --- | --- | --- | --- |
| `BC_pick5.DSN` (the base) | 21588 | 21588 | 5 | 6 |
| `y1.DSN`, one wire `end` | 21646 | 21646 | 5 | 7 |
| `y2.DSN`, two wires `end head` | 21704 | 21704 | 5 | 8 |
| `z_end0.DSN`, three wires `end head end0` | 21762 | **16070** | **0** | 7 |
| the six wire build | 21952 | **16070** | **0** | 7 |
| `y0`/`y3`/`z_end` (third wire as `end` or `head`) | 21762 | unchanged, title bare | - | - |

So `end0` - and any build that used it - produced a file the application *opens* and then writes
back with **every instance missing**: a partial read that looks like a load. The three-wire shapes
that do not load at all are the honest failure. Counting instances in the saved file is how these
were told apart, and it is the check to use from now on:

```
pwsh -File _re/scratch/roundtrip_many.ps1 -ListFile list.txt -OutDir _re/scratch/rt
python _re/scratch/count_objs.py _re/scratch/rt/*.DSN
```

## And the wire that survives is not where it was written

The one wire file is the cleanest evidence. Before the round trip its wire reads
`(2.5, 1.0) (2.8, 1.0) (2.8, 0.0)` - the record this writer spliced in. After the round trip, the
same record reads `(0.7, 0.8) (2.8, 1.0) (0.7, -0.3)`: the middle point is mine, and the two ends
have been replaced by the endpoints of *other* wires in the design. Isis resolves a wire's ends
through its own ledger of tail blocks, so a spliced record that looks right in a hex dump is not a
wire at that position as far as the application is concerned.

That is the reason the file route can be trusted for instances and not for wires: what it writes
loads, and sometimes survives, but the geometry it asked for is not what the design ends up
holding. Anything that needs a wire *here* has to be drawn in the application.
