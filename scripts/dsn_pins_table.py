#!/usr/bin/env python3
"""Pin offsets per device, measured from this machine's own hand-wired designs.

Everything here comes from wire ends in .DSN files the *user* wired by hand, then cross-checked
between instances: an offset that shows up on every instance of a device is that device's pin,
because a wire only exists between connection points. That is why these numbers are trusted over
the ones in the device definition block, which are relative to a different origin.

    python dsn_pins_table.py                 # print the table
    python dsn_pins_table.py --device 74LS00
"""
import argparse

# offsets are relative to the anchor this project's dsn_netlist.py/dsn_objects.py read out of the
# record, in design inches, +y up
TABLE = {
    "74LS00": {                    # from hand_wire_2.DSN: U3:A, U3:B, U3:C agree
        "A": (-0.192, -0.108),
        "B": (-0.192, -0.308),
        "Y": (+0.808, -0.208),
    },
    "SW-SPST": {                   # from hand_new.DSN: SW1
        "1": (-0.092, -0.138),
        "2": (+0.408, -0.138),
    },
    "RES": {                       # from hand_new.DSN: R1 (device id 10k, value RES)
        "1": (-0.092, -0.048),
        "2": (+0.408, -0.048),
    },
    "LOGICPROBE": {                # from hand_new.DSN: U1
        "P": (+0.208, +0.142),
    },
}

# how far the record's anchor lands from the point that was clicked, per device, measured by
# placing one and reading the file back
PLACE_ANCHOR_OFFSET = {
    "74LS00": (-0.308, +0.208),
    "TERMINAL": (-0.100, +0.200),
}


def pin(device, name):
    return TABLE[device][name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device")
    a = ap.parse_args()
    for dev, pins in TABLE.items():
        if a.device and dev != a.device:
            continue
        print("== %s" % dev)
        for name, (x, y) in pins.items():
            print("   %-3s (%+0.3f, %+0.3f)" % (name, x, y))


if __name__ == "__main__":
    main()
