# windows-gui-vision

Notes and small tools for driving a Windows GUI from an agent that cannot see images.

I put this together while filling in a lab report that wanted a screenshot per item out of
Proteus ISIS. The agent had no image input, screen captures kept grabbing whatever window
was floating on top, and a good half of my clicks were landing on nothing at all. What is
in here is what actually worked, together with the mistakes that cost me the most time.

## The loop it is built around

capture the right pixels -> read them -> act -> prove the action landed

Capture. `PrintWindow` gets a window's own pixels, so occluding windows and the mouse cursor
never appear and the target does not need focus. It works for GDI apps such as Proteus 7 and
returns an all-black bitmap for GPU-composited clients. There is a foreground screen grab for
that case, plus scripts that tell you which window you are looking at.

Read. A vision model for "what is this thing", Windows OCR for exact text with bounding
boxes, and a handful of numpy scripts for anything that has to be measured rather than
described: blob geometry, colour masks, ink profiles, before/after diffs.

Act. Keyboard first, accessibility indexes second, coordinates last. The coordinate case is
handled by working in the application's own logical pixel grid and multiplying by a measured
scale factor, so the same anchors survive a different monitor or DPI setting.

Prove it. Every canvas action commits silently. Diff two captures, or check for the ink you
expected to appear. A click that returns success has told you nothing.

## Quick start

```bash
python scripts/verify_env.py                        # interpreter, deps, key, OCR, smoke test
powershell -File scripts/wins.ps1 -Filter '*ISIS*'   # window handles, rects, titles
powershell -File scripts/capture_window.ps1 -OutPath shot.png -ProcessId <pid>
python scripts/calibrate.py --print shot.png --out calib.json
python scripts/see.py shot.png "which list row is selected?"
```

The only thing that needs a network connection and an API key is `see.py`. OCR and all the
pixel tools run locally.

## Install as a Codex skill

Copy the folder to `%USERPROFILE%\.codex\skills\windows-gui-vision`, or point
`skill-installer` at this repository. `SKILL.md` is the entry point an agent reads; the
`references/` files are the detail it pulls in when it needs it.

## Contents

| Path | What it is |
| --- | --- |
| `SKILL.md` | the entry point: the loop, tool selection, rules of thumb |
| `references/capture.md` | PrintWindow vs screen capture, occlusion, cursor, DPI, black captures |
| `references/vision.md` | using a vision model, and where it lies to you |
| `references/pixels.md` | the measurement scripts and when to reach for each |
| `references/calibration.md` | logical pixels, scale factors, `calibrate.py`, `layout.py` |
| `references/interaction.md` | clicking, typing, IME trouble, modal dialogs, canvas placement |
| `references/coords.md` | the pointer readout, and turning a design coordinate into a screen pixel |
| `references/docx-report.md` | turning captures into figures inside a Word document |
| `references/proteus.md` | Proteus ISIS/ARES specifics, measured on a real install |
| `references/dsn-format.md`, `references/dsn-generate.md` | editing Proteus `.DSN` files directly |
| `references/dsn-append.md` | adding a component to a design from a script, verified, and what is still missing |
| `references/dsn-templates.md` | lifting part records out of existing designs into a json library |
| `references/dsn-wires.md` | adding a wire by script: the tail block, the link fields, and the verified recipe |
| `scripts/` | 26 helpers: capture, OCR, vision, pixels, calibration, layout, input, self-checks, `.DSN` reading, appending, wiring, pin lookup and load checks |

Everything under `scripts/` is command line and prints plain text or json, so it composes in
shell loops. `SKILL.md` and the reference files are what an agent reads; you can read them too.

## Things it does not solve

- GPU-composited windows. PrintWindow gives you black; the screen-grab fallback then depends
  on nothing being on top of the window.
- The first calibration for a new app. Detectors find the canvas, an icon column and evenly
  spaced list rows, but naming which button is which is still a one-time manual pass.
- Vision accuracy. It is fine at "what is this" and unreliable at coordinates, small text and
  anything that sounds like an inventory. The docs say which questions to avoid.
- Locating two link fields per generated wire. Components and wires can both be written by
  script now, but a new wire needs two 2-byte fields elsewhere in the design pointed at it, and
  their meaning is not pinned down yet, so they have to be found by measuring one hand-drawn
  wire first. Everything else about a generated wire is automatic - see
  `references/dsn-wires.md`.
- Creating a part from a script. An appended part loads and keeps its reference designator, but
  no symbol is drawn and it has no pins, so it cannot be wired into anything - including when
  the record comes from the same design. `references/dsn-append.md` has the recipe and the
  three measurements that show exactly where it stops, and the ink subtraction that catches it.

## License

MIT. See `LICENSE`.
