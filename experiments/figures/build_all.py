"""
build_all.py - regenerate every Paper 1 figure and prove it meets MDPI.

Deletes figures/*.png first. A rebuild that leaves stale output behind is not a
rebuild: on 11.09.2026 a superseded apparatus render survived a regeneration and
was nearly submitted, because the renderer wrote a new file and nobody checked
that the old one was gone. Clearing the directory makes a missing figure a
failure instead of an invisible stale one.

    python build_all.py

Exit 0 means every figure was rendered in this run and passes the audit.
"""
import pathlib
import subprocess
import sys

SCRIPTS = ["make_fig_pareto.py", "make_fig_per_page.py", "make_fig_apparatus.py"]
FIGURES = pathlib.Path("figures")
EXPECTED = {"figure_apparatus.png", "figure_pareto.png", "figure_per_page.png"}


def main() -> int:
    FIGURES.mkdir(exist_ok=True)
    removed = 0
    for stale in FIGURES.glob("*.png"):
        stale.unlink()
        removed += 1
    print(f"Cleared {removed} file(s) from {FIGURES}/")

    for script in SCRIPTS:
        print(f"\n=== {script} ===")
        result = subprocess.run([sys.executable, script])
        if result.returncode:
            print(f"{script} failed - stopping.")
            return result.returncode

    produced = {path.name for path in FIGURES.glob("*.png")}
    missing = EXPECTED - produced
    if missing:
        print(f"\nMissing after the run: {sorted(missing)}")
        return 1
    unexpected = produced - EXPECTED
    if unexpected:
        print(f"\nUnexpected extra output: {sorted(unexpected)}")
        return 1

    print("\n=== audit ===")
    return subprocess.run(
        [sys.executable, "mdpi_figures.py", "audit", "figures"]
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
