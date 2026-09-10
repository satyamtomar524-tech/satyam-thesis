"""Build a local versioned successor from reviewed scope and evidence decisions.

No manuscript, workbook, historical calculation, or raw source is overwritten.
Detailed outputs stay in the ignored local directory; this script is shareable.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import date
from pathlib import Path

from apply_scope_amendments import apply_amendments
from date_sensitivity import analyse
from evidence_holds import apply_holds


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, content) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    historical = here.parent / "11_CORRECTION_REVIEW_V2"
    paths = {
        "rows": historical / "revised_decisions.json",
        "inputs": historical / "revision_inputs.json",
        "config": historical / "revision_config.json",
        "scope": here / "local/claim_scope_amendments.json",
        "holds": here / "local/evidence_hold_decisions.json",
        "engine": historical / "revision_calculations.py",
    }
    hashes = {key: digest(path) for key, path in paths.items()}
    data = {key: json.loads(path.read_text(encoding="utf-8"))
            for key, path in paths.items() if key != "engine"}
    scope, holds = data["scope"], data["holds"]
    rows = apply_amendments(data["rows"], scope["amendments"], scope["review_date"])
    rows = apply_holds(rows, holds["holds"], holds["review_date"])
    if [r["Link_ID"] for r in rows] != [r["Link_ID"] for r in data["rows"]]:
        raise AssertionError("Candidate identifiers/order changed")
    spec = importlib.util.spec_from_file_location("retained_revision_calculations", paths["engine"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print("Recalculating all retained network and sensitivity specifications", flush=True)
    calculation = module.calculate_all(root, rows, data["inputs"]["Link_Master_500"])
    calculation["input_revision"] = "FINALISATION_REVIEW_V3_20260910"
    calculation["engine_identity_note"] = "Internal CORRECTION_REVIEW_V2 labels identify the reusable calculation engine, not the input ledger. See input_revision and input_manifest."
    calculation["input_manifest"] = hashes
    dated = analyse(rows, data["inputs"]["Evidence_Log"],
                    date.fromisoformat(data["config"]["evidence_start"]),
                    date.fromisoformat(data["config"]["evidence_cutoff"]))
    dated["input_revision"] = calculation["input_revision"]
    dated["input_manifest"] = hashes
    # Independent topology implementation: no calculation-engine helper used.
    network = calculation["networks"]["N00"]
    topology = dated["non_temporal_primary"]
    mapping = {"claims": "link_n", "suppliers": "supplier_n", "categories": "grain_n",
               "memberships": "pair_n", "positive_overlap_pairs": "positive_edge_n",
               "possible_pairs": "possible_pair_n", "components": "component_n",
               "isolates": "isolate_n", "component_sizes": "component_sizes"}
    for independent_key, engine_key in mapping.items():
        left, right = topology[independent_key], network[engine_key]
        if independent_key == "component_sizes":
            left, right = sorted(left), sorted(right)
        if left != right:
            raise AssertionError(f"Independent topology disagrees: {independent_key}")
    for key, path in paths.items():
        if digest(path) != hashes[key]:
            raise AssertionError(f"Input changed: {key}")
    canonical = [r for r in rows if r["Canonical_Representative"] == 1]
    counts = {
        "candidate_rows": len(rows), "canonical_groups": len(canonical),
        "capability_supported": sum(r["Capability_Supported_Revised"] for r in canonical),
        "bmw_relationship_supported": sum(r["BMW_Relationship_Supported_Revised"] for r in canonical),
        "both_supported": sum(bool(r["Capability_Supported_Revised"] and r["BMW_Relationship_Supported_Revised"]) for r in canonical),
        "exact_bmw_technology": sum(r["Exact_BMW_Technology_Revised"] for r in canonical),
        "eligible_student_review_flags": sum(bool(r["Primary_Eligible"] and r["Needs_Student_Review"]) for r in rows),
    }
    out = here / "local/v3"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "revised_decisions.json", rows)
    write_json(out / "calculation_output.json", calculation)
    write_json(out / "date_sensitivity.json", dated)
    summary = {
        "input_revision": calculation["input_revision"], "input_sha256": hashes,
        "output_sha256": {name: digest(out / name) for name in
                          ("revised_decisions.json", "calculation_output.json", "date_sensitivity.json")},
        "inputs_unchanged": True, "scope_amendments": len(scope["amendments"]),
        "capability_holds": len(holds["holds"]), "register_counts": counts,
        "primary": topology, "recorded_date_restricted": dated["recorded_date_restricted"],
        "profile_counts": calculation["primary"]["profile_counts"],
        "sensitivity_run_count": len(calculation["sensitivity_runs"]),
        "independent_topology_agrees": True,
        "calculation_qa": calculation["qa"],
        "limitations": [
            "Not all source meanings or sensitivity calculations independently checked.",
            "Historical fields remain provenance, not current support decisions; use revised fields and audit deltas.",
            "Current live sources do not authenticate their historical content at the evidence cutoff.",
            "Manuscript, figures and workbooks still require integration; this is not submission-ready.",
            "Student understanding and personal review have not been confirmed.",
        ],
    }
    write_json(out / "recalculation_validation.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in
                      ("input_sha256", "output_sha256", "calculation_qa")}, indent=2))


if __name__ == "__main__":
    main()
