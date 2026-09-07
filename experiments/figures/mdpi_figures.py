"""
mdpi_figures.py - audit and repair raster figures against MDPI requirements.

WHY THIS EXISTS
---------------
MDPI states two thresholds, and they are not the same thing:

  * Instructions for Authors (binding minimum): at least 1000 pixels in
    width/height, OR 300 dpi or higher.
  * Editorial checklist (recommended): preferably not less than 600 dpi,
    RGB 8-bit per channel, supplied as PNG / JPEG / TIFF.

"dpi" is meaningless without a print width. A 2160 px figure is 300 dpi at
7.2 in and 343 dpi at 6.3 in. This tool therefore always reports dpi AS
PRINTED, computed against a declared target width, and never against the
number a program happened to write into the file header.

THE TRAP THIS TOOL IS REALLY FOR
--------------------------------
Word places an image using the pHYs chunk embedded in the PNG. If that chunk
is missing, Word assumes 96 dpi and drops a 3780 px figure in at 100 cm; the
author then drags it down to fit the column. Dragging changes the print size
but NOT the drawn point sizes, so an 8 pt annotation silently prints at 5 pt.
Stamping the right pHYs makes the figure land at exactly the intended width,
which is the only way the point sizes chosen in the plotting script survive.

MODES
-----
  audit <path>            report every raster figure in a file or folder
  stamp <path> [--apply]  rewrite pHYs so the figure lands at --width-cm

Resampling is deliberately NOT offered. Upscaling a 1400 px plot to 3800 px
adds pixels, not resolution, and a reviewer opening the file sees blurred
type. Under-resolution is fixed by regenerating from the source script at a
higher dpi, never by interpolation.

Usage:
    python mdpi_figures.py audit  .
    python mdpi_figures.py stamp  . --width-cm 16 --apply
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from PIL import Image

CM_PER_INCH = 2.54

# MDPI thresholds.
MIN_PIXELS_EITHER_SIDE = 1000      # Instructions for Authors
MIN_DPI_AT_PRINT_SIZE = 300        # Instructions for Authors
RECOMMENDED_DPI = 600              # editorial checklist
ACCEPTED_SUFFIXES = {".png", ".tif", ".tiff", ".jpg", ".jpeg"}

# MDPI A4 template: the text block is ~16 cm; 17.5 cm is the absolute
# full-bleed maximum. 16 cm is the safe default for a body figure.
DEFAULT_WIDTH_CM = 16.0
MAX_HEIGHT_CM = 22.0

# Smallest type that survives MDPI typesetting. Tables are capped at 8 pt by
# the Instructions for Authors; figure text should not go below it either.
MIN_FONT_PT = 8.0


def collect(target: pathlib.Path) -> list[pathlib.Path]:
    if target.is_file():
        return [target]
    return sorted(
        path for path in target.iterdir()
        if path.suffix.lower() in ACCEPTED_SUFFIXES
    )


def embedded_dpi(image: Image.Image) -> float | None:
    """The dpi Word will believe. None means no pHYs chunk -> Word assumes 96."""
    dpi = image.info.get("dpi")
    if not dpi:
        return None
    value = float(dpi[0])
    # Pillow reports 1 dpi for files whose pHYs unit is 'unknown'.
    return value if value > 1 else None


def inspect(path: pathlib.Path, width_cm: float) -> dict:
    with Image.open(path) as image:
        width_px, height_px = image.size
        mode = image.mode
        declared = embedded_dpi(image)

    target_width_in = width_cm / CM_PER_INCH
    printed_dpi = width_px / target_width_in
    printed_height_cm = height_px / printed_dpi * CM_PER_INCH

    # What Word does today, with whatever metadata the file currently carries.
    assumed = declared if declared else 96.0
    word_width_cm = width_px / assumed * CM_PER_INCH

    problems: list[str] = []
    if min(width_px, height_px) < MIN_PIXELS_EITHER_SIDE and printed_dpi < MIN_DPI_AT_PRINT_SIZE:
        problems.append(
            f"FAILS the MDPI minimum: {width_px}x{height_px} px is under 1000 px "
            f"and only {printed_dpi:.0f} dpi at {width_cm:.1f} cm"
        )
    elif printed_dpi < RECOMMENDED_DPI - 1:
        problems.append(
            f"meets the minimum but not the 600 dpi recommendation "
            f"({printed_dpi:.0f} dpi at {width_cm:.1f} cm) - regenerate from source"
        )
    if declared is None:
        problems.append("no pHYs chunk: Word will insert this at 96 dpi and you will rescale by hand")
    elif abs(word_width_cm - width_cm) > 0.25:
        problems.append(
            f"pHYs says {declared:.0f} dpi, so Word inserts it at {word_width_cm:.1f} cm, "
            f"not {width_cm:.1f} cm - point sizes will not print as drawn"
        )
    if mode not in {"RGB", "L"}:
        problems.append(f"colour mode is {mode}; MDPI wants RGB 8-bit per channel (no alpha)")
    if printed_height_cm > MAX_HEIGHT_CM:
        problems.append(f"prints {printed_height_cm:.1f} cm tall - over the {MAX_HEIGHT_CM:.0f} cm page limit")

    return {
        "path": path,
        "width_px": width_px,
        "height_px": height_px,
        "mode": mode,
        "declared_dpi": declared,
        "printed_dpi": printed_dpi,
        "printed_height_cm": printed_height_cm,
        "word_width_cm": word_width_cm,
        "problems": problems,
    }


def report(results: list[dict], width_cm: float) -> int:
    failures = 0
    print(f"\nMDPI figure audit - target print width {width_cm:.1f} cm")
    print("=" * 78)
    for item in results:
        status = "OK" if not item["problems"] else "CHECK"
        declared = f"{item['declared_dpi']:.0f}" if item["declared_dpi"] else "none"
        print(f"\n[{status}] {item['path'].name}")
        print(f"       {item['width_px']} x {item['height_px']} px, {item['mode']}, pHYs={declared} dpi")
        print(f"       prints at {item['printed_dpi']:.0f} dpi / {item['printed_height_cm']:.1f} cm tall")
        for problem in item["problems"]:
            print(f"       - {problem}")
        if item["problems"]:
            failures += 1
    print("\n" + "=" * 78)
    print(f"{len(results) - failures}/{len(results)} clean")
    print(
        "Reminder: dpi is not legibility. Check that the smallest type in each "
        f"figure is >= {MIN_FONT_PT:.0f} pt AT {width_cm:.1f} cm, not in the source script."
    )
    return failures


def stamp(results: list[dict], width_cm: float, apply: bool) -> None:
    target_width_in = width_cm / CM_PER_INCH
    for item in results:
        dpi = item["width_px"] / target_width_in
        if dpi < MIN_DPI_AT_PRINT_SIZE:
            print(f"SKIP  {item['path'].name}: would be {dpi:.0f} dpi - regenerate, do not stamp")
            continue
        if not apply:
            print(f"WOULD {item['path'].name}: pHYs -> {dpi:.0f} dpi (lands at {width_cm:.1f} cm)")
            continue
        source = item["path"]
        backup = source.with_suffix(source.suffix + ".bak")
        if not backup.exists():
            backup.write_bytes(source.read_bytes())
        with Image.open(backup) as original:
            flattened = original.convert("RGB")
            flattened.save(source, dpi=(dpi, dpi))
        print(f"OK    {source.name}: pHYs -> {dpi:.0f} dpi, backup {backup.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["audit", "stamp"])
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--width-cm", type=float, default=DEFAULT_WIDTH_CM)
    parser.add_argument("--apply", action="store_true", help="stamp mode: actually write")
    args = parser.parse_args()

    if not args.path.exists():
        sys.exit(f"{args.path} does not exist.")

    files = collect(args.path)
    if not files:
        sys.exit(f"No raster figures found in {args.path}.")

    results = [inspect(path, args.width_cm) for path in files]

    if args.mode == "audit":
        return 1 if report(results, args.width_cm) else 0

    report(results, args.width_cm)
    print()
    stamp(results, args.width_cm, args.apply)
    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
