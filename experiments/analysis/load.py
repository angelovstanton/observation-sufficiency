"""
load.py — single source of truth for this study's grounding experiment data.

Reads all 24 matrix_page_NN.jsonl files from experiments/runs/ into one pandas
DataFrame and validates the schema before returning.  Every analysis script
calls load_dataframe(repo_root) from here instead of reading JSONL itself.

What it adds beyond the raw records:
  - 'semantic_density' column (HIGH / LOW) for every row, derived from the
    page-classification table defined in §9 of the paper plan.
"""

import pathlib
import pandas as pd


# ── Page → semantic density classification ────────────────────────────────
#
# HIGH-semantic pages were designed with richer accessible names, ARIA roles,
# and visible text labels.  LOW-semantic pages lean on structural cues and are
# more susceptible to model errors when volatile class strings are present.
#
HIGH_SEMANTIC_PAGES = {
    f"page_{n:02d}" for n in [1, 2, 3, 4, 9, 10, 11, 12, 17, 18, 19, 20]
}
LOW_SEMANTIC_PAGES = {
    f"page_{n:02d}" for n in [5, 6, 7, 8, 13, 14, 15, 16, 21, 22, 23, 24]
}

# ── Expected schema constants ─────────────────────────────────────────────
#
# These are asserted on every load so schema drift is caught immediately.
#
EXPECTED_COLUMNS = {
    "run_id", "task_id", "page", "bundle", "encoding", "regime", "model",
    "repetition", "observation_tokens", "prompt_tokens_total",
    "completion_tokens", "locator_raw", "locator_type", "locator_value",
    "success", "failure_mode", "predicate_unique_match",
    "predicate_matches_oracle", "predicate_non_volatile",
    "predicate_non_positional", "stable_signal_present_in_bundle",
    "model_id_returned", "tokenizer_version", "schema_version",
    "testbed_page", "timestamp_utc", "seed",
}

EXPECTED_BUNDLES = {
    "B_full", "B_noVolatile", "B_noState", "B_noSemantic",
    "B_identityCore", "B_minimalCore", "B_playwrightMCP",
}

EXPECTED_ENCODINGS = {"F0", "F1", "F2", "F3", "F4"}

# DOM encodings are used by every bundle except B_playwrightMCP.
DOM_ENCODINGS = {"F0", "F1", "F2", "F3"}

# DOM bundles are all bundles that use DOM-walk observations (not ARIA).
DOM_BUNDLES = {
    "B_full", "B_noVolatile", "B_noState", "B_noSemantic",
    "B_identityCore", "B_minimalCore",
}


def load_dataframe(repo_root: pathlib.Path) -> pd.DataFrame:
    """
    Read, concatenate, and validate all 24 JSONL files.

    Args:
        repo_root: pathlib.Path pointing at the repository root.

    Returns:
        Validated DataFrame with 6,000 rows and an added 'semantic_density' column.

    Raises:
        AssertionError on any schema violation (fails loudly by design).
    """
    data_dir = repo_root / "experiments" / "runs"

    # Sort glob results so pages are processed in numeric order.
    jsonl_files = sorted(data_dir.glob("matrix_page_*.jsonl"))

    assert len(jsonl_files) == 24, (
        f"Expected 24 JSONL files in {data_dir}, found {len(jsonl_files)}"
    )

    # Read each file individually, then concatenate into one DataFrame.
    # pd.read_json with lines=True handles newline-delimited JSON.
    page_frames = []
    for jsonl_path in jsonl_files:
        page_frame = pd.read_json(jsonl_path, lines=True)
        page_frames.append(page_frame)

    df = pd.concat(page_frames, ignore_index=True)

    # ── Normalize 'page' column ───────────────────────────────────────────
    #
    # The harness stores full page paths such as 'pages/page_01.html'.
    # Downstream analysis uses the short form 'page_01', so extract it here
    # from either format.  Fails loudly if any value doesn't contain 'page_NN'.
    #
    df["page"] = df["page"].str.extract(r"(page_\d{2})", expand=False)
    assert df["page"].notna().all(), (
        "Some 'page' values did not contain a 'page_NN' pattern after normalization"
    )

    # ── Record count ──────────────────────────────────────────────────────
    #
    # 24 pages × 250 records per page (25 bundle×encoding pairs × 10 tasks) = 6,000.
    #
    assert len(df) == 6000, f"Expected 6,000 records, got {len(df):,}"

    # ── Column presence ───────────────────────────────────────────────────
    missing_columns = EXPECTED_COLUMNS - set(df.columns)
    assert not missing_columns, f"Missing columns: {missing_columns}"

    # ── Tokenizer version ─────────────────────────────────────────────────
    #
    # Cost is measured under the fixed o200k_base tokenizer (experiments/docs/SCHEMA.md §4).
    # Any other tokenizer version invalidates the cost comparison.
    #
    seen_tokenizer_versions = set(df["tokenizer_version"].dropna().unique())
    assert seen_tokenizer_versions == {"o200k_base"}, (
        f"Unexpected tokenizer version(s): {seen_tokenizer_versions}"
    )

    # ── Schema version ────────────────────────────────────────────────────
    # pandas reads "1.0" from JSON as int64 1, so compare numerically.
    seen_schema_versions = set(df["schema_version"].dropna().astype(float).unique())
    assert seen_schema_versions == {1.0}, (
        f"Unexpected schema version(s): {seen_schema_versions}"
    )

    # ── Type coercions ────────────────────────────────────────────────────
    df["success"] = df["success"].astype(bool)
    df["stable_signal_present_in_bundle"] = df["stable_signal_present_in_bundle"].astype(bool)
    df["observation_tokens"] = df["observation_tokens"].astype(int)

    # ── Bundle and encoding coverage ──────────────────────────────────────
    missing_bundles = EXPECTED_BUNDLES - set(df["bundle"].unique())
    assert not missing_bundles, f"Missing bundles: {missing_bundles}"

    unexpected_encodings = set(df["encoding"].unique()) - EXPECTED_ENCODINGS
    assert not unexpected_encodings, f"Unexpected encodings: {unexpected_encodings}"

    # ── F4 / ARIA pairing invariant ───────────────────────────────────────
    #
    # F4 is the genuine Playwright ARIA snapshot.  It must only appear with
    # B_playwrightMCP, and B_playwrightMCP must only use F4.
    #
    f4_in_dom_bundle = df[(df["encoding"] == "F4") & (df["bundle"] != "B_playwrightMCP")]
    assert len(f4_in_dom_bundle) == 0, (
        f"F4 encoding found outside B_playwrightMCP: {f4_in_dom_bundle['bundle'].unique()}"
    )

    aria_with_dom_encoding = df[
        (df["bundle"] == "B_playwrightMCP") & (df["encoding"] != "F4")
    ]
    assert len(aria_with_dom_encoding) == 0, (
        f"B_playwrightMCP found with non-F4 encoding: "
        f"{aria_with_dom_encoding['encoding'].unique()}"
    )

    # ── B_minimalCore produces near-zero token observations ──────────────
    #
    # B_minimalCore passes an empty or near-empty string to the model.  In
    # practice, records show either 0 or 1 token (mean 0.5) — the 1-token case
    # is a whitespace or newline artefact from the serialiser.  The key invariant
    # is that no meaningful content is present: all observation_tokens ≤ 1.
    #
    minimal_core_records = df[df["bundle"] == "B_minimalCore"]
    assert (minimal_core_records["observation_tokens"] <= 1).all(), (
        "B_minimalCore records have observation_tokens > 1 — unexpected content in minimal bundle"
    )

    # ── Page name format ──────────────────────────────────────────────────
    valid_page_name = df["page"].str.match(r"^page_\d{2}$")
    assert valid_page_name.all(), (
        f"Unexpected page name format: {df.loc[~valid_page_name, 'page'].unique()}"
    )

    # ── Add semantic_density column ───────────────────────────────────────
    #
    # Build a lookup dict and apply it.  Every page must resolve to a known stratum.
    #
    semantic_density_map = (
        {page: "HIGH" for page in HIGH_SEMANTIC_PAGES}
        | {page: "LOW" for page in LOW_SEMANTIC_PAGES}
    )
    df["semantic_density"] = df["page"].map(semantic_density_map)

    unmapped_pages = df.loc[df["semantic_density"].isna(), "page"].unique()
    assert len(unmapped_pages) == 0, (
        f"Pages not in semantic density map: {unmapped_pages}"
    )

    print(
        f"[load] {len(df):,} records | "
        f"{df['page'].nunique()} pages | "
        f"{df['bundle'].nunique()} bundles | "
        f"{df['encoding'].nunique()} encodings | "
        f"schema OK"
    )

    return df


if __name__ == "__main__":
    import sys
    repo_root = pathlib.Path(__file__).parent.parent.parent
    df = load_dataframe(repo_root)
    print(f"\nBundles:   {sorted(df['bundle'].unique())}")
    print(f"Encodings: {sorted(df['encoding'].unique())}")
    print(f"Pages:     {df['page'].nunique()}")
    print(f"Successes: {df['success'].sum():,} / {len(df):,} = {df['success'].mean():.2%}")
