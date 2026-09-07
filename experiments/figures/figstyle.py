"""
figstyle.py - the single place where Paper 1 figures are sized and written.

The rule this module enforces: a figure is authored at its PRINT size. The
figsize passed to plt.subplots is the width the figure will occupy in the
typeset paper, in inches, and nothing rescales it afterwards. That is what
makes a font size chosen in the script (8 pt) the font size that appears on
the page (8 pt). Drawing at 7.2 in and letting Word shrink the image to
16 cm silently reduces every label by 12.5 percent.

save_mdpi() does the three things savefig alone gets wrong:

  1. flattens RGBA to RGB - matplotlib writes an alpha channel even when
     facecolor is white, and MDPI asks for RGB 8-bit per channel;
  2. stamps the pHYs chunk so Word inserts the image at exactly WIDTH_CM
     instead of guessing 96 dpi;
  3. refuses to write a figure whose smallest type falls below MIN_FONT_PT,
     because that is the failure a dpi check cannot see.

Import it from make_figure2.py / make_figure3.py:

    from figstyle import WIDTH_IN, save_mdpi
    figure, axes = plt.subplots(figsize=(WIDTH_IN, 3.9))
    ...
    save_mdpi(figure, destination)
"""
from __future__ import annotations

import pathlib

import matplotlib.text
from PIL import Image

CM_PER_INCH = 2.54

WIDTH_CM = 16.0                    # MDPI A4 body text block
WIDTH_IN = WIDTH_CM / CM_PER_INCH  # 6.299 in
MAX_HEIGHT_CM = 22.0
TARGET_DPI = 600                   # MDPI editorial recommendation
MIN_FONT_PT = 8.0                  # MDPI floor for typeset text


def smallest_font_pt(figure) -> tuple[float, str]:
    """The smallest rendered type in the figure, and the string that carries it."""
    smallest, carrier = float("inf"), ""
    for artist in figure.findobj(matplotlib.text.Text):
        label = artist.get_text()
        if not label.strip():
            continue
        size = float(artist.get_fontsize())
        if size < smallest:
            smallest, carrier = size, label
    return smallest, carrier


def save_mdpi(figure, destination: pathlib.Path, dpi: int = TARGET_DPI,
              allow_small_type: bool = False) -> None:
    destination = pathlib.Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    width_in, height_in = figure.get_size_inches()
    assert abs(width_in - WIDTH_IN) < 0.02, (
        f"Figure is {width_in:.2f} in wide but the MDPI text block is "
        f"{WIDTH_IN:.2f} in ({WIDTH_CM:.0f} cm). Author at print size - do not "
        "let Word do the scaling."
    )
    height_cm = height_in * CM_PER_INCH
    assert height_cm <= MAX_HEIGHT_CM, (
        f"Figure prints {height_cm:.1f} cm tall, over the {MAX_HEIGHT_CM:.0f} cm page limit."
    )

    size_pt, carrier = smallest_font_pt(figure)
    if size_pt < MIN_FONT_PT and not allow_small_type:
        raise AssertionError(
            f"Smallest type is {size_pt:.1f} pt (on {carrier!r}), below the "
            f"{MIN_FONT_PT:.0f} pt MDPI floor. Raise the font size or reduce the "
            "number of labels - do not ship it and hope the typesetter misses it."
        )

    figure.savefig(destination, dpi=dpi, facecolor="white")

    with Image.open(destination) as raster:
        flattened = raster.convert("RGB")
        width_px, height_px = flattened.size
        flattened.save(destination, dpi=(dpi, dpi))

    print(
        f"Wrote {destination} - {width_px}x{height_px} px, {dpi} dpi, RGB, "
        f"prints {WIDTH_CM:.0f} x {height_cm:.1f} cm, smallest type {size_pt:.1f} pt"
    )
