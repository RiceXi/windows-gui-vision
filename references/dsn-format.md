# The Proteus ISIS .DSN file

Everything here was checked by making a byte edit, opening the file in ISIS 7.8, saving it
again, and looking at what survived. Claims that did not survive that test are marked as such.

## Why anyone would do this

There is no automation API. Proteus 7 and 8 expose nothing for schematic authoring - the
registry has VDM debug drivers and a file association, no type library, and there is no
third-party tooling for these files. If you want to generate or batch-edit designs, you are
editing the file.

## Saving is stable, but only within one version

Open a design, save it twice without touching anything, and the two files differ by exactly
one byte (offset 177 in a 44 KB file). Take that as a volatile stamp and expect everything
else to round-trip.

A design saved by a 2006 build and re-saved by 7.8 differs by tens of kilobytes. Always build
your diffs from two saves of the same build, or you will be looking at the version
difference rather than your edit.

ISIS also writes a `<name>.DBK` beside the design.

## How a file is laid out

It opens with the literal text `ISIS SCHEMATIC FILE`, then the design properties in plain
text, then the objects.

An object record starts `02 <flags> <TYPE NAME> 00` and then its payload. Type names seen in
the wild: `COMPONENT`, `WIRE`, `BUS WIRE`, `WIRE DOT`, `GENERATOR`, `TERMINAL`, `MARKER`,
`VPROBE`, `IPROBE`, `ACTUATOR`, `INDICATOR`, `2D GRAPHIC`, `SUBCIRCUIT`, `SCRIPT`.

Strings are length-prefixed with a single byte, and the length counts the leading `$` of a
part name: `08 "$SINEGEN"`, `09 "$PULSEGEN"`, `0B "__DEFAULT__"`, `06 "RESISTOR"`. The design
description is the exception - it uses a four-byte length (`5E 02 00 00`).

Coordinates are signed 32-bit little-endian in units of 10 nm, and 2540000 of them make an
inch. So a wire record

```
02 7F "WIRE" 00 | 00 00 | 02 00 | (-11684000, 5080000) | (-12954000, 5080000)
                            ^ point count
```

is a horizontal wire from (-4.60, 2.00) to (-5.10, 2.00) inches. Round numbers on the 0.001
inch grid are how you know you decoded it correctly.

The WIRE payload is `00 00`, a u16 point count, then that many (int32 x, int32 y) pairs in
order - a bent wire is one record with three or more points.

To find where a payload starts: `offset of the type name + len(name) + 1`. Records are not
aligned to anything, so do not assume they are, and check decoded coordinates against the
grid before believing them.

## What editing the bytes gets you

Moving a wire works: shifting one up by an inch came back at y = 3.00 in after a load and
save.

Replacing text works: a marker written into the design description showed up in ISIS.

Renaming a part to a *same-length* name works: `$SINEGEN` to `$DCLOCK0`, both eight bytes
including the dollar. ISIS opened the file, kept the new name when it saved, and the file
changed by exactly those fourteen bytes. The model follows the new name, because Proteus
resolves the part by name - but the symbol drawing does not change, because each design embeds
the drawings of the parts it uses.

Renaming to a different length does not work: `$SINEGEN` to `$PULSEGEN`, eight bytes to nine,
with the length byte updated and a byte inserted, made ISIS hang on load. Something in there
counts on the old length and I never found what. Treat the record as fixed-size and clone it
whole.

## Adding a part

This is the one thing in this file that did not survive re-testing - in September 2026 every
design built this way failed to load. The byte layout below is still what the edit does; the
re-test is in [dsn-generate.md](dsn-generate.md). Take a record that ISIS itself produced for
that part, insert it before the second `ISIS CIRCUIT FILE` marker, and fix up the four places
that track lengths:

- the u16 "next id" counter at the first `ISIS CIRCUIT FILE` marker plus 19;
- a u16 near offset 12319 in small designs whose value is the object-area end plus 48;
- the u32 inside the directory that equals the old object-area end;
- the one-byte entry count at `ROOT1` plus 12, and a new entry appended to the directory.

Do the insertion first and then apply the directory edits, shifting every post-insertion
offset by the length you inserted. Writing the directory fields at their pre-insertion
offsets corrupts the record you just added.

How well it works, measured: starting from a design of 18372 bytes, inserting a 347-byte
component record produced 18734 bytes, the record count went from four to five, and the
next-id counter from 16 to 17. Compared with the file ISIS writes when you add that same part
by hand, six bytes differ: two for a timestamp, two for the reference name I chose, and the
two cosmetic fields listed below. ISIS opens the generated file without complaint, and the
added record survives a save from inside ISIS.

One caveat that cost me an afternoon: ISIS rewrites parts of a file when it saves, so a byte
diff taken *after* a save is only meaningful between files with the same save history. Compare
generated and hand-made files before either one has been opened.

## Still unknown

The tail of the file holds a second `OBJECT DATA` section followed by a name list of
`[u8 length][name]` entries. Two values near there look like absolute file offsets, but the
per-object entries (`U1`, `R1`, `P2C...`) carry two-byte ids rather than record offsets, so
searching for a record's offset does not find them. Any re-serialiser that wants to change
record sizes has to decode that id scheme first.

Two fields differ from ISIS's own output and apparently are not validated on load: the
sequence u16 in a directory entry, and one flag byte near the end of the file. Designs with
those left alone load and render correctly.

## The workflow that keeps you honest

Work on a copy. Open that copy in ISIS once and save it, so your baseline is in the current
format. Patch the bytes. Open it in ISIS and save again. Then re-parse: anything that survived
the round trip was genuinely loaded, and anything ISIS ignored has been overwritten.

If ISIS comes up as `未响应` after a patch, the patch broke something internal. Kill it rather
than waiting.
