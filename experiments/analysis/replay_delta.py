"""Zero-delta replay check.

Compares an offline-replay output (`experiments/runs/replay_<date>.jsonl`, produced by
`dotnet run --project experiments/ -- --replay`) against the committed source corpus
(`experiments/runs/matrix_page_*.jsonl`), joined on
`(page, bundle, encoding, task_id, repetition)`.

Replay re-applies the *current* predicate to the *originally recorded* model outputs,
so a faithful predicate + unchanged testbed HTML must reproduce every classification
exactly. This script is the verdict `ReplayMode` does not print (that only reports the
record total and the NONE-target invariant): it reports per-field deltas and coverage,
prints an explicit PASS/FAIL, and exits non-zero on any difference.

Usage:
    python replay_delta.py [replay_file] [matrix_dir]

Both arguments are optional:
    replay_file  default = newest experiments/runs/replay_*.jsonl
    matrix_dir   default = experiments/runs   (globs matrix_page_*.jsonl)
"""
import glob
import json
import pathlib
import sys

# UTF-8 console-independence: reconfigure stdout/stderr so Unicode glyphs print on any
# console (e.g. Windows cp1252) without PYTHONUTF8. Affects output ENCODING only.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

RUNS_DIR = pathlib.Path(__file__).resolve().parent.parent / "runs"

# Join key and the fields whose classification must be reproduced exactly.
KEY_FIELDS = ("page", "bundle", "encoding", "task_id", "repetition")
COMPARE_FIELDS = (
    "success",
    "failure_mode",
    "stable_signal_present_in_bundle",
    "observation_tokens",
)


def _load(path):
    """Read a JSONL file into {key_tuple: record}. Duplicate keys are a corpus error."""
    records = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = tuple(rec.get(f) for f in KEY_FIELDS)
            if key in records:
                raise SystemExit(f"FAIL: duplicate key {key} in {path}")
            records[key] = rec
    return records


def _resolve_replay(arg):
    if arg:
        return pathlib.Path(arg)
    candidates = sorted(RUNS_DIR.glob("replay_*.jsonl"))
    if not candidates:
        raise SystemExit(
            f"FAIL: no replay_*.jsonl in {RUNS_DIR}. Run the --replay step first "
            "(see TESTING.md §5)."
        )
    return candidates[-1]  # newest by lexicographic date-stamped name


def main(argv):
    replay_path = _resolve_replay(argv[0] if len(argv) > 0 else None)
    matrix_dir = pathlib.Path(argv[1]) if len(argv) > 1 else RUNS_DIR

    matrix_files = sorted(matrix_dir.glob("matrix_page_*.jsonl"))
    if not matrix_files:
        raise SystemExit(f"FAIL: no matrix_page_*.jsonl in {matrix_dir}")

    source = {}
    for mf in matrix_files:
        for key, rec in _load(mf).items():
            if key in source:
                raise SystemExit(f"FAIL: duplicate key {key} across matrix files")
            source[key] = rec
    replay = _load(replay_path)

    print(f"replay file:    {replay_path}")
    print(f"matrix dir:     {matrix_dir}  ({len(matrix_files)} files)")
    print(f"source records: {len(source)}")
    print(f"replay records: {len(replay)}")

    source_keys = set(source)
    replay_keys = set(replay)
    missing_in_replay = source_keys - replay_keys
    extra_in_replay = replay_keys - source_keys
    common = source_keys & replay_keys
    print(f"common keys:    {len(common)}")
    print(f"missing in replay: {len(missing_in_replay)}")
    print(f"extra in replay:   {len(extra_in_replay)}")
    print()

    # Per-field delta counts over the common keys.
    field_deltas = {f: [] for f in COMPARE_FIELDS}
    for key in common:
        s, r = source[key], replay[key]
        for f in COMPARE_FIELDS:
            if s.get(f) != r.get(f):
                field_deltas[f].append((key, s.get(f), r.get(f)))

    for f in COMPARE_FIELDS:
        print(f"  {f:<34} delta: {len(field_deltas[f])}")
    for f in COMPARE_FIELDS:
        for key, sv, rv in field_deltas[f][:10]:
            print(f"    [{f}] {key}: source={sv!r} replay={rv!r}")

    total_field_delta = sum(len(v) for v in field_deltas.values())
    coverage_clean = not missing_in_replay and not extra_in_replay
    ok = coverage_clean and total_field_delta == 0

    print()
    if ok:
        print(f"ZERO DELTA — {len(common)} records reproduce exactly on "
              f"{', '.join(COMPARE_FIELDS)}.")
        return 0

    print("NON-ZERO DELTA — replay does not match the source corpus.")
    print(f"  coverage mismatch: {len(missing_in_replay)} missing / "
          f"{len(extra_in_replay)} extra")
    print(f"  field deltas:      {total_field_delta}")
    print("A non-zero delta means the predicate or the testbed HTML changed since the "
          "corpus was locked (see TESTING.md §5).")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
