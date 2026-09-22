# Wires in a .DSN

Status, September 2026, ISIS 7.08 SP2. Adding a wire by editing the file works, and for the
design family this was measured on the result is now **byte-identical to what Isis itself
writes**, apart from the two byte stamp it rewrites on every save. Multi-wire designs are the
part that is not finished: see the load test table at the bottom before relying on it.

`scripts/dsn_add_wire.py` does the writing, `scripts/dsn_walk.py` reads a design's wire
section back so you can see what you are editing, and `scripts/dsn_diff.py` is the comparison
tool the whole thing was worked out with.

## How a wire is stored

```
FF FF FF 00 FF FF FF 00 | 02 7F "WIRE" 00 | 00 00 | u16 point count | points | body
     8 byte prefix          9 byte header           count at +9       int32 pairs
```

so a wire's own record is 34 + 8n bytes for n points, with points as (x, y) int32 pairs. What
follows the points is the wire's **body**, and that is where the rest of the wire lives: a
`01` tag with a point and a list of tail offsets, or a `30` tag with a point, or an attachment
list of named properties, and at the very end a **15 byte tail block**:

```
00 1D 00 00 00 00 C0 9E 00 00 00 40 00 00 01      the shared default tail
```

That 15 byte block is not a separate object and it is not attached to the wire by position
alone: it is what the file's many pointer fields point *at*. Every wire body ends with one,
and most wires' bodies are nothing but the block.

The practical consequence is that the object area is position-sensitive: inserting bytes
anywhere shifts every offset after it, and a field that used to name a tail block now names
whatever landed on that number. A stale pointer is exactly what produces
`access violation in module VGDVCDLL` on load.

## What Isis does when a wire is drawn

Two saves of the same design, one edit apart (`scripts/dsn_diff.py`), show three things
happening at once:

1. **The new wire takes over a body.** Isis splices the new wire's record in where a body
   already starts, hands that body to the new wire, and gives the previous owner a plain
   default tail. Nothing is copied: the body bytes stay where they are and the records move
   around them.
2. **Every pointer past the insertion point is shifted** by the number of bytes inserted.
   Recognise them the same way `dsn_walk.py` does: a four byte field whose value is the offset
   of a 15 byte block that occurs at more than one wire body start.
3. **The zeroed "current tail" slots get filled** with the tail offset the insert creates.
   They sit at the end of a run of three tail offsets; a design Isis saved with no wire drawn
   in that session has them zero.

Where the new wire goes depends on the design's state, and there are two shapes:

| shape | when | what moves |
| --- | --- | --- |
| `end` | nothing pending at the head record | the last wire's body travels to the new wire |
| `head` | the record before the first wire still carries a pending body (`01` tag + point + tail refs) | that pending body travels to the new wire, and the record keeps a plain tail |

Both are byte-verified against Isis's own output:

* `end`: five instances, one wire drawn by Isis (6 points, autorouted). Reproducing it gave
  21670 bytes, identical to Isis's save except the stamp and one flag byte at the end of the
  file that Isis clears.
* `head`: the same design with a **second** wire drawn by Isis. Reproducing it gave 21720 bytes,
  identical except the stamp.

Both ground truths came out of the same recipe, which is the one worth reusing:

1. copy the design, open it in Isis, save, close - that is the baseline (do **not** compare
   against the pristine file: Isis normalises on save and the diff drowns);
2. copy the baseline, open, make one edit, save, close;
3. diff the pair. The changed fields are the whole specification of the edit.

## What the load tests say

### A wire that touches nothing is not a wire

The most useful thing the acceptance test taught is why generated designs degrade. Measured on
the five-instance base, with `dsn_savecheck.ps1 -Modify` (open, drop one more part in so Isis
actually writes, save, compare the object list):

| build | what Isis wrote back |
| --- | --- |
| base design, nothing added | whole: 6/6 wires, 7/7 references, plus the part I dropped in |
| four appended instances, no wires | whole: 11/11 references, plus the dropped-in part |
| one appended wire, both ends in empty canvas | **the wire is gone**; the save has the base's six wires and one other |
| three appended wires | **partial**: only U1, U2, U3:A survive, 16505 bytes |
| four instances plus four wires (the latch) | **partial**: same stop point, U1, U2, U3:A |

The reading: Isis drops a wire whose endpoints are not connection points, and that is not an
edge case here - it is what the generated designs were full of. Reading `Wiring_Up.htm` from
the application's own help (see below) says it outright: *a connection point can connect to
precisely one wire*, wires start and end on connection points, and there is no wire mode to
draw a free one.

So the rule for the writer is not "put the points where you want the copper", it is "put the
ends on connection points". Where the pins actually are has to be measured per unit, and the
first measurement says the offsets in `pin_tables.json` are about 0.1 inch off: probing the
part Isis placed itself in the control design found a live connection point at
anchor + (-0.25, +0.125), where the table says (-0.25, +0.025). Wires written to the table's
coordinates do not touch the pin. That measurement needs finishing before the pin tables can
be trusted.

### There is no wire mode

Straight out of `GENERAL_CONCEPTS/Wiring_Up.htm` in the bundled help, and it explains months of
misunderstandings: *"You may have noticed that there is no Wire icon. This is because ISIS is
intelligent enough to detect automatically when you want to place a wire."* You move the
pointer over a connection point until the cursor turns into a green pencil, click to start,
click another connection point to commit. Consequences that matter for automation:

* there is no toolbar button to select, so a click on the canvas is the only way to draw;
* a click on empty canvas does nothing at all, which is why the first attempts "drew" nothing;
* a pin or terminal end takes exactly one wire; a wire's body is a connection point all along
  its length, and ISIS adds a junction dot where a third wire meets;
* because a wire can only start and end on connection points, an injected gesture needs two
  real connection points - a pin pair, or a pin and a wire.

Two tests, and the weak one has to come first because it is the cheap one:

* `scripts/design_loadcheck.ps1` - does Isis accept the file. Exit 0 yes, 1 silently refused, 2
  crash dialog. **This is not enough on its own**: a design whose object area is damaged part
  way through loads *partially*, and the title still names the file.
* `scripts/dsn_savecheck.ps1` - opens it, saves from inside the application, closes it, and
  compares the reference designators and wire count before and after. A clean design comes back
  unchanged; one that only partly loaded comes back with the objects after the damage missing.
  This is the test that matters for anything a script writes.

On the five-instance base design:

| construction | wires | load check | save check |
| --- | --- | --- | --- |
| one insert, `end` | 7 | yes | full load (a previous round trip kept all seven wires) |
| `end` then `head` | 8 | yes | - |
| `end`, `head`, `end` | 9 | yes | - |
| four instances plus four wires (`end,head,end0,end0`) | 10 | yes | **partial: Isis kept two of the five packages** |
| `end` then `end` | 8 | **crash** | - |
| one insert, `end`, on a Labcenter sample (Counter5) | 12 | **crash** | - |

So the rules above reproduce what Isis writes, and a one-wire insert lands whole, but a
multi-wire file is not trustworthy yet: the same edits in a different order crash, and the
four-wire build passes the load check while having lost most of the design. What the model is
still missing is somewhere in the interaction between the section header, the junction records
and the attachment lists - the reference design has all three, including a wire carrying a
`$DIGGEN` property, and a sample design with a different section header crashed on the very
first insert.

Until that is understood, the file route is for instances and for one wire, and the save check
is what tells you whether you got away with more.

## Reading your own design first

Before writing anything into a design, look at what its section header looks like:

```
python scripts/dsn_walk.py design.DSN
```

If there are no shared tail blocks, no pointer fields, or the record before the first wire
does not look like anything described above, the writer's assumptions do not hold for that
file and it needs the two-save diff treatment before it can be trusted.

## The tools

| script | what it is for |
| --- | --- |
| `dsn_walk.py` | read a design: wires, points, bodies, tail blocks, pointer fields |
| `dsn_diff.py` | diff two saves byte by byte, with context |
| `dsn_add_wire.py` | write a wire (`--mode end` or `--mode head`) |
| `dsn_add_instance.py` | add an instance of a device the design already embeds |
| `design_loadcheck.ps1` | does it load: exit 0 yes, 1 silently refused, 2 crash dialog |
