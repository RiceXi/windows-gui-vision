# The save that embeds the missing definitions

Two files from the same start, one save apart:

| file | bytes | first section | object area | second section | object markers |
| --- | --- | --- | --- | --- | --- |
| `hand_wire.DSN` | 21949 | 13219 | 7438 | 1292 | 2 COMPONENT, 3 PIN, 19 GENERATOR, 12 WIRE |
| `hand_wire_2.DSN` | 74185 | **65150** | 7743 | 1292 | **55 COMPONENT, 9 PIN, 14 ACTUATOR, 19 PORT, 16 TERMINAL, 12 INDICATOR**, 27 GENERATOR, 16 WIRE |

The user made the second by copying the first, drawing three more connections in the application
and saving. The object area barely changed - 7438 to 7743, which is those few wires. The extra
50 KB is in the **first section**, and what appeared there is the vocabulary of symbol drawings:
COMPONENT, PIN, PORT, TERMINAL, ACTUATOR, INDICATOR. That is an embedded **library of device
definitions** that the first file did not carry.

## Why this matters

This is the missing link the append notes kept circling: parts written into a design by script
name a device whose symbol and unit drawings the design may not embed, so they render as
stand-ins. Once the application has opened and saved such a design, it fetches those definitions
from its library and writes them in - and from then on the parts are ordinary parts, wireable and
everything. It also fits the user's evidence: their hand-drawn wires all stuck, and the second
file is the one that carries the definitions.

## The recipe, therefore

Generating a circuit is: write the parts and wires into the file, then **open the result in Isis
and save it once**. That single round trip embeds whatever the parts were missing and hands the
design back complete. It needs a person for the launch (the modal notice has to be clicked
through) unless the notice can be cleared by automation, which is the one thing still open here.
