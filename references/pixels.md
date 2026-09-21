# Measuring instead of asking

Every script here takes an image and a region `x0,y0,x1,y1`, with `-1` for the whole image,
and prints text or json. That means they compose in a shell loop and their output can be
diffed, which is the point: these are the tools that tell you facts.

## clusters.py

Connected blobs of one colour class, with centre and bounding box. This is the one I reach
for most: which list row did the click land on, how big is this symbol, is there a second
object hiding behind the first.

```
python clusters.py shot.png 42,185,160,520 --dark 200 --min-px 8
python clusters.py shot.png 300,150,2600,1600 --color blue --min-px 30
python clusters.py shot.png -1 --rgb 0,0,192 --tol 80 --json
```

`--dark N` is the usual choice for text and line art. `--color` takes `blue, green, red,
magenta, yellow, any`. Raise `--min-px` to skip text, drop it to find small controls.

## colorfind.py

For a coloured strip - a graph window's title bar, a tab header, a highlighted row. `rowband`
mode reports which row, and how far the colour runs along it, which is the quickest way to
find the top edge of a chart:

```
python colorfind.py shot.png 0,0,2800,1650 --color green --mode rowband --min-width 300
python colorfind.py shot.png 300,150,2600,1600 --rgb 0,0,192 --tol 80 --min-px 25
```

## region_ascii.py

Prints ink statistics, the ink bounding box, long horizontal and vertical runs, and an ASCII
picture of the area. This is how I look at a symbol's outline, find where a pin ends, confirm
a wire exists, or check that a region is empty - without needing to see anything.

```
python region_ascii.py shot.png 400,600,900,720 --thresh 150 --block 3
```

Keep the region under about 500x400 and use `--block 4` or larger. It is meant to be read, not
stored.

## edgecheck.py

Run this on every crop before it goes into a document.

```
python edgecheck.py crops/*.png --thresh 150 --band 3 --allow 40
```

It counts dark pixels in the outermost band. Anything non-zero means content is touching the
edge, which usually means you cut through it. Set `--thresh` just under the background
luminance so grid dots and light borders do not set it off.

## diffshots.py

```
python diffshots.py before.png after.png --region 300,170,2560,1570 -o heat.png
```

Changed pixel count, where the change is, and the busiest rows and columns. Changes confined
to a side panel or the status bar mean the document itself did not change - the classic case
where the click succeeded and nothing happened. Exit status is non-zero when there is no
change at all, so it works in a shell `if`.

## crop.py

```
python crop.py canvas.png out/ --box 350,190,1300,850 --box 1700,190,2550,850 --prefix fig
python crop.py canvas.png out/ --center 700,380 --half 300x240 --trim --dark 160 --pad 40 --scale 1.7
```

`--trim` shrinks a rough box down to the ink and `--pad` gives it breathing room, which is
what turns "a box somewhere near the object" into a deliberate figure. `--clamp-right` and
`--clamp-bottom` stop a crop from swallowing a neighbouring pane or a scrollbar. When one
canvas holds several objects, fixed boxes beat auto-trim: uniform figures look better on a
page.

## montage.py

```
python montage.py all.png crops/*.png --grid 3 --scale 0.6 --labels
python scripts/see.py all.png "for each tile, read the title bar; answer as tile=text"
```

File names are burned into the tiles, so answers stay attributable to the right crop. One
question about nine tiles is cheaper and often more reliable than nine questions.

## ruler.py

```
python ruler.py shot.png 0,150,70,1500 -o toolbar.png --scale 4 --step 50
```

Zooms a strip and draws a labelled ruler in the original image's coordinates. Useful when you
need a position from a vision model, or when you just want to read one off by eye.
