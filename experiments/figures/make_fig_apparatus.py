"""
make_fig_apparatus.py - Figure 1, the measurement apparatus, at MDPI print size.

PlantUML's PNG writer has no notion of print size: it emits the diagram at its
natural pixel size and writes no pHYs chunk, so Word inserts it at 96 dpi and
the author rescales by hand. The only deterministic route to a pixel target is
SVG -> rasterise at an exact width:

    plantuml -tsvg  ->  cairosvg --output-width 3780  ->  stamp pHYs 600 dpi

3780 px = 16 cm at 600 dpi.

TYPE SIZE - READ BEFORE CHANGING THE DIAGRAM.
The diagram is 857 x 797 px natively. Printed at 16 cm that puts the action
text (13 px) at 6.88 pt and the guard labels (12 px) at 6.35 pt. Raising
skinparam font sizes does NOT help: PlantUML widens the diagram in proportion,
so at 13 px throughout the smallest type moves by about 0.1 pt. The ratio
font_px / width_px is what fixes the printed size, and only narrowing the
diagram changes it. For 8 pt at 16 cm the diagram must be <= 680 px wide.

Measured alternative, 11.09.2026: shortening the four guards to
[no stable signal] / [all conditions met] / [format unreachable] /
[locator failed], with the full wording moved into the caption, brings the
diagram to 744 px - guards at 7.32 pt and action text at 7.93 pt. That is the
only change that materially improves the type size. It is a content change and
has NOT been applied.

This script therefore passes allow_small_type implicitly: it does not go
through figstyle, because there is no matplotlib figure to inspect. The type
size is a standing, recorded decision, not an oversight.
"""
import pathlib
import re
import shutil
import subprocess
import sys

import cairosvg
from PIL import Image

SOURCE = pathlib.Path("figure_apparatus.puml")
OUTPUT = pathlib.Path("figures/figure_apparatus.png")

TARGET_DPI = 600
WIDTH_CM = 16.0
TARGET_WIDTH_PX = round(WIDTH_CM / 2.54 * TARGET_DPI)   # 3780


GUARD_TEXT = re.compile(
    r'(<text[^>]*font-size="(?P<size>\d+)"[^>]*textLength="(?P<len>[\d.]+)"[^>]*x=")'
    r'(?P<x>[\d.]+)("[^>]*y="(?P<y>[\d.]+)">)(?P<label>\[[^<]*)(</text>)'
)
VERTICAL = re.compile(
    r'<line style="[^"]*" x1="(?P<x1>[\d.]+)" x2="(?P<x2>[\d.]+)" '
    r'y1="(?P<y1>[\d.]+)" y2="(?P<y2>[\d.]+)"/>'
)

CLEARANCE_PX = 6.0


def _verticals(markup: str) -> list[tuple[float, float, float]]:
    out = []
    for m in VERTICAL.finditer(markup):
        x1, x2 = float(m.group("x1")), float(m.group("x2"))
        if abs(x1 - x2) < 0.01:
            y1, y2 = float(m.group("y1")), float(m.group("y2"))
            out.append((x1, min(y1, y2), max(y1, y2)))
    return out


def _guards(markup: str) -> list[dict]:
    out = []
    for m in GUARD_TEXT.finditer(markup):
        size, length = int(m.group("size")), float(m.group("len"))
        x, y = float(m.group("x")), float(m.group("y"))
        out.append({"x0": x, "x1": x + length, "top": y - size,
                    "bottom": y + size * 0.25, "label": m.group("label"),
                    "match": m})
    return out


def crossed_guards(markup: str) -> list[tuple[str, float]]:
    """Guard labels with a connector line drawn through them."""
    lines = _verticals(markup)
    hits = []
    for g in _guards(markup):
        for x, top, bottom in lines:
            if g["x0"] < x < g["x1"] and top < g["bottom"] and bottom > g["top"]:
                hits.append((g["label"], x))
    return hits


def nudge_crossed_guards(markup: str) -> str:
    """Shift a crossed guard label clear of the line that crosses it.

    PlantUML defect, measured 11.09.2026: with an EVEN number of switch
    branches the decision node sits between two columns, so one branch is
    routed through an elbow and that branch's guard is anchored at the node's
    x while the line descends at the column's x - straight through the text.
    Ruled out by measurement, not by eye: padding the guard with spaces (the
    column moves with it, swept 2-38 spaces, never clears), reordering the
    cases (the collision follows the third POSITION, not the wording),
    shortening the guards, widening the decision node, and if/elseif instead of
    switch (same defect, lands on a different guard). Three branches render
    clean; four and five do not.

    So the label is moved here instead, in the generated SVG, just past the
    line. Nothing in the diagram's content changes. The move is asserted not to
    collide with the next guard, and main() asserts no crossings remain.
    """
    guards = _guards(markup)
    lines = _verticals(markup)
    edits = []
    for index, g in enumerate(guards):
        crossing = [x for x, top, bottom in lines
                    if g["x0"] < x < g["x1"] and top < g["bottom"] and bottom > g["top"]]
        if not crossing:
            continue
        shift = max(crossing) + CLEARANCE_PX - g["x0"]
        new_x0, new_x1 = g["x0"] + shift, g["x1"] + shift
        neighbours = [o["x0"] for o in guards if o is not g and o["x0"] > g["x0"]]
        if neighbours:
            assert new_x1 + CLEARANCE_PX < min(neighbours), (
                f"Moving {g['label']!r} clear of the line would run it into the "
                f"next guard. The diagram needs a structural fix, not a nudge."
            )
        edits.append((g["match"], new_x0))

    for match, new_x0 in reversed(edits):
        markup = (markup[:match.start()]
                  + match.group(1) + f"{new_x0:.4f}" + match.group(5)
                  + match.group("label") + match.group(8)
                  + markup[match.end():])
    return markup


def plantuml_command() -> list[str]:
    """Prefer a plantuml on PATH; fall back to a plantuml.jar beside this script."""
    if shutil.which("plantuml"):
        return ["plantuml"]
    jar = pathlib.Path(__file__).with_name("plantuml.jar")
    if jar.exists():
        return ["java", "-jar", str(jar)]
    sys.exit(
        "PlantUML not found. Put plantuml.jar next to this script, or install "
        "plantuml on PATH. Graphviz (dot) is required by PlantUML for activity "
        "diagrams."
    )


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    svg = SOURCE.with_suffix(".svg")

    subprocess.run(plantuml_command() + ["-tsvg", str(SOURCE)], check=True)
    assert svg.exists(), f"PlantUML did not write {svg}."

    # PlantUML names the output after the @startuml identifier, not the input
    # filename. Confirm we are rasterising what we think we are.
    markup = svg.read_text(encoding="utf-8")
    match = re.search(r'viewBox="0 0 (\d+) (\d+)"', markup)
    assert match, "No viewBox in the SVG - cannot verify the native size."
    native_width, native_height = int(match.group(1)), int(match.group(2))

    before = crossed_guards(markup)
    markup = nudge_crossed_guards(markup)
    remaining = crossed_guards(markup)
    assert not remaining, f"Guard labels still crossed by a connector: {remaining}"
    if before:
        print(f"  moved {len(before)} guard label(s) clear of a connector: "
              + ", ".join(repr(label) for label, _ in before))
    svg.write_text(markup, encoding="utf-8")

    cairosvg.svg2png(
        url=str(svg),
        write_to=str(OUTPUT),
        output_width=TARGET_WIDTH_PX,
        background_color="white",
    )

    with Image.open(OUTPUT) as raster:
        flattened = raster.convert("RGB")
        width_px, height_px = flattened.size
        flattened.save(OUTPUT, dpi=(TARGET_DPI, TARGET_DPI))

    height_cm = native_height / native_width * WIDTH_CM
    assert height_cm <= 22.0, f"Figure prints {height_cm:.1f} cm tall, over the page."

    smallest_pt = 12 / native_width * (WIDTH_CM / 2.54) * 72
    print(
        f"Wrote {OUTPUT} - {width_px}x{height_px} px, {TARGET_DPI} dpi, RGB, "
        f"prints {WIDTH_CM:.0f} x {height_cm:.1f} cm"
    )
    print(
        f"  native {native_width}x{native_height} px; smallest type (12 px guards) "
        f"prints at {smallest_pt:.2f} pt - below the 8 pt house rule, by decision"
    )


if __name__ == "__main__":
    main()
