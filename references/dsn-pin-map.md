# The pin map Isis writes for a new part

Measured by comparing the base design with the same design plus one part placed by the
application itself (`dsn_diff.py`, and the 451 byte difference the acceptance test reports).

What a placement adds is a 420 byte instance record and then a 31 byte directory entry carrying
the part's pin map:

```
00 00 00 00 15 00 08 00 00 00 | 04 "U4:B" | 06 00 | 03 00 | 01 "A" 01 "4" 01 "B" 01 "5" 01 "Y" 01 "6"
                               reference   ?       3 pins  (name, pin number) pairs
```

The pin numbers are the physical pins of that *unit*, not of unit A: A/4, B/5, Y/6 is unit B of a
DIL14 74LS00, while unit A is A/1, B/2, Y/3.

## The writer has this wrong

`dsn_add_instance.py` does write a pin-map entry, so the format is understood. It writes the **unit
A pin numbers on every unit**: the appended part in the instances-only build carries

```
04 "U4:B" ... 01 "A" 01 "1" 01 "B" 01 "2" 01 "Y" 01 "3"
```

where the placed one carries 4, 5, 6. That is a real defect for anything that reads the map -
netlists especially - and it is a local fix: take the pin numbers from the unit's own PINOUT text
rather than reusing the first unit's.

## Two facts worth keeping from the same comparison

* the base design's own parts have **no** pin-map entry at all, and they are exactly the parts that
  wire up. So the entry is something Isis writes when it places a part; it is not what makes a part
  wireable.
* apart from that entry and the instance record itself, an appended part and a placed part are the
  same bytes in the same shapes. That is an argument that the file route is not what makes added
  parts unwireable - the gesture that cannot draw is the more likely culprit, and every probe
  result that suggested otherwise was taken with that gesture.
