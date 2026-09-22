# The left mode toolbar, named from the application's own status bar

Isis 7 gives its mode buttons no tooltips, and they are 20 px apart, so clicking "the third one"
from a guess is a coin toss. The names are readable anyway: hovering a button makes Isis write the
tool's name into the status bar, and that text can be read out of a capture.

Method: hover each button, `capture_window.ps1` the window, crop the status bar
(`60,795`-`760,825` on a 1416x832 window), stack the crops into one image and read them with the
vision model (`scripts/see.py`). One reading per button, verified against what the button does.

Measured on this install (screen y, window at (0,20)):

| y (screen) | status bar says | mode |
| --- | --- | --- |
| 110 | 选择模式 | selection |
| 130 | 器件 | device / component |
| 150 | 连接点 | junction dot |
| 170 | 连线标号 | wire label |
| 190 | 文字脚本 | text script |
| 210 | 总线 | bus |
| 230 | 子电路 | subcircuit |
| 250 | 页面间连接端 | inter-sheet terminal |
| 310 | 仿真图表 | simulation graph |

**There is no wire mode in that list**, and that is the point: Isis starts a wire from *any* mode
when the pointer rests on a connection point - the cursor turns into a pencil and the wire follows
it. A hand-drawn wire in this project was made that way (the user's words: "直接鼠标置于上方就会出现
绿色铅笔"). So a script does not have to select a tool before wiring; it has to be *on the pin*.

## What that costs, and the two checks that are worth having

Being on the pin is the whole difficulty, because the window moves between runs (measured (12,10)
one session and (0,20) the next) and the canvas scrolls, so a screen mapping measured earlier is
worthless. Two checks make it findable:

* **the cursor shape.** `PrintWindow` never contains the cursor, but `grab_foreground.ps1` reads
  the composited desktop and does. A capture with the pointer parked on a candidate, read by the
  vision model, answers "pencil or arrow?" - which is exactly "on a connection point or not".
  Used at one candidate this session, it reported a crosshair over empty sheet, which is how that
  candidate was ruled out;
* **the hover marker.** Hovering a connection point makes Isis draw a small marker (~31x16 px at
  this zoom); a part body instead gets a wide highlight (~96x61). Both are visible in a
  `PrintWindow` capture, and their *shapes* tell them apart, so a scan can find candidate pins
  without a vision call at all.

`_re/scratch/wire_search.ps1` (scan + click), `_re/scratch/mode_wire_test.ps1` (per-button test),
`_re/scratch/cursor_state.ps1` (cursor captures) and `_re/scratch/try_wire.ps1` are the tools that
came out of this; they are scratch, not skill scripts, until the recipe is settled.
