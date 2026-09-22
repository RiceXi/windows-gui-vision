# The pin map a new part carries

Measured by diffing the base design against the same design plus one part placed by the
application (`dsn_diff.py`; the acceptance test reports the same edit as +451 bytes).

## What a placement adds

A 420 byte instance record and then a 31 byte directory entry holding the part's pin map:

```
00 00 00 00 15 00 08 00 00 00 | 04 "U4:B" | 06 00 | 03 00 | 01 "A" 01 "4" 01 "B" 01 "5" 01 "Y" 01 "6"
                               reference   ?       count   (pin name, physical pin number) pairs
```

The numbers are the physical pins of **that unit**, not of unit A. For a DIL14 74LS00:
unit A is A/1 B/2 Y/3, unit B is A/4 B/5 Y/6, unit C is A/10 B/9 Y/8, unit D is A/13 B/12 Y/11 -
which is what the device's own PINOUT block holds, one number per unit in unit order.

## The writer already gets this right (correction)

An earlier version of this page claimed `dsn_add_instance.py` reused unit A's numbers on every
unit. That was a misread of a hex dump, and it is wrong. Reading the entries out of a fresh build
shows the tool writing exactly the PINOUT's per-unit numbers:

| reference | entry says |
| --- | --- |
| U3:A | A/1, B/2, Y/3 |
| U3:B | A/4, B/5, Y/6 |
| U3:C | A/10, B/9, Y/8 |
| U3:D | A/13, B/12, Y/11 |

`pinout()` parses the block into `[1, 4, 10, 13]` and the entry builder indexes it by the unit it
just chose, so the map is right by construction.

## What the comparison does say

* the base design's own parts carry **no** pin-map entry at all, and they are exactly the parts
  that wire up - so this entry is something Isis writes when it places a part, not what makes a
  part wireable;
* apart from that entry and the instance record itself, an appended part and a placed part are the
  same bytes in the same shapes, and the entries agree field for field. That is an argument that
  the file route is not what makes added parts unwireable, and that the gesture which cannot draw
  is the thing to fix first.
