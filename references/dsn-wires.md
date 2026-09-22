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

#### Where the pins are is the real blocker (measured, and one claim retracted)

**Correction to an earlier note in this file.** A first pass found one "hit" on a part Isis
placed itself - a small ink change at anchor + (-0.25, +0.125) - and it was written up as a live
connection point. Repeating it does not reproduce: the same point, and forty more around the
symbol on both sides at 0.05 inch steps, all came back with no change at all, in a fresh session
with the same file. So the hit was not a wire starting; treat it as noise from a repaint. What
stands is the negative result, and it now covers both routes:

* a part the **script appended** to the design: no connection point anywhere on it;
* a part **placed through the GUI** (the control design's U4:B, written by Isis itself, saved and
  reopened): no connection point found either;
* the design's **own** parts, the ones the base design shipped with, do answer - the earlier
  session's probe found exactly one wire around the junction at (0.7, 0.8), and the wire gestures
  in this file were all drawn between such points.

That is the state of the blocker: a circuit made of *newly added* parts cannot be wired, by
either the file route or the GUI route, while the parts a design already had stay wireable.
Until something changes that, the skill can add parts (verified) and cannot connect them.

The earlier version of this section said the placed part answered at its pin and that
`pin_tables.json` was 0.1 inch off. Both of those came from the single unreproducible hit, so
neither should be relied on; the pin table still has to be measured properly before generated
nets can be trusted to land on pins.

Probing is cheap per candidate but has to be repeated: click a candidate, move the pointer,
capture the canvas, capture it again, subtract - `scripts/proteus_probe_pins.ps1` does the
clicking and this file's `diff2.py`-style check is the cheaper filter. What it costs is time:
about 1.2 s per candidate, and the pins are sparse.

One confound is worth ruling out, because it would have made every earlier probe meaningless:
in Component mode, if a device is still armed in the selector, a click on the canvas *places
another one* instead of starting a wire, so a probe run there measures nothing. Repeating the
scan in Selection mode (选择模式), where a click cannot place anything, gives the same answer -
22 candidate points down both sides of the placed part, no wire, file unchanged. So the
placement really does produce a part with no usable connection points, and the parts the design
already had still answer. That is the narrow, confirmed blocker.

The open question is what a *hand*-placed part has that these two do not: the design this base
was cut down from was built by clicking in Isis, and its parts wire up fine. Comparing the
record of a hand-placed part against a script-placed one, byte for byte, is the cheapest way to
find the difference and it needs no GUI session.

#### The naming mismatch is the lead

Listing the `ff <len> <name>` records inside each instance, the design carries two families of
part, and they do not agree on the device:

| parts | device identifier the record names |
| --- | --- |
| the two the design was built around (U1, U2) | `NAND2`, and the symbol record `NAND_2` |
| everything added since, by script or by injected placement (U3:A, U3:B, ... U4:B) | `74LS00` |

The symbol and unit records the design actually embeds are the `NAND2` / `NAND_2` ones (and
their `U1(Q)` / `U2(Q)` drawings). A record that names `74LS00` is pointing at an identifier the
design does not define, which is the second half of the warning already in
[dsn-append.md](dsn-append.md): *a Labcenter sample carries definitions under old device
identifiers and placing a part from its device list produces a stand-in with no pins.* A part
that draws but has no connection points is exactly what that predicts.

So the concrete next step is to make the parts the writer adds name the identifier the design's
own symbol records use - `NAND_2`, not `74LS00` - and then re-run the pin probe. Every
generated part in this design currently names `74LS00`, so none of them can be expected to be
wireable, whichever route put them there.

#### Renaming alone does not do it, and the real difference is the base design

Tried: every `74LS00` device reference in the instances-only build rewritten to `NAND_2`, in
place so nothing moved (19 occurrences, file still 23396 bytes, still loads). The pin probe in
Selection mode then found nothing on the renamed part either - same 14 candidate points around
the symbol, all zero. So the identifier is not what makes the connection points appear; it is
consistent with the append notes, where renaming only changed the drawing and never produced a
part that could be wired.

The pattern that is left, and it is a hypothesis rather than a measurement: this base design was
cut down from a Labcenter sample, and *its* embedded definitions are the sample's - the symbol
records are `NAND2` / `NAND_2`. Parts added from the current library name `74LS00`, so they
resolve against a definition the design does not carry and become stand-ins. The designs that
behave properly are the ones a person built in Isis: the experiment-1 schematic was made by
picking devices and placing them, and everything in it wires up.

That is the next test, and it needs one Pick Devices pass rather than any new code: take an
empty design, add 74LS00 through Pick Devices so the design embeds the *current* definition,
place a part with `proteus_place.ps1` (Component mode, which is now reliable) and probe its
pins. If those answer, the rule for the whole skill becomes: build on a design that was created
this way, and the part-adding and wire-drawing half falls into place.

#### Naming is closed: three variants, no pins in any of them

The identifier hypothesis is now tested properly, by rewriting the added parts' records to match
the design's own pattern - `NAND2` as the device id and `NAND_2` as the symbol reference, the
same pair the working U1/U2 records carry (9 instances, both fields, in place, file still 23396
bytes and still loads) - and then probing in Selection mode. Sixteen candidate points around the
symbol: all zero. Together with the earlier `NAND_2`-only and untouched-`74LS00` runs that is
three variants, no connection points in any of them.

So the identifier is not the link. That leaves the conclusion the append notes reached by
elimination: whatever attaches an instance to its symbol and its connection points is not
carried in the record at all - it is either an offset the insertion moved or a side table only
Isis maintains - and a part that has to be wireable must be created by the application rather
than written into the file.

The one thing still not separated is *hand* placement from *injected* placement: the designs in
this account that wire up were built by a person clicking, and every part built by automation -
appended or placed - has come back unwireable. The next attempt is to make the injected
placement look like a hand one (move the pointer first so a preview is following it, click once
to drop, then a slow second click), and if that changes nothing, a single hand-placed reference
part is what settles it.

#### Before trusting any of the above: the probe does not reproduce

The honest correction. This section's pin conclusions rest on a rubber-band probe - click a
candidate, move the pointer, capture the canvas twice, subtract - and that probe does not
reproduce. The base design's junction at (0.70, 0.80) gave a 226 pixel reading the first time it
was tried and reads zero now, and the file oracle agrees: clicking it and finishing on a second
known point commits no wire and leaves the file unchanged.

So the transient hits at (0.70, 0.80) and at the placed part's (2.75, 3.125) were probably not
wire starts, and everything above that depends on them - "appended parts have no pins",
"placed parts have no pins", "the identifier does not matter" - is **unproven rather than
settled**. The parts may well be wireable; what is established is that this probe cannot say.

What stays, because it is measured with the file rather than with pixels:

* appended instances are byte-exact and the design loads whole (`dsn_savecheck.ps1 -Modify`);
* generated *wires* are dropped or only partly loaded, and a generated wire with both ends in
  empty canvas disappears on save;
* placement needs Component mode (`proteus_place.ps1` now clicks it, and a placement adds exactly
  one 451 byte record);
* the help says there is no wire mode and that wires run connection point to connection point;
* ISIS 7 registers no COM automation server, so the file is the only automation surface.

The next thing to do is not another conclusion, it is to rebuild the pin test so it reproduces:
`proteus_probe_pins.ps1` against a known-good pin, checking the saved file for the committed
wire (that is how it produced exactly one wire once), and if that does not reproduce either, do
it the slow, unambiguous way - one candidate per save, file diffed after each.

#### The control that settles it: the gesture itself does not draw

Ran the test that should have been run first, with two points that *must* be valid connection
points - midway along two existing wires, which the help says are connection points along their
whole length. (0.65, 0.80) and (1.05, 0.80) in the base design, Component mode clicked first,
nothing armed. No wire commits: file 21588 bytes before and after, still six wires. Repeated
with a slow two-step gesture, a pointer move between the clicks and a second of settling time -
same result.

So the instrument is not just imprecise, it does not work in these sessions at all: whatever the
earlier session had set up, this one does not reproduce it, and every "no pins" reading taken
with it means nothing at all. That also removes the reason to prefer one part-creation route
over the other - the question of whether added parts are wireable is open again, and it cannot be
answered until a gesture that draws is available.

What to do next is therefore mechanical rather than scientific: get one wire committed from the
kernel outwards - confirm the mode from the status bar (the hint sits in the bar at the bottom,
OCR it rather than assuming), click the Component Mode button, then click a point in the middle
of an existing wire and see whether the canvas starts following the pointer - and only once that
happens go back to probing pins. If the gesture will not draw at all, the GUI half of this
workflow is not available and the file half has to stand on its own.

#### Two things that were sitting on top of the canvas

Diagnosing the gesture turned up both of them, and either is enough to eat every click.

* **The notice window is parked exactly where the test points are.** Listing the windows of the
  Isis process right after a launch shows a second visible window titled `ISIS Professional` at
  (573, 358), 294x136 - a 294 by 136 rectangle sitting on the canvas. The base design's wires run
  across y = -0.3 to 0.8 inch, which is screen y 370 to 480, and x 0.6 to 1.4 inch, which is
  screen 850 to 930: the mid-wire points used as the control are inside that rectangle, so their
  clicks land on the notice, not the canvas. Closing it is what `-CloseNotices` is for, and the
  close should be verified by listing the windows again rather than assumed. Picking a test point
  outside the rectangle - for example (1.30, 0.80) on the long input wire, screen (920, 370) - is
  the cheap way to tell the two cases apart.
* **The status bar keeps saying it is loading.** `proteus_wait_ready.ps1` polls the hint area and
  stops when the text no longer reads 正在加载设计, and on this machine the message was still
  there more than four minutes after launch - while the earlier `design_loadcheck.ps1` runs were
  reporting the design loaded. So the message lingers and is not a readiness signal; do not gate
  the first click on it.

Both of these mean the "the gesture does not draw" conclusion above is not safe either. The
reliable sequence is: launch, list the windows, close the notice, list them again to confirm only
the main window is visible, then click a point that is both a connection point and outside where
the notice used to be.

#### Five attempts, no wire - the gesture does not work in these sessions

Run with the sequence above, in Component mode, with the notice window verified closed:

| attempt | result |
| --- | --- |
| mid-wire (0.65, 0.80) to mid-wire (1.05, 0.80) | no wire, 21588 bytes unchanged |
| the same, slow two-step with a pointer move between clicks | no wire |
| mid-wire (1.30, 0.80) to (0.85, 0.80), both outside the notice rectangle | no wire |
| the same with a warm-up click first, in case the first click was eaten by activation | no wire |
| the documented probe recipe: 9 candidates around (0.7, 0.8), finishing on (0.7, 0.8) | no wire |
| the pair Isis itself drew in this design's history: (0.70, 0.80) to (0.70, -0.30) | no wire |

Injected input does reach the application: a placement through `proteus_place.ps1` adds exactly
one 451 byte record, the mode buttons change the panel, list rows select. So the failure is
specific to wire placement, and after six attempts with the known confounds removed it is not a
coincidence.

The most plausible remaining mechanism is the one the coordinate notes already lean on: Isis
snaps a pointer that is within a few pixels of a connection point onto it, and every attempt here
depends on that snap engaging. If snap is not engaging in these sessions, a click a few pixels
away lands on empty canvas and does nothing at all - which is exactly what is observed, and
would also explain why the previous session (where one wire was produced) could do it. Checking
and turning snap on is the next cheap thing to try, before any more conclusions about pins.

Beyond that, the fastest unblock is a single hand-drawn reference: open the base design, draw one
wire by hand, save and close. That gives a file where the wire is known to be real, and it tells
us at once whether the blocker is the automation or this copy of Isis.

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
