"""
Tests for failure_decomp.py — the three-mode failure taxonomy (§6).

Regression tripwire. The analysis layer previously asserted a closed two-mode
set, so the first record carrying output_format_unreachable would have crashed
failure_decomp and, through run_all.py, every downstream number. Nothing caught
that because no test ever fed the module a third mode. This is that test.

Run with: pytest experiments/analysis/test_failure_modes.py -v
"""

import pathlib
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from failure_decomp import (  # noqa: E402
    CANONICAL_FAILURE_MODES,
    GRABBED,
    LACKED,
    UNREACHABLE,
    build_nv_residual,
    decompose_modes,
)


def _failure(mode: str, ssp: bool) -> dict:
    """One failed record. SSP must agree with the mode's D4 priority semantics."""
    return {
        "success": False,
        "failure_mode": mode,
        "stable_signal_present_in_bundle": ssp,
    }


def _frame(rows) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The tripwire: all three modes present
# ---------------------------------------------------------------------------

def test_all_three_modes_do_not_raise_and_are_counted_separately():
    """
    A record set containing all three canonical modes must decompose without
    raising, and each mode must be counted in its own category — never folded
    into another.
    """
    rows = (
        [_failure(LACKED, False)] * 5
        + [_failure(GRABBED, True)] * 3
        + [_failure(UNREACHABLE, True)] * 2
    )
    counts = decompose_modes(_frame(rows))

    assert counts["lacked"] == 5
    assert counts["grabbed"] == 3
    assert counts["unreachable"] == 2
    assert counts["total"] == 10
    # unreachable was not absorbed into either neighbour
    assert counts["lacked"] + counts["grabbed"] != counts["total"]


def test_modes_sum_to_total():
    rows = (
        [_failure(LACKED, False)] * 7
        + [_failure(GRABBED, True)] * 11
        + [_failure(UNREACHABLE, True)] * 4
    )
    c = decompose_modes(_frame(rows))
    assert c["lacked"] + c["grabbed"] + c["unreachable"] == c["total"]


# ---------------------------------------------------------------------------
# The SSP identity, which unreachable sits on the True side of
# ---------------------------------------------------------------------------

def test_unreachable_counts_on_the_ssp_true_side():
    """
    lacked wins whenever SSP is false (D4 priority), so unreachable can only
    occur with SSP=True. The identity is ssp_true == grabbed + unreachable,
    not ssp_true == grabbed.
    """
    rows = (
        [_failure(LACKED, False)] * 6
        + [_failure(GRABBED, True)] * 2
        + [_failure(UNREACHABLE, True)] * 3
    )
    c = decompose_modes(_frame(rows))
    assert c["grabbed"] + c["unreachable"] == 5
    assert c["lacked"] == 6


def test_unreachable_with_ssp_false_is_rejected():
    """An unreachable record with SSP=False violates D4 priority — lacked
    should have won. The identity must catch it rather than silently pass."""
    rows = [_failure(LACKED, False), _failure(UNREACHABLE, False)]
    with pytest.raises(AssertionError):
        decompose_modes(_frame(rows))


# ---------------------------------------------------------------------------
# Absence is allowed; a foreign mode is not
# ---------------------------------------------------------------------------

def test_missing_mode_is_not_an_error():
    """The current corpus has zero unreachable records. A mode being absent
    must not fail — the check is a subset, not equality."""
    rows = [_failure(LACKED, False)] * 4 + [_failure(GRABBED, True)] * 2
    c = decompose_modes(_frame(rows))
    assert c["unreachable"] == 0
    assert c["total"] == 6


def test_unknown_mode_is_rejected():
    rows = [_failure(LACKED, False), _failure("some_new_mode", True)]
    with pytest.raises(AssertionError, match="Unexpected failure modes"):
        decompose_modes(_frame(rows))


def test_null_failure_mode_is_rejected():
    rows = [_failure(LACKED, False), _failure(None, True)]
    with pytest.raises(AssertionError, match="null failure_mode"):
        decompose_modes(_frame(rows))


def test_canonical_set_is_exactly_the_three_modes():
    assert CANONICAL_FAILURE_MODES == {LACKED, GRABBED, UNREACHABLE}


# ---------------------------------------------------------------------------
# The residual-by-encoding table must fold unreachable into the denominator
# ---------------------------------------------------------------------------

def test_residual_denominator_includes_unreachable():
    """
    build_nv_residual must count unreachable in total_fail — a record carrying
    output_format_unreachable cannot be silently dropped, and the lacked%/grabbed%
    denominators must reflect it rather than a two-mode sum.
    """
    lacked      = pd.Series({"F0": 48, "F1": 48})
    grabbed     = pd.Series({"F0": 30, "F1": 30})
    unreachable = pd.Series({"F0": 2})  # empty for F1 — the NaN-poisoning case

    residual = build_nv_residual(lacked, grabbed, unreachable)

    # F1 has no unreachable record → filled to 0, not NaN.
    assert residual.loc["F1", "unreachable"] == 0
    # F0's unreachable is in its own column and in the denominator.
    assert residual.loc["F0", "unreachable"] == 2
    assert residual.loc["F0", "total_fail"] == 48 + 30 + 2  # not 78
    # Percentages use the three-mode denominator (80, not 78).
    assert residual.loc["F0", "lacked %"] == round(48 / 80 * 100, 1)
    assert residual.loc["F0", "unreachable %"] == round(2 / 80 * 100, 1)


def test_residual_zero_unreachable_matches_two_mode_values():
    """With zero unreachable records (the current corpus), the unreachable column
    is all-zero and lacked/grabbed percentages equal the old two-mode form."""
    lacked      = pd.Series({"F0": 48, "F1": 48})
    grabbed     = pd.Series({"F0": 33, "F1": 30})
    unreachable = pd.Series(dtype="int64")  # none at all

    residual = build_nv_residual(lacked, grabbed, unreachable)

    assert (residual["unreachable"] == 0).all()
    assert residual.loc["F0", "total_fail"] == 81
    assert residual.loc["F0", "lacked %"] == round(48 / 81 * 100, 1)
