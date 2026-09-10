"""Apply reviewed wording amendments to a new local ledger, preserving all input fields.

The local amendment file is deliberately excluded from Git. This operation cannot
change eligibility, source dates, identities, evidence flags or canonical groups.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


def apply_amendments(rows: list[dict], amendments: list[dict], review_date: str) -> list[dict]:
    updated = copy.deepcopy(rows)
    by_id = {row["Link_ID"]: row for row in updated}
    if len(by_id) != len(rows):
        raise ValueError("Original link IDs are not unique")
    applied = set()
    for amendment in amendments:
        identifier = amendment["Link_ID"]
        if identifier in applied:
            raise ValueError("Duplicate amendment identifier")
        row = by_id[identifier]
        if row["Analytical_Technology_EN"] != amendment["expected_technology"]:
            raise ValueError(f"Source wording changed for {identifier}; re-review before applying")
        row["Analytical_Technology_EN"] = amendment["technology"]
        row["Finalisation_Scope_Review"] = {
            "review_date": review_date, "source_url": amendment["source_url"],
            "source_locator": amendment["source_locator"], "reason": amendment["reason"],
            "paired_record": amendment["paired_record"], "status": amendment["review_status"],
            "student_review_confirmed": False,
        }
        applied.add(identifier)
    for before, after in zip(rows, updated):
        # Only the derived wording and a new dated audit field may differ.
        restored = {key: value for key, value in after.items() if key != "Finalisation_Scope_Review"}
        restored["Analytical_Technology_EN"] = before["Analytical_Technology_EN"]
        if restored != before:
            raise AssertionError("An unrelated input field changed")
    return updated


def main() -> None:
    here = Path(__file__).resolve().parent
    source = here.parent / "11_CORRECTION_REVIEW_V2/revised_decisions.json"
    amendments_path = here / "local/claim_scope_amendments.json"
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    rows = json.loads(source.read_text(encoding="utf-8"))
    package = json.loads(amendments_path.read_text(encoding="utf-8"))
    output = apply_amendments(rows, package["amendments"], package["review_date"])
    target = here / "local/revised_decisions_scope_clarified.json"
    target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if hashlib.sha256(source.read_bytes()).hexdigest() != before_hash:
        raise AssertionError("Historical decision ledger changed")
    manifest = {
        "source_sha256": before_hash, "amendments_sha256": hashlib.sha256(amendments_path.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "records_retained": len(output), "wording_amendments": len(package["amendments"]),
        "all_other_original_fields_unchanged": True,
        "numerical_inputs_unchanged": True, "manuscript_and_workbooks_not_yet_integrated": True,
    }
    (here / "local/scope_amendments_validation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
