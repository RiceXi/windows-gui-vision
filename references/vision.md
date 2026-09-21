# Asking a model to read a screenshot

```
python scripts/see.py shot.png "which row of the list is highlighted?"
python scripts/see.py shot.png "read the dialog title" --crop 0,0,900,60 --scale 2
python scripts/see.py shot.png "is a wire drawn between these two pins?" --model deepseek-v4-pro
```

One image and one question go to an OpenAI-compatible `/responses` endpoint, and the answer
comes back as text. It needs `DEEPSEEK_API_KEY`; nothing else in this folder does.

The endpoint matters. With `/chat/completions` the image is dropped without an error and the
model cheerfully tells you it cannot see pictures. Use `/responses`, where the image goes in
as `{"type":"input_image","image_url":"data:image/png;base64,..."}`.

## Where it is worth trusting

Saying what a thing is: "this is a four-channel oscilloscope symbol". Reading large text in a
tight crop. Answering yes/no about something you described precisely. Describing the shape of
a curve or the state of a checkbox.

## Where it is not

Numbers, small text, dense lists. Pixel coordinates - it will produce plausible ones out of
thin air. "List every object in this screenshot" - it invents items, and once it has
invented one it will reason about it. And "is this figure complete", which is the question I
got wrong most often: it mixes up neighbouring panes, crop padding and the cursor.

For any of those, use `ocr.ps1` for text and the scripts in [pixels.md](pixels.md) for
anything with a position or a size.

## Asking so you get something usable

One question per call. Two questions halve the accuracy of both.

Give it a crop rather than the whole screen. A 3x-zoomed 200x120 crop reads far better than a
4K screenshot, and `--crop` plus `--scale` gets you there.

Tell it what to do when it cannot read something: "if the text is unreadable, answer
unreadable". Otherwise it fills the gap with something plausible.

Ask for a transcription rather than a summary, then compare it with `ocr.ps1` on the same
crop. Two independent readers disagreeing is useful information; one confident reader is not.

## Checking an answer

For a claim like "the chart shows a sine wave" or "the symbol is cut off":

Ask again on a tighter crop. If the answer changes, you learned something about the answer.

Or measure it. `colorfind.py --color green --mode rowband` proves a coloured title strip is
there and gives its extent. `clusters.py` measures a symbol. `edgecheck.py` settles whether a
crop cut through content.

Or read the same text with OCR and compare.

Vision answers are hypotheses. Measurements are evidence. When the two disagree, the
measurement wins.
