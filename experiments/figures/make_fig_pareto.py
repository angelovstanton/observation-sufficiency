"""
make_fig_pareto.py - the cost/success Pareto surface, all 21 cells.

Derived from make_figure2.py. Two changes only:
  * reads experiments/results/computed/pareto_21cells.csv directly (bundle, encoding,
    mean_obs_tokens, success_rate) instead of the six published cells;
  * authored at MDPI print width and written through figstyle.save_mdpi.

Domination is recomputed here from the token/success columns and is NOT read
from the file's pareto_status column, so the figure is an independent check on
the pipeline rather than a rendering of it. The two are asserted to agree.
"""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from figstyle import WIDTH_IN, save_mdpi

REPO = pathlib.Path(__file__).resolve().parent.parent / "results" / "computed"
SOURCE = REPO / "pareto_21cells.csv"
OUTPUT = pathlib.Path("figures/figure_pareto.png")

COLOUR_FRONTIER = "#1F3864"
COLOUR_DOMINATED = "#B4BCC4"
COLOUR_COP = "#B03A2E"


def compute_frontier(frame: pd.DataFrame) -> list:
    """A cell is on the frontier if no other cell is cheaper AND at least as successful."""
    flags = []
    for _, cell in frame.iterrows():
        dominated = (
            (frame["tokens"] <= cell["tokens"])
            & (frame["success"] >= cell["success"])
            & ((frame["tokens"] < cell["tokens"]) | (frame["success"] > cell["success"]))
        ).any()
        flags.append(not dominated)
    return flags


def load() -> pd.DataFrame:
    raw = pd.read_csv(SOURCE)
    frame = pd.DataFrame({
        "bundle": raw["bundle"],
        "encoding": raw["encoding"],
        "tokens": raw["mean_obs_tokens"],
        "success": raw["success_rate"] * 100,
    })
    frame["on_frontier"] = compute_frontier(frame)

    assert len(frame) == 21, f"Expected 21 cells, found {len(frame)}."
    assert frame["tokens"].min() > 0, "Log axis needs strictly positive token counts."
    assert frame["success"].between(0, 100).all(), "Success values must be percentages."

    published = raw["pareto_status"].eq("FRONTIER").tolist()
    assert frame["on_frontier"].tolist() == published, (
        "Independently computed frontier disagrees with the pipeline's pareto_status column."
    )
    assert int(frame["on_frontier"].sum()) == 4, "The frontier should hold four cells."
    return frame


def draw(frame: pd.DataFrame, destination: pathlib.Path) -> None:
    figure, axes = plt.subplots(figsize=(WIDTH_IN, 4.0))

    frontier = frame[frame["on_frontier"]].sort_values("tokens")
    dominated = frame[~frame["on_frontier"]]

    axes.plot(frontier["tokens"], frontier["success"], "-",
              color=COLOUR_FRONTIER, linewidth=1.6, zorder=2,
              label="Pareto frontier")
    axes.scatter(frontier["tokens"], frontier["success"], s=62,
                 color=COLOUR_FRONTIER, zorder=3)
    axes.scatter(dominated["tokens"], dominated["success"], s=40,
                 color=COLOUR_DOMINATED, zorder=3,
                 label=f"dominated (n={len(dominated)})")

    cop = frame[(frame["bundle"] == "B_noVolatile") & (frame["encoding"] == "F3")]
    axes.scatter(cop["tokens"], cop["success"], s=170, facecolors="none",
                 edgecolors=COLOUR_COP, linewidths=2.0, zorder=4)

    # Label only the cells the manuscript refers to. Labelling all 21 produces
    # unreadable overlap: the dominated cloud carries its meaning by position.
    offsets = {
        ("B_identityCore", "F3"): (-6, -42),
        ("B_identityCore", "F0"): (18, 24),
        ("B_playwrightMCP", "F4"): (-46, -24),
        ("B_noVolatile", "F3"): (-44, 15),
        ("B_noVolatile", "F1"): (14, 10),
        ("B_full", "F1"): (-30, -36),
    }
    for _, cell in frame.iterrows():
        key = (cell["bundle"], cell["encoding"])
        if key not in offsets:
            continue
        label = f"{cell['bundle']}×{cell['encoding']}"
        if key == ("B_noVolatile", "F3"):
            label += " (COP)"
        elif key == ("B_full", "F1"):
            label += "\n(naïve baseline)"
        needs_leader = key != ("B_noVolatile", "F3")
        axes.annotate(
            label,
            (cell["tokens"], cell["success"]),
            textcoords="offset points",
            xytext=offsets[key],
            fontsize=8,
            color="#2B2B2B",
            arrowprops=dict(arrowstyle="-", color="#7A828A", linewidth=0.7,
                            shrinkA=0, shrinkB=3) if needs_leader else None,
        )

    axes.set_xscale("log")
    axes.set_xlabel("Mean observation cost (tokens, o200k_base, log scale)", fontsize=9)
    axes.set_ylabel("Grounding success (%)", fontsize=9)
    axes.tick_params(labelsize=8)
    axes.set_ylim(20, 78)
    axes.set_xlim(120, 45000)
    axes.grid(True, which="both", linewidth=0.4, color="#DDE2E6")
    axes.set_axisbelow(True)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    axes.legend(frameon=False, loc="upper left", fontsize=8)

    figure.tight_layout()
    save_mdpi(figure, destination)
    plt.close(figure)


if __name__ == "__main__":
    frame = load()
    draw(frame, OUTPUT)
