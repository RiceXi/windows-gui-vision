# Part records, and the library you can lift them from

Measured on ISIS 7.08 SP2, build 10468, September 2026.

A part in a `.DSN` is one record, and only ISIS writes a valid one. There is no way to
synthesise a record for a part that no design has ever contained, so the practical move is to
take records out of designs that already have them. `scripts/dsn_templates.py` walks a folder
of designs and stores what it finds as json.

```
python scripts/dsn_templates.py scan  "C:\Program Files (x86)\...\Proteus 7 Professional\SAMPLES"
python scripts/dsn_templates.py build dsn_lib.json <same folder>
python scripts/dsn_templates.py show  dsn_lib.json NAND_2
```

The `SAMPLES\` folder that ships with the install turned out to be a good source: 368 distinct
parts, and the json comes to about 1.9 MB. It covers the parts you would expect - `RES`,
`RESISTOR`, `CAP`, `CAP-ELEC`, `POT-LIN`, `LED-RED`, `NPN`, `TIP31`, `TL071`, `8051`,
`PIC16F877` - along with the simulator primitives (`OSCILLOSCOPE`, `LOGIC ANALYSER`,
`$SINEGEN`) and a long tail of one-off parts that individual samples happen to use.

## What is in a record

It starts `FF 02 <two-character reference>`, then:

| offset | contents |
| --- | --- |
| +4 | two int32s, x and y in 10 nm units |
| after that | `COMPONENT ID`, `COMPONENT VALUE`, `SUBCKT NAME`, `PROPERTIES` sub-blocks |

The part's library name comes out of `COMPONENT VALUE`, which is a single-byte length followed
by the name. Simulator primitives have no `COMPONENT VALUE` and are named `$NAME` instead,
which is why both spellings appear in a listing.

Two things to know before using the data:

The extractor splits on `FF 02` markers, so a record runs to wherever the next part's record
starts. The last part in a design therefore absorbs everything after it - the NAND record in
one 18 KB test design came out at 4414 bytes, where the part itself takes 347. That is fine
for a lookup table and wrong for cloning.

Wires are not in the directory. The same test design held eight wire records and six directory
entries, because the directory only lists objects that have a name. `02 7F "WIRE" 00 | 00 00 |
u16 point count | points` is the whole of a wire record, and `dsn_build.py` builds one.

## What it is good for

Reading. Part lists, positions and attribute values fall out of a design easily, and decoded
coordinates land on the 0.1 inch grid when you have got the offsets right, which is how you
know you have. Comparing two designs, or answering "which of these samples uses a 741", is a
few lines of script.

It is not a way to build a design. Inserting these records into another design produced files
ISIS would not load, whichever design the record came from. That result and the tests behind
it are in [dsn-generate.md](dsn-generate.md).
