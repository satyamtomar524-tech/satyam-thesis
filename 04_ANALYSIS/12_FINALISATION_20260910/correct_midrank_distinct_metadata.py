"""Versioned metadata-only correction for exact weighted-midrank distinct counts.

This does not change the retained calculation engine, scores, thresholds,
profiles or source data. It reconstructs rational midrank Embeddedness scores
from retained exact/high-precision raw indicators, validates displayed values,
and changes only dimension_summary.Embeddedness.distinct_n in an in-memory
successor. The CLI writes a hash-bound supplementary patch, not the full data.
The production engine's Decimal tie-representation limitation remains until a
separately validated algorithm successor is implemented; frozen engines remain preserved.
"""
from __future__ import annotations

import argparse
import copy
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any


def exact_midranks(values: dict[str, Any]) -> dict[str, Fraction] | None:
    """Average tied ranks on a 0–100 scale; constants have no usable transform."""
    if len(set(values.values())) <= 1:
        return None
    n = len(values)
    return {key: Fraction(100, n - 1) * (
        sum(other < value for other in values.values())
        + Fraction(sum(other == value for other in values.values()) - 1, 2))
        for key, value in values.items()}


def tree_changes(before: Any, after: Any, path: tuple = ()) -> list[dict]:
    """Return every changed leaf; changes in topology/type are explicit too."""
    if type(before) is not type(after):
        return [{"path": list(path), "before": before, "after": after}]
    if isinstance(before, dict):
        if set(before) != set(after):
            return [{"path": list(path), "before": before, "after": after}]
        return [change for key in before for change in tree_changes(before[key], after[key], path + (key,))]
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": list(path), "before": before, "after": after}]
        return [change for i, value in enumerate(before) for change in tree_changes(value, after[i], path + (i,))]
    return [] if before == after else [{"path": list(path), "before": before, "after": after}]


def _raw_number(value: str) -> Fraction | Decimal:
    return Fraction(value) if "/" in value else Decimal(value)


def _display_agrees(actual: Fraction | None, stored: Any) -> bool:
    if actual is None or stored is None:
        return actual is stored
    return math.isclose(float(actual), float(stored), abs_tol=1e-12, rel_tol=1e-12)


def corrected_metadata(payload: dict, run_ids: set[str]) -> tuple[dict, dict]:
    """Return a deep-copied successor and receipt; input is never mutated.

    Primary is included when its run_id is selected. Explicit run selection
    prevents this diagnostic correction from expanding into unreviewed runs.
    """
    successor = copy.deepcopy(payload)
    selected = []
    if payload["primary"]["run_id"] in run_ids:
        selected.append((("primary",), payload["primary"], successor["primary"]))
    for index, run in enumerate(payload["sensitivity_runs"]):
        if run["run_id"] in run_ids:
            selected.append((("sensitivity_runs", index), run, successor["sensitivity_runs"][index]))
    found = {run["run_id"] for _, run, _ in selected}
    if found != run_ids:
        raise ValueError(f"Unknown selected runs: {sorted(run_ids - found)}")
    checked, skipped, allowed = [], [], set()
    names = [("Strength", "Strength_Transformed", "Strength_Exact_or_High_Precision"),
             ("Normalized_Betweenness", "Betweenness_Transformed", "Normalized_Betweenness_Exact_or_High_Precision")]
    for prefix, run, destination in selected:
        if run["transformation"] != "midrank_percentile":
            skipped.append({"path": list(prefix), "run_id": run["run_id"], "reason": "Non-midrank transformation; no correction authorized by this method."})
            continue
        raw_rows = payload["networks"][run["network_spec_id"]]["supplier_rows"]
        raw_by_id = {row["Supplier_ID"]: row for row in raw_rows}
        if len(raw_by_id) != len(raw_rows):
            raise ValueError("Duplicate network supplier IDs")
        suppliers = {row["Supplier_ID"]: row for row in run["supplier_rows"]}
        if len(suppliers) != len(run["supplier_rows"]) or set(suppliers) != set(raw_by_id):
            raise ValueError("Run/network supplier populations do not agree")
        requested = [Fraction(str(value)) for value in run["requested_embeddedness_weights"]]
        if len(requested) != 2 or any(w < 0 for w in requested) or sum(requested) <= 0:
            raise ValueError("Invalid requested Embeddedness weights")
        transformed = {}
        for name, displayed, raw_field in names:
            values = {s: _raw_number(row[raw_field]) for s, row in raw_by_id.items()}
            ranks = exact_midranks(values)
            transformed[name] = ranks
            if bool(run["zero_variance"][name]) != (ranks is None):
                raise ValueError(f"Constant-indicator disagreement: {run['run_id']} {name}")
            if not all(_display_agrees(None if ranks is None else ranks[s], suppliers[s][displayed]) for s in suppliers):
                raise ValueError(f"Stored transformed indicator disagreement: {run['run_id']} {name}")
        usable = [(name, weight) for (name, _, _), weight in zip(names, requested)
                  if transformed[name] is not None and name != run["remove_indicator"]]
        total = sum((weight for _, weight in usable), Fraction(0))
        if usable and total <= 0:
            raise ValueError("Remaining indicators have no positive weight")
        effective = {name: weight / total for name, weight in usable}
        if set(effective) != set(run["effective_weights"]["Embeddedness"]) or not all(
            _display_agrees(weight, run["effective_weights"]["Embeddedness"][name]) for name, weight in effective.items()):
            raise ValueError("Stored effective weights disagree with selected policy")
        scores = None if not usable else {s: sum((weight * transformed[name][s] for name, weight in effective.items()), Fraction(0)) for s in suppliers}
        if not all(_display_agrees(None if scores is None else scores[s], suppliers[s]["Embeddedness_Score"]) for s in suppliers):
            raise ValueError("Exact weighted-midrank score does not match stored display")
        expected = 0 if scores is None else len(set(scores.values()))
        path = prefix + ("dimension_summary", "Embeddedness", "distinct_n")
        before = run["dimension_summary"]["Embeddedness"]["distinct_n"]
        if not isinstance(before, int) or isinstance(before, bool):
            raise ValueError("Distinct count must be an integer")
        destination["dimension_summary"]["Embeddedness"]["distinct_n"] = expected
        allowed.add(path)
        checked.append({"path": list(path), "run_id": run["run_id"], "before": before, "after": expected,
                        "supplier_n": len(suppliers), "displayed_scores_verified_unchanged": True})
    changes = tree_changes(payload, successor)
    if any(tuple(change["path"]) not in allowed for change in changes):
        raise AssertionError("A field outside the metadata whitelist changed")
    receipt = {"schema": "exact_midrank_distinct_metadata/1.0", "selected_run_ids": sorted(run_ids),
        "checked_records": checked, "skipped_records": skipped, "corrections": changes,
        "full_tree_comparison": {"only_allowed_distinct_n_leaves_changed": True, "changed_leaf_count": len(changes),
            "all_scores_profiles_thresholds_and_other_fields_unchanged": True},
        "method": "Exact rational pairwise midranks and rational normalized requested weights; distinct exact Embeddedness scores.",
        "production_engine_changed": False,
        "remaining_limitation": "The production engine still performs Decimal weighted-score arithmetic and may reproduce split-tie distinct counts on rerun. Apply this hash-bound metadata supplement to the specified inputs only; resolve the underlying arithmetic through a separately validated algorithm successor while preserving the frozen engine."}
    return successor, receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New supplementary correction JSON, not full analytical data")
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--run-ids", nargs="+", required=True)
    args = parser.parse_args()
    before = args.input.read_bytes()
    actual_hash = sha256(before).hexdigest()
    if actual_hash != args.expected_input_sha256.lower():
        raise ValueError("Input hash does not match the authorized analytical version")
    if args.output.exists() or args.output.resolve() == args.input.resolve():
        raise FileExistsError("Output must be a new distinct supplementary file")
    payload = json.loads(before)
    _, receipt = corrected_metadata(payload, set(args.run_ids))
    receipt.update(input_path=str(args.input), input_sha256=actual_hash,
                   script_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    if args.input.read_bytes() != before:
        raise RuntimeError("Input changed during validation")
    receipt["input_file_unchanged"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output.read_bytes()).hexdigest(),
                      "changed_leaf_count": len(receipt["corrections"])}))


if __name__ == "__main__":
    main()
