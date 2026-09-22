# Proteus notes

Measured on a Chinese-language Proteus 7.8 install (`ISIS.EXE`, `ARES.EXE`). Menu items are
given in Chinese with the English in brackets where it matters; the English builds use the
same layout.

## Capture

ISIS 7 and ARES 7 are GDI applications, so PrintWindow gives you the window's own pixels and
never the cursor. Dialogs come out fine too.

Proteus 8's design window is GPU-composited and captures as solid black. Its home page is a
web view and captures normally. If you need screenshots out of Proteus, 7 is the easier
target.

One quirk worth knowing before you trust a label: this build renders some text objects as the
literal placeholder `<TEXT>` when a font resource is missing. Labcenter's own sample designs
do it too. The symbols themselves draw correctly, so identify a part by its symbol shape, or
by parsing the saved `.DSN`, rather than by reading its caption.

## Layout

Do not hard-code toolbar coordinates - that is what made the first version of this folder
useless on any other machine. Calibrate instead:

```
powershell -File scripts/capture_window.ps1 -OutPath pw.png -ProcessId <isis-pid>
python scripts/calibrate.py --print pw.png --out calib.json
python scripts/layout.py init layout.json --from calib.json --app "Proteus ISIS 7"
```

On a maximized ISIS 7 window the detector lands near these values, which is a useful check
that it found the right things. They are logical pixels, so they are the same at any DPI:

| anchor | value |
| --- | --- |
| mode toolbar icon column | x = 15, button pitch about 22 px |
| object selector list | first row y about 211, pitch about 13 px, click column x about 100 |
| canvas | starts around x 164, y 85 |
| preview pane | about x 43..141, y 94..185 |

If the detector reports far more bands than you expect it has picked up the menu bar and the
window border as well. The button pitch is the reliable signal, and the first regular run of
bands is the mode toolbar.

## What the modes contain

The mode buttons are a single column on the left; the object selector's title and contents
change with the mode. Verified contents:

| mode | list title | items |
| --- | --- | --- |
| 元件模式 | DEVICES | whatever Pick Devices added |
| 终端模式 | TERMINALS | DEFAULT, INPUT, OUTPUT, BIDIR, POWER, GROUND, BUS |
| 器件引脚模式 | PINS | pin types |
| 图表模式 | GRAPHS | ANALOGUE, DIGITAL, MIXED, FREQUENCY, TRANSFER, NOISE, DISTORTION, FOURIER, AUDIO, INTERACTIVE, CONFORMANCE, DC SWEEP, AC SWEEP |
| 激励源模式 | GENERATORS | DC, SINE, PULSE, EXP, SFFM, PWLIN, FILE, AUDIO, DSTATE, DEDGE, DPULSE, DCLOCK, DPATTERN, SCRIPTABLE |
| 虚拟仪器模式 | INSTRUMENTS | OSCILLOSCOPE, LOGIC ANALYSER, COUNTER TIMER, VIRTUAL TERMINAL, SPI DEBUGGER, I2C DEBUGGER, SIGNAL GENERATOR, PATTERN GENERATOR, DC VOLTMETER, DC AMMETER, AC VOLTMETER, AC AMMETER |
| 图纸连接器模式 | PORTS | sheet ports |
| 2D 图形 / 标记 | GRAPHIC STYLES / MARKERS | drawing styles and markers |

Generators and instruments are simulator primitives and are deliberately hidden from Pick
Devices. The mode buttons are the only way to reach them, which is why the toolbar matters.

## Placing things

Components, generators and instruments take three clicks: the list row, a nearby free point,
then the target. One click on the canvas only moves the preview, and it is easy to conclude
the placement failed when it has not started.

`scripts/proteus_place.ps1` does it from a design coordinate. Measured details, all of which
cost time to find:

* the row has to be hit in the text, not the panel. At window coordinates, a click near
  (60..80, 212) lands on the buttons above the list and opens Pick Devices or the Devices
  Libraries Manager instead; row 0 is at about (72, 220) with a 13 pixel pitch below it;
* each click must come from its own process with about a second between them. Two clicks issued
  in one process, 700 ms apart, were ignored; the same two clicks from separate short-lived
  processes placed the part every time;
* the point clicked and the coordinate ISIS stores are not the same point. Clicking design
  (3.600, -1.500) stored the part at (3.292, -1.292) - 0.308 inch left and 0.208 inch above.
  The tool asks for the coordinate you want and clicks at the compensating point;
* asked for (3.600, -1.500) and (2.000, 1.000), it produced (3.592, -1.492) and (1.992, 1.008):
  within 0.01 inch. Both parts were drawn - ink subtraction found 702 pixels where the base
  design has none.

What is not solved: where those new parts' pins are. A grid probe over one of them found no
connection points at all, and the pin offset that the design's older parts of the same device
answer to did not work on it. Until that is measured, a newly placed part can be positioned but
not scripted-wired.

Chart frames and other rectangles want two different points - one corner, then the opposite
one. Two clicks at the same point give a zero-size frame.

The anchor is the symbol's top-left, not its centre. A logic analyser or pattern generator
extends two or three grid squares right and down from where you clicked, which is why my
first attempt at a figure set had them clipped on the right.

Instruments and probes draw a long dotted leader line down the sheet. A crop that includes it
comes out tall and thin and looks like a mistake; crop to the symbol.

## Simulation

`F12` toggles interactive simulation and the title gains （仿真中……）. For graph-based
simulation, place a GRAPHS object, select it, and press `space`.

Most launches show a notice dialog with no usable accessibility text. Press `Return` to
dismiss it, or it will be sitting in the middle of every screenshot you take afterwards.

## Saving and opening

A new design opens as `UNTITLED`. 文件 → 另存为 (`Alt+F`, `a`) preselects the file name stem,
so typing a full path without the extension and pressing `Return` saves there. A bare name
goes to the install's `BIN\` folder, or to the per-user VirtualStore copy of it under
`AppData\Local\VirtualStore\Program Files (x86)\...`, which sandboxed shells cannot read.

文件 → 新建设计 (`Alt+F`, `n`) asks 保存当前设计的改动? first, with 是/否/取消. 取消 aborts the
entire new-design action, so answer 否 (`n`) to discard and carry on. This one wasted hours:
the dialog kept appearing, I kept cancelling it, and every placement after that landed on the
old canvas instead of a new one.

文件 → 打开 (`Alt+F`, `o`) keeps the previous text in the file name box and appends to it,
which produces 文件名无效. Press `Ctrl+A` first, or skip the dialog entirely:

```
Start-Process ISIS.EXE -ArgumentList '"C:\...\Design.DSN"'
```

When you open a design that way, check that it actually loaded before doing anything else. The
title bar gains the design's file name: `base2 - ISIS Professional` means loaded, plain
`ISIS Professional` means it did not, and a `(未响应)` suffix means it crashed. A design ISIS
will not load fails either silently or with a small dialog that has the same title as the main
window, so the title bar is the cheap check.

## Wires

Click a pin to start a wire, click the destination pin to finish. Pins are at the ends of the
lead lines, which `region_ascii.py` will show you. Click a few pixels off and you select the
part instead; if the symbol goes solid, you hit the body rather than the pin. Afterwards,
compile the netlist or check with a capture that both ends show a connection dot.

The snapping is forgiving enough to script against. Measured: a click 0.03 inch - three pixels
at 100 px/in - off both axes still connected, and the wire ISIS wrote has its endpoints exactly
on the pins, `(0.700, 0.800)` and `(0.700, -0.300)`. So a script does not need exact pin
coordinates, only the right neighbourhood, and the result is verifiable without looking at the
screen: parse the saved design and check where the wire's endpoints ended up.

`scripts/dsn_pins.py` lists the candidates for a part: it takes the endpoints of the wires
around each component and reports them as offsets from the component's anchor. Points shared by
two instances of the same part are its pins; the rest are wire bends. Wire a part once by hand,
read the offsets, and you can place and wire more copies of it by script.

The offsets belong to the *record*, not to the part name. A record carries the instance's
orientation, and a clone keeps it, so offsets measured on one instance transfer to every clone
of that same record. They do not transfer to instances that were placed separately - measured
once: a NAND record lifted from a design with no wires, placed at a new position, did not
connect at the pin offset that another NAND in the base design uses. That is why the donor
sheet approach works and guessing does not: place one instance per part type with the record you
intend to clone, wire it once, and measure.

## Sample designs, which are the fastest way to a waveform

Under `SAMPLES\` in the install directory:

`Generator Scripts\` has Sine Wave, Triangle Wave, Noise Generator, Piecewise Linear Waveform,
Serial Data Generator, SPI Memory Stimulus and QPSK Modulation. They are pre-wired, so running
one gets you a real curve on screen in a couple of minutes. `Graph Based Simulation\` has
Fourier, Mixed, Transfer, Sweep, Lpf, 741noise, Resistor, Diode, Vco, Zin and Zout, named
after the analysis they demonstrate. `Interactive Simulation\Animated Circuits\` puts every
virtual instrument on one sheet. `HELP\` has the manuals: ISIS.chm, LISA.chm for the analysis
types, Instruments.chm for the virtual instruments.

These files are also where you find example instances of parts if you are generating designs
by writing `.DSN` files - see [dsn-generate.md](dsn-generate.md).

## Driving it without fighting it

Activate the ISIS window before any Computer Use capture. Otherwise the Codex or ChatGPT
window is composited into the same screen region and you end up reading chat text as if it
were a dialog.

Extra screenshot regions reported for the ISIS window are usually other windows rather than
dialogs. OCR them before acting on them.

Switch to an English keyboard layout before sending single-letter accelerators. A Chinese IME
swallows them.

Editing a `.DSN` is a good way to read a design, and it works for changes that keep every
record the same size - moving a part, renaming it to an equally long name. Adding objects that
way does not work on 7.08 SP2; see [dsn-generate.md](dsn-generate.md) for the tests. Building a
schematic means driving the GUI, and the saved design is then the evidence trail: a saved
design tells you what is really there, where a screenshot only tells you what was drawn.
