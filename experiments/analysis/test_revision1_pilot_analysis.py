"""
Tests for revision1_pilot_analysis.py on synthetic records only (no pilot outcome is read).

One record per pilot event is built from the pinned plan, reuse map and targets with seeded random
outcomes, written as batch_pilot_*.jsonl shards to a temp directory, and the analysis is checked
against an independent recomputation.

Run with: pytest experiments/analysis/test_revision1_pilot_analysis.py -v
"""

import hashlib
import json
import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import revision1_pilot_analysis as PA  # noqa: E402

BUNDLE_OF = {"B_full": "B_full", "B_noVolatile": "B_noVolatileConsistent", "class_only": "B_full_minus_volClass"}


@pytest.fixture(scope="module")
def pin():
    return PA.load_pinned()


def synth(pin, seed=7):
    """event_key → record (called events first, then reused copies of their sources)."""
    rng = np.random.default_rng(seed)
    p5_rate = {"B_full": 0.55, "B_noVolatile": 0.70, "class_only": 0.65}
    recs = {}
    for k, e in pin["called"].items():
        t = pin["target"][(e["page"], e["task_id"])]
        has = t["stratum"] == PA.HAS
        p5 = bool(has and rng.random() < p5_rate[e["cell"]])
        um = bool(p5 or rng.random() < 0.8)
        mo = bool(p5 or (um and rng.random() < 0.9))
        recs[k] = {
            "event_key": k, "page": e["page"], "task_id": e["task_id"], "bundle": e["bundle"],
            "encoding": e["encoding"], "model": "gpt-4.1", "plan_sha256": PA.PINS["pilot_plan.json"],
            "observation_sha256": e["observation_sha256"], "success": p5,
            "predicate_unique_match": um, "predicate_matches_oracle": mo,
            "stable_signal_present_in_bundle": has,
            "failure_mode": None if p5 else ("observation_lacked_stable_signal" if not has else "model_grabbed_brittle_signal"),
            "locator_raw": f"css:[data-x='{k}']", "prompt_tokens_total": e["input_tokens"] + 12,
            "completion_tokens": 20, "observation_tokens": 1000, "reused": False, "reused_from_event_key": None,
        }
    for k, r in pin["reused"].items():
        s = dict(recs[r["reused_event_key"]])
        s.update(event_key=k, bundle="B_full_minus_volClass", reused=True, reused_from_event_key=r["reused_event_key"])
        recs[k] = s
    return recs


def write(recs, d: pathlib.Path):
    d.mkdir(parents=True, exist_ok=True)
    shards = {}
    for r in recs.values():
        shards.setdefault(r["page"], []).append(r)
    for page, rs in shards.items():
        (d / f"batch_pilot_gpt-4-1_{page}.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8")
    return d


@pytest.fixture(scope="module")
def full(pin, tmp_path_factory):
    recs = synth(pin)
    d = write(recs, tmp_path_factory.mktemp("pilot") / "records")
    return recs, d, PA.analyse(d, None)


def by_cell(recs, pin):
    out = {}
    for k, r in recs.items():
        cell = PA.CELL_OF[r["bundle"]]
        out[(r["page"], r["task_id"], r["encoding"], cell)] = r
    return out


def test_counts(full, pin):
    recs, _, res = full
    s = res["run_summary"]
    assert (s["records"], s["expected"], s["missing"]) == (1956, 1956, 0)
    assert (s["called_records"], s["reused_records"]) == (1476, 480)
    n_has = sum(t["stratum"] == PA.HAS for t in pin["target"].values())
    assert n_has == 313
    for c in res["comparisons"]:
        assert c["n"] == n_has and c["stratum"] == PA.HAS


def test_mcnemar_matches_independent_count(full, pin):
    recs, _, res = full
    cells = by_cell(recs, pin)
    for c in res["comparisons"]:
        b = cc = 0
        for (page, task), t in pin["target"].items():
            if t["stratum"] != PA.HAS:
                continue
            f, s = cells[(page, task, c["encoding"], c["first"])], cells[(page, task, c["encoding"], c["second"])]
            val = (lambda r: r["success"]) if c["metric"] == "P5" else \
                  (lambda r: r["predicate_unique_match"] and r["predicate_matches_oracle"])
            b += (not val(f)) and val(s)
            cc += val(f) and not val(s)
        assert (c["b_second_only"], c["c_first_only"]) == (b, cc)
        assert c["delta_pp"] == pytest.approx((b - cc) / c["n"] * 100)
        assert c["ci_lo"] <= c["delta_pp"] <= c["ci_hi"] and c["empty_replicates"] == 0
        assert c["replicates"] == PA.N_BOOT


def test_deterministic(full, pin):
    _, d, res = full
    again = PA.analyse(d, None)
    assert json.dumps(PA.jsonable(again["comparisons"])) == json.dumps(PA.jsonable(res["comparisons"]))


def test_no_signal_is_descriptive_only(full):
    _, _, res = full
    assert all(c["stratum"] == PA.HAS for c in res["comparisons"])
    for r in res["descriptive_no_signal"]:
        assert set(r) == {"stratum", "encoding", "cell", "n", "P5_count", "P5_pct", "P_now_count", "P_now_pct"}
        assert r["n"] == 13 and r["P5_count"] == 0          # condition 5 false ⇒ P5 false (synthetic, as by design)


def test_reused_records_carry_source(full, pin):
    recs, _, res = full
    nv = {r["cell"]: r for r in res["descriptive_has_signal"] if r["encoding"] == "F1"}
    assert nv["class_only"]["n"] == nv["B_noVolatile"]["n"] == 313


def test_interpretation_rule(full):
    _, _, res = full
    for c in res["comparisons"]:
        if c["metric"] == "P5":
            assert c["matches_corpus"] == (c["delta_pp"] > 0)
        else:
            assert c["matches_corpus"] == (c["ci_lo"] <= 0 <= c["ci_hi"])


def test_missing_events_reported_not_replaced(pin, tmp_path):
    recs = synth(pin)
    src = next(r["reused_event_key"] for r in pin["reused"].values())
    co = next(k for k, r in pin["reused"].items() if r["reused_event_key"] == src)
    del recs[src], recs[co]
    res = PA.analyse(write(recs, tmp_path / "r"), None)
    assert res["run_summary"]["missing"] == 2 and set(res["run_summary"]["missing_keys"]) == {src, co}
    t = pin["target"][(pin["called"][src]["page"], pin["called"][src]["task_id"])]
    enc = pin["called"][src]["encoding"]
    for c in res["comparisons"]:
        expect = 313 - (1 if (c["encoding"] == enc and t["stratum"] == PA.HAS) else 0)
        assert c["n"] == expect


@pytest.mark.parametrize("field,value,msg", [
    ("plan_sha256", "0" * 64, "plan_sha256"),
    ("observation_sha256", "0" * 64, "observation_sha256"),
    ("stable_signal_present_in_bundle", None, "condition 5"),
    ("reused", True, "reuse marker"),
])
def test_inconsistent_called_record_refused(pin, tmp_path, field, value, msg):
    recs = synth(pin)
    k = next(iter(pin["called"]))
    recs[k][field] = (not recs[k][field]) if value is None else value
    with pytest.raises(PA.PilotDataError, match=msg):
        PA.analyse(write(recs, tmp_path / "r"), None)


def test_reused_differs_from_source_refused(pin, tmp_path):
    recs = synth(pin)
    k = next(iter(pin["reused"]))
    recs[k]["success"] = not recs[k]["success"]
    with pytest.raises(PA.PilotDataError, match="differs from source"):
        PA.analyse(write(recs, tmp_path / "r"), None)


def test_duplicate_and_unknown_refused(pin, tmp_path):
    recs = synth(pin)
    d = write(recs, tmp_path / "r")
    extra = dict(next(iter(recs.values())))
    (d / "batch_pilot_gpt-4-1_zzzz.jsonl").write_text(json.dumps(extra) + "\n", encoding="utf-8")
    with pytest.raises(PA.PilotDataError, match="duplicate"):
        PA.analyse(d, None)
    extra["event_key"] = "gpt-4.1|B_full|F2|x|t_01|0"
    (d / "batch_pilot_gpt-4-1_zzzz.jsonl").write_text(json.dumps(extra) + "\n", encoding="utf-8")
    with pytest.raises(PA.PilotDataError, match="not a pilot event"):
        PA.analyse(d, None)


def test_site_bootstrap_counts_empty_replicates():
    order = [f"s{i}" for i in range(5)]
    pairs = [("s2", False, True), ("s2", False, True), ("s2", True, True)]
    r = PA.site_bootstrap(order, pairs, n_boot=2000, seed=42)
    rng = np.random.default_rng(42)
    empty = sum("s2" not in rng.choice(np.asarray(order, dtype=object), size=5, replace=True) for _ in range(2000))
    assert r["empty_replicates"] == empty > 0
    assert r["ci_lo"] == pytest.approx(66.6666667) and r["ci_hi"] == pytest.approx(66.6666667)


def survival_tsv(recs, pin, path, flip=None, bad_sha=None, undetermined=(), no_reference_sites=()):
    lines = [PA.SURVIVAL_HEADER]
    for k, r in sorted(recs.items()):
        if pin["sept"][(r["page"], r["task_id"])]["status"] != "unique":
            continue
        ok = r["success"] if k != flip else not r["success"]
        sha = hashlib.sha256(r["locator_raw"].encode("utf-8")).hexdigest() if k != bad_sha else "0" * 64
        if r["page"] in no_reference_sites:
            lines.append(f"{k}\t{sha}\t\t\tundetermined_no_reference\t0\t\t")
        elif k in undetermined:
            lines.append(f"{k}\t{sha}\t\t\tundetermined\t5\t{','.join(['f' * 64] * 5)}\t0/1/-1,0/1/-1,0/1/-1,0/1/-1,0/1/-1")
        else:
            lines.append(f"{k}\t{sha}\t{ok}\t{ok}\t{'survived' if ok else 'broken'}\t1\t{'e' * 64}\t1/0/1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def reference_file(pin, path, unstable=()):
    """A synthetic real_pilot/survival_reference.json: 33 sites, `unstable` without a stable reference (е′)."""
    sites = [{"key": k, "stable": k not in unstable, "status": PA.NO_REFERENCE if k in unstable else "stable",
              "reference_sha256": None if k in unstable else hashlib.sha256(k.encode()).hexdigest()}
             for k in pin["site_order"]]
    path.write_text(json.dumps({"sites": sites}), encoding="utf-8")
    return path


def test_survival(full, pin, tmp_path):
    recs, d, _ = full
    res = PA.analyse(d, survival_tsv(recs, pin, tmp_path / "s.tsv"),
                     reference=reference_file(pin, tmp_path / "ref.json"))
    sv = res["survival"]
    assert sv["computed"] and sv["undefined_targets"] == {"absent": 51, "ambiguous": 10}
    cells = by_cell(recs, pin)
    for c in sv["cells"]:
        defined = [r for (p, t, e, cell), r in cells.items()
                   if e == c["encoding"] and cell == c["cell"] and pin["sept"][(p, t)]["status"] == "unique"]
        assert c["defined"] == len(defined) and c["undefined"] == 326 - len(defined)
        assert c["survived"] == sum(r["success"] for r in defined)
    k = next(k for k, r in recs.items() if pin["sept"][(r["page"], r["task_id"])]["status"] == "unique")
    with pytest.raises(PA.PilotDataError, match="locator"):
        PA.analyse(d, survival_tsv(recs, pin, tmp_path / "b.tsv", bad_sha=k),
                   reference=reference_file(pin, tmp_path / "ref.json"))


def test_survival_undetermined_is_counted_apart_and_left_out_of_the_share(full, pin, tmp_path):
    """Addendum (д): unstable September DOM after 5 loads → 'undetermined', separate from survived / broken / undefined."""
    recs, d, _ = full
    cells = by_cell(recs, pin)
    ks = [r["event_key"] for (p, t, e, c), r in sorted(cells.items())
          if e == "F1" and c == "B_full" and pin["sept"][(p, t)]["status"] == "unique"][:3]
    sv = PA.analyse(d, survival_tsv(recs, pin, tmp_path / "u.tsv", undetermined=set(ks)),
                    reference=reference_file(pin, tmp_path / "ref.json"))["survival"]
    c = next(c for c in sv["cells"] if c["encoding"] == "F1" and c["cell"] == "B_full")
    defined = [r for (p, t, e, cell), r in cells.items()
               if e == "F1" and cell == "B_full" and pin["sept"][(p, t)]["status"] == "unique"]
    assert c["undetermined"] == 3 and c["determined"] == c["defined"] - 3 == len(defined) - 3
    assert c["survived"] == sum(r["success"] for r in defined if r["event_key"] not in ks)
    assert c["share_pct"] == pytest.approx(c["survived"] / c["determined"] * 100)
    other = next(c for c in sv["cells"] if c["encoding"] == "F3" and c["cell"] == "B_full")
    assert other["undetermined"] == 0


def test_survival_status_must_agree_with_the_predicates(full, pin, tmp_path):
    recs, d, _ = full
    path = survival_tsv(recs, pin, tmp_path / "s.tsv")
    lines = path.read_text(encoding="utf-8").splitlines()
    f = lines[1].split("\t")
    f[4] = "broken" if f[4] == "survived" else "survived"
    lines[1] = "\t".join(f)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(PA.PilotDataError, match="disagrees"):
        PA.analyse(d, path, reference=reference_file(pin, tmp_path / "ref.json"))


def test_survival_no_reference_is_counted_apart_and_left_out_of_the_share(full, pin, tmp_path):
    """Addendum (е′): a site without a stable September reference → all its survival results are
    'undetermined_no_reference', reported apart from survived / broken / undefined / undetermined (unstable DOM)."""
    recs, d, _ = full
    site = pin["site_order"][1]
    ref = reference_file(pin, tmp_path / "ref.json", unstable={site})
    sv = PA.analyse(d, survival_tsv(recs, pin, tmp_path / "n.tsv", no_reference_sites={site}), reference=ref)["survival"]
    assert sv["no_reference_sites"] == [site]
    cells = by_cell(recs, pin)
    for c in sv["cells"]:
        defined = [r for (p, t, e, cell), r in cells.items()
                   if e == c["encoding"] and cell == c["cell"] and pin["sept"][(p, t)]["status"] == "unique"]
        on_site = [r for r in defined if r["page"] == site]
        assert on_site and c["undetermined_no_reference"] == len(on_site)
        assert c["undetermined"] == 0 and c["determined"] == len(defined) - len(on_site)
        assert c["survived"] == sum(r["success"] for r in defined if r["page"] != site)
        assert c["survived"] + c["broken"] == c["determined"]
        assert c["share_pct"] == pytest.approx(c["survived"] / c["determined"] * 100)


def test_survival_no_reference_must_match_the_reference_file(full, pin, tmp_path):
    recs, d, _ = full
    a, b = pin["site_order"][1], pin["site_order"][2]
    # the TSV says "no reference" for a site whose reference is stable
    with pytest.raises(PA.PilotDataError, match="reference of"):
        PA.analyse(d, survival_tsv(recs, pin, tmp_path / "x.tsv", no_reference_sites={a}),
                   reference=reference_file(pin, tmp_path / "r1.json"))
    # the reference file has no stable reference for a site the TSV evaluated
    with pytest.raises(PA.PilotDataError, match="reference of"):
        PA.analyse(d, survival_tsv(recs, pin, tmp_path / "y.tsv", no_reference_sites={a}),
                   reference=reference_file(pin, tmp_path / "r2.json", unstable={a, b}))
    # no reference file at all
    with pytest.raises(PA.PilotDataError, match="survival_reference"):
        PA.analyse(d, survival_tsv(recs, pin, tmp_path / "z.tsv"), reference=tmp_path / "missing.json")


def test_reference_site_neither_stable_nor_marked_is_refused(full, pin, tmp_path):
    """Addenda (е′) / (е‴) point 3: a site without a stable reference must carry the 'undetermined (no stable
    reference)' mark; an unmarked non-stable site stops the analysis."""
    recs, d, _ = full
    ref = reference_file(pin, tmp_path / "ref.json", unstable={pin["site_order"][1]})
    doc = json.loads(ref.read_text(encoding="utf-8"))
    del doc["sites"][1]["status"]
    ref.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(PA.PilotDataError, match="neither stable nor marked"):
        PA.analyse(d, None, reference=ref)


def test_n3_released_liability_one_released_key_and_one_overrun_release():
    """Addendum (е) point 4: one released key adds Bound(reservation) = reservation × 2 + 256 × 8 µUSD (the line's
    reservation, else the last pending's); an overrun release adds nothing; a released key called again keeps its
    liability (its response is counted with the called records; nothing is netted)."""
    j = [
        {"type": "pending", "key": "A", "attempt": 1, "reservation": 37_982},
        {"type": "error", "key": "A", "attempt": 1, "message": "TaskCanceledException"},
        {"type": "released", "key": "A", "attempt": 1, "reservation": 37_982},
        {"type": "pending", "key": "A", "attempt": 2, "reservation": 37_982},
        {"type": "response", "key": "A", "attempt": 2, "prompt_tokens": 37_900, "completion_tokens": 20},
        {"type": "pending", "key": "B", "attempt": 1, "reservation": 1_000},
        {"type": "response", "key": "B", "attempt": 1, "prompt_tokens": 1_200, "completion_tokens": 10},
        {"type": "budget_overrun", "key": "B", "attempt": 1, "prompt_tokens": 1_200, "reservation": 1_000},
        {"type": "overrun_released", "key": "B", "attempt": 1, "reservation": 1_000, "prompt_tokens": 1_200,
         "completion_tokens": 10},
    ]
    assert PA.released_liability(j) == (37_982 * 2 + 256 * 8, 1)
    no_line_reservation = [dict(e) for e in j]
    del no_line_reservation[2]["reservation"]
    assert PA.released_liability(no_line_reservation) == (37_982 * 2 + 256 * 8, 1)
    assert PA.released_liability([e for e in j if e["key"] == "B"]) == (0, 0)


def test_n3_run_summary_adds_the_liability(full, pin, tmp_path):
    recs, _, _ = full
    d = write(recs, tmp_path / "j")
    (d / "journal.jsonl").write_text("\n".join(json.dumps(e) for e in [
        {"type": "pending", "key": "k", "attempt": 1, "reservation": 28_898},
        {"type": "released", "key": "k", "attempt": 1, "reservation": 28_898},
    ]) + "\n", encoding="utf-8")
    s = PA.analyse(d, None)["run_summary"]
    assert s["released_lines"] == 1
    assert s["released_liability_usd"] == pytest.approx(59_844 / 1e6)
    assert s["total_usd"] == pytest.approx(s["list_price_usd"] + 59_844 / 1e6)


def test_survival_not_computed(full):
    _, _, res = full
    assert res["survival"]["computed"] is False


def test_main_writes_report(full, tmp_path):
    _, d, _ = full
    out = tmp_path / "pilot_analysis"
    assert PA.main(["--records", str(d), "--survival", str(tmp_path / "none.tsv"), "--out-prefix", str(out)]) == 0
    md = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "Direction, not size" in md and "descriptive only" in md and "Not computed" in md
    assert json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))["run_summary"]["records"] == 1956


def test_missing_records_dir_refused(tmp_path):
    with pytest.raises(PA.PilotDataError, match="not found"):
        PA.analyse(tmp_path / "nope", None)


# Strict join and refusals (synthetic records only)

def test_pinned_join_is_one_to_one(pin):
    """Plan + reuse map cover every (target × cell × encoding) exactly once; called and reused keys are disjoint."""
    assert not set(pin["called"]) & set(pin["reused"])
    cells = {(e["page"], e["task_id"], e["cell"], e["encoding"]) for e in pin["called"].values()} | \
            {(r["page"], r["task_id"], "class_only", r["encoding"]) for r in pin["reused"].values()}
    assert len(cells) == PA.N_CALLED + PA.N_REUSED == 326 * 3 * 2


def _join_args(pin):
    called = {k: dict(e) for k, e in pin["called"].items()}
    reused = {k: dict(r) for k, r in pin["reused"].items()}
    return called, reused, pin["target"], PA.PINS["pilot_plan.json"]


def test_join_refuses_a_key_both_called_and_reused(pin):
    called, reused, target, sha = _join_args(pin)
    k = next(iter(reused))
    called[k] = dict(next(iter(called.values())))
    with pytest.raises(PA.PilotDataError, match="both called and reused"):
        PA.check_join(called, reused, target, sha)


def test_join_refuses_a_missing_or_duplicated_cell(pin):
    called, reused, target, sha = _join_args(pin)
    k = next(iter(called))
    del called[k]
    with pytest.raises(PA.PilotDataError, match="1:1"):
        PA.check_join(called, reused, target, sha)
    called, reused, target, sha = _join_args(pin)
    k1, k2 = [k for k, e in called.items() if e["cell"] == "B_full"][:2]
    called[k2] = dict(called[k2], page=called[k1]["page"], task_id=called[k1]["task_id"], encoding=called[k1]["encoding"])
    with pytest.raises(PA.PilotDataError, match="1:1"):
        PA.check_join(called, reused, target, sha)


def test_join_refuses_stratum_mismatch_wrong_source_and_reuse_plan(pin):
    called, reused, target, sha = _join_args(pin)
    k = next(iter(called))
    called[k]["stratum"] = PA.NONE if called[k]["stratum"] == PA.HAS else PA.HAS
    with pytest.raises(PA.PilotDataError, match="stratum"):
        PA.check_join(called, reused, target, sha)
    called, reused, target, sha = _join_args(pin)
    k = next(iter(reused))
    reused[k]["reused_event_key"] = next(e for e, v in called.items() if v["cell"] == "B_full")
    with pytest.raises(PA.PilotDataError, match="reuse source"):
        PA.check_join(called, reused, target, sha)
    called, reused, target, _ = _join_args(pin)
    with pytest.raises(PA.PilotDataError, match="names plan"):
        PA.check_join(called, reused, target, "0" * 64)


def test_pinned_file_hash_mismatch_refused(tmp_path):
    import shutil
    for name in PA.PINS:
        shutil.copy(PA.RP_DIR / name, tmp_path / name)
    with open(tmp_path / "targets.json", "ab") as f:
        f.write(b" ")
    with pytest.raises(PA.PilotDataError, match="targets.json sha256"):
        PA.load_pinned(tmp_path)


@pytest.mark.parametrize("field", ["page", "task_id", "bundle", "encoding"])
def test_record_disagreeing_with_plan_refused(pin, tmp_path, field):
    recs = synth(pin)
    k = next(iter(pin["called"]))
    recs[k][field] = {"page": "0001_x.org", "task_id": "t_99", "bundle": "B_noState", "encoding": "F2"}[field]
    with pytest.raises(PA.PilotDataError, match="differ from the plan"):
        PA.analyse(write(recs, tmp_path / "r"), None)


def test_reused_record_without_source_or_wrong_source_refused(pin, tmp_path):
    recs = synth(pin)
    k, r = next(iter(pin["reused"].items()))
    del recs[r["reused_event_key"]]
    with pytest.raises(PA.PilotDataError, match="without its source"):
        PA.analyse(write(recs, tmp_path / "a"), None)
    recs = synth(pin)
    recs[k]["reused_from_event_key"] = next(iter(pin["called"]))
    with pytest.raises(PA.PilotDataError, match="reuse marker"):
        PA.analyse(write(recs, tmp_path / "b"), None)
    recs = synth(pin)
    recs[k]["observation_sha256"] = "0" * 64
    with pytest.raises(PA.PilotDataError, match="observation_sha256"):
        PA.analyse(write(recs, tmp_path / "c"), None)


@pytest.mark.parametrize("damage,msg", [
    ("header", "header"), ("duplicate", "duplicate"), ("missing", "no result"), ("extra", "without a record"),
])
def test_survival_tsv_refusals(full, pin, tmp_path, damage, msg):
    recs, d, _ = full
    path = survival_tsv(recs, pin, tmp_path / "s.tsv")
    lines = path.read_text(encoding="utf-8").splitlines()
    if damage == "header":
        lines[0] = "event_key\tunique_match"
    elif damage == "duplicate":
        lines.append(lines[1])
    elif damage == "missing":
        del lines[1]
    else:
        lines.append(f"gpt-4.1|B_full|F1|9999_x.org|t_01|0\t{'0' * 64}\tTrue\tTrue\tsurvived\t1\t{'e' * 64}\t1/0/1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(PA.PilotDataError, match=msg):
        PA.analyse(d, path, reference=reference_file(pin, tmp_path / "ref.json"))


def test_bootstrap_clusters_are_sites_in_tranco_order(pin):
    sites = json.loads((PA.RP_DIR / "pilot_sites.json").read_text(encoding="utf-8"))["sites"]
    ranks = {s["key"]: s["rank"] for s in sites}
    assert len(pin["site_order"]) == 33
    assert [ranks[k] for k in pin["site_order"]] == sorted(ranks.values())


def test_comparisons_report_mcnemar_or_ci_and_p(full, pin):
    """χ² uncorrected, exact p, OR = b/c with its exact conditional CI — as revision1_diagnostics.mcnemar reports them."""
    from scipy.stats import beta, binomtest
    _, _, res = full
    for c in res["comparisons"]:
        b, cc = c["b_second_only"], c["c_first_only"]
        if b + cc == 0:
            continue
        assert c["chi2"] == pytest.approx((b - cc) ** 2 / (b + cc))
        assert c["p_exact"] == pytest.approx(binomtest(b, b + cc, 0.5).pvalue)
        if cc > 0 and b > 0:
            assert c["odds_ratio"] == pytest.approx(b / cc)
            lo = beta.ppf(0.025, b, cc + 1)
            hi = beta.ppf(0.975, b + 1, cc)
            assert c["or_ci_lo"] == pytest.approx(lo / (1 - lo)) and c["or_ci_hi"] == pytest.approx(hi / (1 - hi))


def test_no_signal_rows_report_p_now_from_the_records(full, pin):
    recs, _, res = full
    cells = by_cell(recs, pin)
    for r in res["descriptive_no_signal"]:
        sel = [cells[(p, t, r["encoding"], r["cell"])] for (p, t), tg in pin["target"].items() if tg["stratum"] == PA.NONE]
        assert r["P_now_count"] == sum(bool(x["predicate_unique_match"] and x["predicate_matches_oracle"]) for x in sel)


def test_survival_match_exactly_one_same_role_and_name():
    rp = PA.RP_DIR
    sys.path.insert(0, str(rp))
    import rp_survival as RS
    link = {"tag": "a", "name": "Docs", "xpath": "/a[1]", "xpathRoundTrip": True}
    other = {"tag": "button", "name": "Docs", "xpath": "/button[1]", "xpathRoundTrip": True}
    roled = {"tag": "div", "roleAttr": "link extra", "name": "Docs", "xpath": "/div[1]", "xpathRoundTrip": True}
    norole = {"tag": "div", "name": "Docs", "xpath": "/div[2]", "xpathRoundTrip": True}
    assert RS.match([link, other, norole], "link", "Docs") == {"status": "unique", "sept_xpath": "/a[1]", "xpath_round_trip": True}
    assert RS.match([link, roled], "link", "Docs") == {"status": "ambiguous", "matches": 2}
    assert RS.match([other], "link", "Docs") == {"status": "absent", "matches": 0}
    assert RS.match([link], "link", "docs") == {"status": "absent", "matches": 0}      # identical string only
