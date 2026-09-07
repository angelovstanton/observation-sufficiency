# experiments/figures/ — figure generators (MDPI-ready)

Everything here is generated; nothing under `figures/` is hand-edited. The only
command:

```
cd experiments/figures
python build_all.py
```

Exit 0 means every figure was rendered in this run and passes the audit.
`build_all.py` clears `figures/*.png` first, so a failed render can't leave a
stale image behind unnoticed.

## Files

| File | What it is |
|---|---|
| `build_all.py` | runs the three renderers below, then the audit |
| `make_fig_apparatus.py` | apparatus diagram: PlantUML → SVG → 3780 px PNG |
| `figure_apparatus.puml` | source of the apparatus diagram (see PlantUML note below) |
| `make_fig_pareto.py` | cost/success Pareto surface, all 21 cells |
| `make_fig_per_page.py` | per-page grounding-success delta, all 24 pages |
| `figstyle.py` | print-size and type-size enforcement; the only place figures are written |
| `mdpi_figures.py` | audit + pHYs stamp (dpi-as-printed, not dpi-in-header) |
| `figures/*.png` | the rendered output |

## What the figures are built from

The two data figures read this repo's own exports, not hand-made CSVs:

- `experiments/results/computed/pareto_21cells.csv` — 21 cells
- `experiments/results/computed/thesis_per_page.csv` — 24 pages

Tripwires that must hold, asserted before anything is drawn:

- per-page split **18 positive / 4 tied / 2 negative**, corpus mean **+9.48 pp**;
- frontier recomputed independently from tokens and success, then asserted to
  equal the pipeline's `pareto_status` column — **4 frontier, 17 dominated**.

## External requirements

- `matplotlib`, `pandas`, `pillow`, `cairosvg` (Python — see
  `experiments/analysis/requirements.txt`).
- **PlantUML 1.2026.8 or newer**, for the apparatus diagram only: either
  `plantuml` on `PATH`, or a `plantuml.jar` dropped next to
  `make_fig_apparatus.py` (not shipped in this repo).
- **Graphviz** (`dot` on `PATH`) — PlantUML needs it for activity diagrams.

Tested with: PlantUML 1.2026.8, Graphviz 13.1.1, cairosvg 2.9.1, OpenJDK
11.0.16.1 (Microsoft build).

Without PlantUML/Graphviz, `make_fig_apparatus.py` fails with a clear error
naming what's missing; the two data figures (Pareto, per-page) don't need
either and can be regenerated independently — confirmed by running both
directly against the shipped CSVs.

`figures/figure_apparatus.png` is the exact image used in the paper, rendered
at 16 cm / 600 dpi. Regenerating it with a different PlantUML version may
produce different text wrapping in the labels, without changing the
diagram's content — see the comment above the two affected actions in
`figure_apparatus.puml`.

## Output specification

All three: **3780 px wide, 600 dpi, RGB, pHYs stamped, prints at 16.0 cm.**
Insert in Word at 16.0 cm and **do not drag to resize** — dragging changes the
print size but not the drawn point sizes.

| Figure | Pixels | Printed | Smallest type |
|---|---|---|---|
| apparatus | 3780 × 3612 | 16.0 × 15.3 cm | 6.53 pt |
| Pareto | 3779 × 2400 | 16.0 × 10.2 cm | 8.0 pt |
| per-page | 3779 × 2160 | 16.0 × 9.1 cm | 8.0 pt |

## Naming

Files are named by content (`apparatus`, `pareto`, `per_page`), not by figure
number — the manuscript's figure numbering isn't locked yet.
