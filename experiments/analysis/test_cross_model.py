"""
Tests for cross_model.py — the failure-mode invariant in the Axis C loader (§6).

Regression tripwire. load_all() validated every failed record against a closed
two-mode tuple (LACKED, GRABBED), so the first record carrying
output_format_unreachable would have been flagged "unexpected failure_mode" and
crashed the loader — the same latent two-mode bug fixed elsewhere, but on a seam
no test covered. The check now lives in _assert_known_failure_modes() so the
taxonomy contract can be exercised on synthetic records without the corpus.

Run with: pytest experiments/analysis/test_cross_model.py -v
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from cross_model import (  # noqa: E402
    GRABBED,
    LACKED,
    UNREACHABLE,
    _assert_known_failure_modes,
)


def _failure(mode: str) -> dict:
    return {"success": False, "failure_mode": mode}


def _success() -> dict:
    return {"success": True, "failure_mode": None}


# ---------------------------------------------------------------------------
# The tripwire: an unreachable record must not be treated as unexpected
# ---------------------------------------------------------------------------

def test_all_three_modes_do_not_raise():
    recs = [
        _failure(LACKED),
        _failure(GRABBED),
        _failure(UNREACHABLE),
        _success(),
    ]
    # The pre-fix (LACKED, GRABBED) tuple would have raised on the UNREACHABLE record.
    _assert_known_failure_modes("synthetic", recs)


def test_absent_mode_is_fine():
    # Only two of the three modes present — still valid (subset, not equality).
    _assert_known_failure_modes("synthetic", [_failure(LACKED), _failure(GRABBED)])


def test_success_records_are_ignored():
    # A successful record with no failure_mode must not trip the check.
    _assert_known_failure_modes("synthetic", [_success(), _success()])


def test_foreign_mode_still_rejected():
    with pytest.raises(AssertionError, match="unexpected failure_mode"):
        _assert_known_failure_modes("synthetic", [_failure("something_else")])


def test_null_failure_mode_on_failure_rejected():
    # A failed record with no failure_mode is a data defect and must be caught.
    with pytest.raises(AssertionError, match="unexpected failure_mode"):
        _assert_known_failure_modes("synthetic", [{"success": False, "failure_mode": None}])
