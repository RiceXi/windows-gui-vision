# Turning captures into figures in a document

The request I built this part for: "fill this report template with one screenshot per item
and a short note". The GUI work is the easy half. Keeping the document consistent, and being
able to prove each figure is right, is the rest.

## Order of work

Capture every canvas once, named after its state. Locate the objects in each capture with
`clusters.py` or `colorfind.py`, or from the placement log if you were driving the GUI
yourself. Crop with one recipe per class of object, so the figures match each other. Check
every crop with `edgecheck.py` and re-crop the failures. Only then write them into the
document. Finally audit the result: count the images, check one figure per required item, and
confirm the captions line up.

## python-docx, without wrecking the template

The template knows its own styles; reuse them instead of inventing paragraph formats, and
insert relative to existing paragraphs rather than appending and hoping.

```python
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

doc = Document(TEMPLATE)

def note_after(anchor, text, size=10.5):
    p = doc.add_paragraph()
    f = p.paragraph_format
    f.line_spacing = 1.5
    f.space_before = Pt(0)
    f.space_after = Pt(0)
    f.first_line_indent = Pt(size * 2)
    r = p.add_run(text)
    r.font.size = Pt(size)
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    anchor._p.addnext(p._p)
    return p

def picture(path, width_cm):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Cm(width_cm))
    return p
```

`anchor._p.addnext(new._p)` is the reliable insert. For a sequence, walk the chain as you go.
To replace a placeholder image that is already in the template, find the paragraph whose
`a:blip` points at the media part you want to swap, delete its `w:r` children, and add the new
picture into the same paragraph - that keeps the alignment and spacing the template author
chose.

## Checking the document afterwards

```python
import docx, io, os
from PIL import Image

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
doc = docx.Document("out.docx")
for i, p in enumerate(doc.paragraphs):
    blip = p._p.find(".//" + A + "blip")
    if blip is None:
        continue
    part = doc.part.rels[blip.get(R + "embed")].target_part
    print(i, os.path.basename(str(part.partname)), Image.open(io.BytesIO(part.blob)).size)
```

Then export a PDF and render a few pages (`pdftoppm -png -r 90 -f 40 -l 41 in.pdf out`). Look
at them, or ask `see.py` about a montage. What you are looking for: the figure is there at
all, nothing is cut off, no cursor or stray window got into it, and the caption matches the
picture.

## Traps from doing this for real

Word holds the output file open while the user has it open, and saving over it raises
`PermissionError`. Write somewhere else and say so; do not quietly leave the old content in
place.

Some templates draw each paragraph's text two or three times - outline plus fill in separate
runs - so `itertext()` returns the text repeated. Compare once per paragraph, and do not
"fix" the duplication, because it is what makes the heading look like a heading.

python-docx sets the Latin font only. If you are writing Chinese or Japanese text, set
`w:eastAsia` on the run or the characters fall back to a different typeface halfway through a
sentence.

A4 with 3 cm margins fits about 15 cm of figure. Pick one width per class of figure so the
captions line up, and keep enough pixels that the width stays above roughly 130 dpi.

Keep the sources. Raw captures, the crop recipe as a small script, and the calibration json
belong next to the deliverable in a working folder, not inside it.
