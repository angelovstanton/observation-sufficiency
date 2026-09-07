"""
make_fig_per_page.py - per-page difference in grounding success, all 24 pages.

Derived from make_figure3.py. Two changes only:
  * reads experiments/results/computed/thesis_per_page.csv (page, B_full %,
    B_noVolatile %) instead of a hand-made per_page.csv;
  * authored at MDPI print width and written through figstyle.save_mdpi,
    which is why the tick labels are 8 pt rather than 7 pt.

The published 18/4/2 split and the +9.48 pp corpus mean are asserted before
anything is drawn. A wrong export fails loudly instead of producing a
plausible but incorrect figure.
"""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from figstyle import WIDTH_IN, save_mdpi

REPO = pathlib.Path(__file__).resolve().parent.parent / "results" / "computed"
SOURCE = REPO / "thesis_per_page.csv"
OUTPUT = pathlib.Path("figures/figure_per_page.png")

EXPECTED_POSITIVE, EXPECTED_TIED, EXPECTED_NEGATIVE = 18, 4, 2
EXPECTED_MEAN_DELTA_PP = 9.48

COLOUR_POSITIVE = "#1F3864"
COLOUR_NEGATIVE = "#B03A2E"
COLOUR_TIED = "#B4BCC4"


def load() -> pd.DataFrame:
    raw = pd.read_csv(SOURCE)
    frame = pd.DataFrame({
        "page": raw["page"],
        "pct_bf": raw["B_full %"],
        "pct_nv": raw["B_noVolatile %"],
    })
    assert len(frame) == 24, f"Expected 24 pages, found {len(frame)}."
    frame["delta_pp"] = frame["pct_nv"] - frame["pct_bf"]
    return frame


def check_against_published(frame: pd.DataFrame) -> tuple[int, int, int]:
    positive = int((frame["delta_pp"] > 0).sum())
    tied = int((frame["delta_pp"] == 0).sum())
    negative = int((frame["delta_pp"] < 0).sum())
    assert (positive, tied, negative) == (EXPECTED_POSITIVE, EXPECTED_TIED, EXPECTED_NEGATIVE), (
        f"Per-page split is {positive}/{tied}/{negative}, but FINDINGS reports "
        f"{EXPECTED_POSITIVE}/{EXPECTED_TIED}/{EXPECTED_NEGATIVE}."
    )
    corpus_delta = frame["pct_nv"].mean() - frame["pct_bf"].mean()
    assert abs(corpus_delta - EXPECTED_MEAN_DELTA_PP) < 0.15, (
        f"Mean per-page delta is {corpus_delta:+.2f} pp; the corpus figure is "
        f"{EXPECTED_MEAN_DELTA_PP:+.2f} pp."
    )
    print(f"Checks passed: {positive}/{tied}/{negative}, mean delta {corpus_delta:+.2f} pp")
    return positive, tied, negative


def draw(frame: pd.DataFrame, split: tuple[int, int, int], destination: pathlib.Path) -> None:
    ordered = frame.sort_values("delta_pp", ascending=False).reset_index(drop=True)
    positive, tied, negative = split

    colours = [
        COLOUR_POSITIVE if value > 0 else COLOUR_NEGATIVE if value < 0 else COLOUR_TIED
        for value in ordered["delta_pp"]
    ]

    figure, axes = plt.subplots(figsize=(WIDTH_IN, 3.6))
    axes.bar(range(len(ordered)), ordered["delta_pp"], color=colours, width=0.72)
    axes.axhline(0, color="#333333", linewidth=0.9)

    # A tied page draws a zero-height bar, i.e. nothing. Without a mark the
    # reader cannot tell "measured, no difference" from "page missing", and the
    # tied category would exist only as a colour that never appears.
    tied_positions = [i for i, value in enumerate(ordered["delta_pp"]) if value == 0]
    axes.scatter(tied_positions, [0] * len(tied_positions), marker="s", s=12,
                 color=COLOUR_TIED, edgecolors="#333333", linewidths=0.4, zorder=4)

    axes.set_xticks(range(len(ordered)))
    axes.set_xticklabels(ordered["page"], rotation=90, fontsize=8)
    axes.tick_params(axis="y", labelsize=8)
    axes.set_ylabel("Success difference,\nB_noVolatile − B_full (pp)", fontsize=9)
    axes.set_xlabel("Test page, sorted by difference", fontsize=9)
    axes.grid(axis="y", linewidth=0.4, color="#DDE2E6")
    axes.set_axisbelow(True)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)

    axes.text(
        0.98, 0.94,
        f"{positive} pages favour B_noVolatile · {tied} tied · {negative} favour B_full",
        transform=axes.transAxes, ha="right", va="top", fontsize=8, color="#333333",
    )

    figure.tight_layout()
    save_mdpi(figure, destination)
    plt.close(figure)


if __name__ == "__main__":
    frame = load()
    draw(frame, check_against_published(frame), OUTPUT)
