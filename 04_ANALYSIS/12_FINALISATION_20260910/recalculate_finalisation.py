"""Build a local versioned successor from reviewed scope and evidence decisions.

No manuscript, workbook, historical calculation, or raw source is overwritten.
Detailed outputs stay in the ignored local directory; this script is shareable.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from apply_scope_amendments import apply_amendments
from date_sensitivity import analyse
from evidence_holds import apply_holds
from distinctness_holds import apply_distinctness_holds
from apply_reviewed_corrections import apply_reviewed_corrections


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, content) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def semantic_json_digest(content) -> str:
    """Compare JSON content without changing historical output serialization."""
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", choices=("v3", "v4", "v5"), default="v4")
    parser.add_argument("--output", type=Path,
                        help="New directory under this finalisation folder's ignored local/ tree. "
                             "Relative paths resolve from the current directory. Existing paths are never overwritten.")
    return parser


def resolve_output(here: Path, revision: str, requested: Path | None) -> Path:
    private_root = (here / "local").resolve()
    candidate = requested if requested is not None else private_root / revision
    if candidate.is_symlink():
        raise FileExistsError(f"Refusing an existing symbolic-link output path: {candidate}")
    output = candidate.resolve()
    if output == private_root or not output.is_relative_to(private_root):
        raise ValueError(f"Output must be a new directory beneath the ignored local tree: {private_root}")
    for frozen_revision in ("v3", "v4", "v5"):
        frozen = private_root / frozen_revision
        if output != frozen and output.is_relative_to(frozen):
            raise ValueError(f"Output must not be placed inside a frozen revision: {frozen}")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite an existing output or frozen revision: {output}")
    return output


def code_dependencies(here: Path) -> list[Path]:
    """Complete source closure imported by the V5 CLI, including historical imports."""
    return [here / f"{name}.py" for name in (
        "recalculate_finalisation", "apply_scope_amendments", "date_sensitivity",
        "evidence_holds", "distinctness_holds", "apply_reviewed_corrections",
    )] + [here.parent / "11_CORRECTION_REVIEW_V2/revision_calculations.py",
          here.parent / "05_NETWORK_ANALYSIS/C3_construct_network.py",
          here.parent / "07_SENSITIVITY_ANALYSIS/C5_run_sensitivity_tests.py"]


def main() -> None:
    args = argument_parser().parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[1]
    historical = here.parent / "11_CORRECTION_REVIEW_V2"
    out = resolve_output(here, args.revision, args.output)
    started_utc = datetime.now(timezone.utc).isoformat()
    started_clock = time.monotonic()
    code_hashes = {path.relative_to(root).as_posix(): digest(path) for path in code_dependencies(here)}
    paths = {
        "rows": historical / "revised_decisions.json",
        "inputs": historical / "revision_inputs.json",
        "config": historical / "revision_config.json",
        "scope": here / "local/claim_scope_amendments.json",
        "holds": here / "local/evidence_hold_decisions.json",
        "engine": historical / "revision_calculations.py",
    }
    if args.revision == "v4":
        paths["distinctness"] = here / "local/distinctness_hold_decisions.json"
    if args.revision == "v5":
        paths['rows'] = here / 'local/v4/revised_decisions.json'
        paths['corrections'] = here / 'local/semantic_review_20260911/reviewed_corrections_v5.json'
        del paths['scope'], paths['holds']
    hashes = {key: digest(path) for key, path in paths.items()}
    data = {key: json.loads(path.read_text(encoding="utf-8"))
            for key, path in paths.items() if key != "engine"}
    scope, holds = data.get('scope', {'amendments': []}), data.get('holds', {'holds': []})
    if args.revision == 'v5':
        correction = data['corrections']
        if correction['input_ledger_sha256'] != hashes['rows'] or correction['inputs_sha256'] != hashes['inputs']:
            raise ValueError('Source corrections are not bound to these frozen inputs')
        for item in correction['required_files']:
            if digest(root / item['path']) != item['sha256']:
                raise ValueError(f"Changed review evidence: {item['path']}")
        rows = apply_reviewed_corrections(data['rows'], correction)
    else:
        rows = apply_amendments(data["rows"], scope["amendments"], scope["review_date"])
        rows = apply_holds(rows, holds["holds"], holds["review_date"])
    if "distinctness" in data:
        rows = apply_distinctness_holds(rows, data["distinctness"]["holds"], data["distinctness"]["review_date"])
    if [r["Link_ID"] for r in rows] != [r["Link_ID"] for r in data["rows"]]:
        raise AssertionError("Candidate identifiers/order changed")
    spec = importlib.util.spec_from_file_location("retained_revision_calculations", paths["engine"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print("Recalculating all retained network and sensitivity specifications", flush=True)
    calculation = module.calculate_all(root, rows, data["inputs"]["Link_Master_500"])
    revision_date = '20260912' if args.revision == 'v5' else '20260910'
    calculation["input_revision"] = f"FINALISATION_REVIEW_{args.revision.upper()}_{revision_date}"
    if args.revision == 'v5':
        calculation['supplier_identity_note'] = 'Supplier_ID is the reconciled analytical entity key. Source_Supplier_ID preserves the frozen key for evidence joins. Original Link_ID and canonical claim groups are unchanged; entity-key reconciliation is not claim deduplication.'
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
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "revised_decisions.json", rows)
    write_json(out / "calculation_output.json", calculation)
    write_json(out / "date_sensitivity.json", dated)
    summary = {
        "input_revision": calculation["input_revision"], "input_sha256": hashes,
        "output_sha256": {name: digest(out / name) for name in
                          ("revised_decisions.json", "calculation_output.json", "date_sensitivity.json")},
        "inputs_unchanged": True, "scope_amendments": len(scope["amendments"]),
        "distinctness_holds_added": len(data.get("distinctness", {}).get("holds", [])),
        "capability_holds": len(holds["holds"]), "register_counts": counts,
        "primary": topology, "recorded_date_restricted": dated["recorded_date_restricted"],
        "profile_counts": calculation["primary"]["profile_counts"],
        "sensitivity_run_count": len(calculation["sensitivity_runs"]),
        "independent_topology_agrees": True,
        "source_corrections": len(data.get('corrections', {}).get('corrections', [])),
        "supplier_aliases": len(data.get('corrections', {}).get('supplier_aliases', [])),
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
    for relative, expected in code_hashes.items():
        if digest(root / relative) != expected:
            raise AssertionError(f"Code changed during execution: {relative}")
    output_names = ("revised_decisions.json", "calculation_output.json", "date_sensitivity.json",
                    "recalculation_validation.json")
    # Separate execution metadata avoids changing the identity of the frozen
    # calculation payloads. Raw hashes and canonical-content hashes serve
    # different purposes; dictionary insertion order can alter only the former.
    write_json(out / "execution_receipt.json", {
        "input_revision": calculation["input_revision"],
        "started_utc": started_utc, "finished_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - started_clock,
        "output_directory": str(out), "code_sha256": code_hashes,
        "code_unchanged_during_execution": True, "input_sha256": hashes,
        "runtime": {"python": sys.version, "python_executable": sys.executable,
                    "platform": platform.platform(), "openpyxl": importlib.metadata.version("openpyxl")},
        "output_sha256": {name: digest(out / name) for name in output_names},
        "semantic_json_sha256": {name: semantic_json_digest(content) for name, content in (
            ("revised_decisions.json", rows), ("calculation_output.json", calculation),
            ("date_sensitivity.json", dated))},
        "semantic_hash_method": "SHA-256 of UTF-8 json.dumps with sorted keys, compact separators, "
                                "ensure_ascii=False and allow_nan=False; no historical file is rewritten.",
        "limitations": ["Execution provenance and content comparison, not independent source verification.",
                        "A matching semantic hash does not imply byte-identical serialization.",
                        "The historical V5 figure builder still pins frozen raw input hashes and cannot "
                        "automatically consume a byte-different, content-equivalent rerun."],
    })
    print(json.dumps({k: v for k, v in summary.items() if k not in
                      ("input_sha256", "output_sha256", "calculation_qa")}, indent=2))


if __name__ == "__main__":
    main()
