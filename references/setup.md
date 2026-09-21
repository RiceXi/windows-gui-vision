# Setting it up, and moving it to another machine

The folder is self-contained. Nothing in the scripts refers to a particular machine, project
or screen resolution, so copying it is the whole install.

## What has to be there

Python 3.8 or newer, with `pillow` and `numpy`. `python-docx` as well if you are going to fill
in a Word document. Windows PowerShell 5.1 - the `powershell.exe` that ships with Windows -
because `ocr.ps1` uses WinRT types that PowerShell 7 cannot load.

A key for the vision endpoint, only if you want `see.py`. Everything else works offline:
OCR is local, the rest is arithmetic on pixels.

```
pip install pillow numpy python-docx
setx DEEPSEEK_API_KEY <key>
```

Windows OCR needs the language pack for whatever you are reading. `-Lang zh-Hans-CN` is the
default in `ocr.ps1`; pass `-Lang en-US` for English interfaces.

## Environment variables

| variable | default | what it does |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | none | bearer token for `see.py` |
| `SEE_BASE_URL` | `https://api.deepseek.com/responses` | any OpenAI-compatible `/responses` endpoint |
| `SEE_MODEL` | `deepseek-v4-flash` | use a larger model when a reading matters |

The endpoint has to be `/responses`. On `/chat/completions` the image is dropped silently and
you get an answer that it cannot see the picture.

## Check the machine

```
python scripts/verify_env.py
```

One line per requirement, then it runs `region_ascii.py` and `edgecheck.py` against a
synthetic image so you know the pixel tooling works rather than merely existing. Non-zero exit
if something is missing.

## Permissions

Capturing another process's window, and injecting input, both need a normal interactive
session. A sandboxed command runner often cannot enumerate windows at all: if `wins.ps1`
lists nothing while the app is plainly open on screen, run it outside the sandbox.

`capture_window.ps1` and `grab_foreground.ps1` only read. `see.py` sends one image to a model;
`ocr.ps1` stays local. Nothing else leaves the machine.

## First hour with a new application

1. `wins.ps1 -Filter '*App*'`, then maximize the window.
2. `capture_window.ps1`, and check the ink. A near-black mean means the client area is
   composited, so switch to `grab_foreground.ps1`.
3. `calibrate.py --print shot.png --out calib.json` and look at the canvas rectangle, the icon
   column and the list pitch.
4. `selftest_scaling.py shot.png` to confirm those measurements scale with the image, which is
   what makes them portable.
5. Label the handful of widgets you actually need with `layout.py set`, and keep that json
   next to your project rather than inside this folder.

## Copying to a second machine

Copy the folder, install the packages, set the key if you want vision, run `verify_env.py`
until it says ready. Then capture and calibrate once on the new display. The logical-pixel
numbers should match what the old machine reported; if they do, any `layout.json` you already
made is still valid there, and you never have to touch the coordinates again.
