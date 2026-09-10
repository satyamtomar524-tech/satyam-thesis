"""Versioned conservative evidence holds; never upgrade support or alter raw sources.

The caller supplies a reviewed, local-only decision manifest. A hold preserves the
candidate and historical evidence, but stops unsupported capability from entering
the primary analysis. Review timestamps are not publication dates.
"""
from __future__ import annotations

import copy
import hashlib
import json


def record_digest(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def apply_holds(rows: list[dict], holds: list[dict], review_date: str) -> list[dict]:
    output = copy.deepcopy(rows)
    lookup = {row["Link_ID"]: row for row in output}
    if len(lookup) != len(output):
        raise ValueError("Duplicate input Link_ID")
    seen = set()
    for hold in holds:
        identifier = hold["Link_ID"]
        if identifier in seen:
            raise ValueError("Duplicate hold")
        seen.add(identifier)
        row = lookup[identifier]
        if record_digest(row) != hold["expected_record_sha256"]:
            raise ValueError(f"Stale review for {identifier}")
        if row["Capability_Supported_Revised"] != 1 or row["Primary_Eligible"] != 1:
            raise ValueError("This operation requires a currently supported primary claim")
        if row["Exact_BMW_Technology_Revised"] or row["BMW_Relationship_Supported_Revised"]:
            raise ValueError("Relationship-supported claims require separate joint review")
        for key in ("reason", "source_url", "source_locator", "search_scope"):
            if not str(hold.get(key, "")).strip():
                raise ValueError(f"Missing review evidence: {key}")
        before = copy.deepcopy(row)
        reason = hold["reason"]
        row.update({
            "Capability_Status": "unresolved",
            "Capability_Match": "not_established_for_exact_candidate",
            "Capability_Evidence_IDs": [],
            "Capability_Supported_Revised": 0,
            "Primary_Eligible": 0,
            "Eligibility_Requirements_Met": 0,
            "Eligibility_Status": "held_insufficient_process_specific_evidence",
            "Eligibility_Reason": reason,
            "Analytical_Technology_EN": hold["candidate_label"],
            "Decision_Reason": reason,
            "Capability_Decision_Reason": reason,
            "BMW_Relationship_Decision_Reason": "No qualifying BMW relationship established; unchanged by capability hold.",
            "Exact_BMW_Technology_Decision_Reason": "No exact BMW technology association established; unchanged by capability hold.",
            "Taxonomy_Reason": "Category retained for the candidate only, not as proof of capability. " + reason,
            "Review_Status": "live_source_review_capability_held",
            "Review_Date": review_date,
            "Source_Recheck_Status": "reopened_exact_capability_not_established",
            "Source_Recheck_Date": review_date,
            "Source_Recheck_URLs": [hold["source_url"]],
            "Needs_Student_Review": True,
            "Issue_Tags": sorted(set(row["Issue_Tags"] + ["process_specific_capability_not_established"])),
        })
        # Legacy source fields stay untouched. The audit gives the exact effective
        # delta so downstream authoring cannot confuse old claims with decisions.
        changes = {key: {"before": before.get(key), "after": value}
                   for key, value in row.items() if before.get(key) != value}
        row["Finalisation_Evidence_Hold"] = {
            "review_date": review_date, "reason": reason,
            "source_url": hold["source_url"], "source_locator": hold["source_locator"],
            "search_scope": hold["search_scope"],
            "original_record_sha256": hold["expected_record_sha256"],
            "previous_capability_evidence_ids": before["Capability_Evidence_IDs"],
            "changes": changes, "student_review_confirmed": False,
            "interpretation": "Support not established; not evidence of absent capability.",
        }
        if row["Non_Excluded_Revised"] != before["Non_Excluded_Revised"]:
            raise AssertionError("Candidate-register retention changed")
    return output
