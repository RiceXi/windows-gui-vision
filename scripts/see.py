#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Image -> text for a model that cannot see pictures.

    python see.py shot.png "what is selected in this list?"
    python see.py shot.png "read the title bar" --crop 0,0,900,60 --scale 3
    python see.py shot.png "..." --model deepseek-v4-pro --json

Environment
    DEEPSEEK_API_KEY   required
    SEE_BASE_URL       default https://api.deepseek.com/responses
    SEE_MODEL          default deepseek-v4-flash (use -pro for hard readings)

The /responses endpoint takes {"type":"input_image","image_url":"data:image/png;base64,..."}.
The /chat/completions endpoint silently drops the image, so never switch to it.
"""
import argparse
import base64
import io
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = os.environ.get("SEE_BASE_URL", "https://api.deepseek.com/responses")
DEFAULT_MODEL = os.environ.get("SEE_MODEL", "deepseek-v4-flash")


def load_image(path, crop=None, scale=1.0, max_w=1400):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                       Image.LANCZOS)
    if im.width > max_w:
        im = im.resize((max_w, max(1, int(im.height * max_w / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode(), im.size


def ask(path, question, crop=None, scale=1.0, model=None, timeout=180):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise SystemExit("DEEPSEEK_API_KEY is not set")
    b64, size = load_image(path, crop, scale)
    prompt = ("[image is %d x %d px, origin top-left, answer with pixel coordinates] %s"
              % (size[0], size[1], question))
    payload = {
        "model": model or DEFAULT_MODEL,
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": "data:image/png;base64," + b64},
        ]}],
    }
    req = urllib.request.Request(
        DEFAULT_BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit("HTTP %s from %s: %s" % (exc.code, DEFAULT_BASE, body))
    except urllib.error.URLError as exc:
        raise SystemExit("cannot reach %s (%s). If you are sandboxed, allow network access."
                         % (DEFAULT_BASE, exc.reason))
    texts = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    texts.append(c.get("text", ""))
    return "\n".join(texts).strip(), size, data.get("usage", {}), data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("question", nargs="*", default=[])
    ap.add_argument("--crop", default=None, help="x0,y0,x1,y1 - ask about a tight area")
    ap.add_argument("--scale", type=float, default=1.0, help="zoom before sending")
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None
    question = " ".join(args.question) or "Describe this image in detail."
    text, size, usage, raw = ask(args.image, question, crop, args.scale, args.model, args.timeout)
    if args.json:
        print(json.dumps({"image": args.image, "sent_size": list(size), "answer": text,
                          "usage": usage}, ensure_ascii=False, indent=1))
    else:
        print("[%s -> %s, tokens %s]" % (os.path.basename(args.image), size,
                                         usage.get("total_tokens")))
        print(text or "(empty response)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
