"""Hold a supported umbrella claim's additional weight without erasing its evidence."""
import copy

from evidence_holds import record_digest


def apply_distinctness_holds(rows, decisions, review_date):
    output = copy.deepcopy(rows)
    by_id = {r["Link_ID"]: r for r in output}
    if len(by_id) != len(output):
        raise ValueError("Duplicate input identifiers")
    seen = set()
    for decision in decisions:
        identifier, retained_id = decision["Link_ID"], decision["retained_narrower_Link_ID"]
        if identifier in seen:
            raise ValueError("Duplicate distinctness decision")
        seen.add(identifier)
        row, narrower = by_id[identifier], by_id[retained_id]
        if record_digest(row) != decision["expected_record_sha256"]:
            raise ValueError("Stale distinctness review")
        if not row["Primary_Eligible"] or not narrower["Primary_Eligible"]:
            raise ValueError("Both reviewed claims must initially be primary eligible")
        if row["Supplier_ID"] != narrower["Supplier_ID"] or row["Analytical_Taxonomy_ID"] != narrower["Analytical_Taxonomy_ID"]:
            raise ValueError("This operation requires same-supplier same-category claims")
        if identifier == retained_id:
            raise ValueError("A claim cannot overlap itself")
        for key in ("reason", "source_urls", "source_locator"):
            if not decision.get(key):
                raise ValueError("Missing distinctness evidence")
        before = copy.deepcopy(row)
        row.update({
            "Distinctness_Status": "unresolved_overlap",
            "Distinctness_Reason": decision["reason"],
            "Primary_Eligible": 0,
            "Eligibility_Status": "held_unresolved_umbrella_overlap",
            "Eligibility_Reason": "Capability remains supported; additional umbrella claim-count weight held. " + decision["reason"],
            "Needs_Student_Review": True,
            "Review_Date": review_date,
            "Source_Recheck_Date": review_date,
            "Source_Recheck_Status": "reopened_capability_supported_distinctness_held",
            "Source_Recheck_URLs": decision["source_urls"],
            "Issue_Tags": sorted(set(row["Issue_Tags"] + ["unresolved_umbrella_overlap"])),
        })
        # Eligibility_Requirements_Met records capability/identity/category support
        # in the retained model; the separate distinctness gate controls inclusion.
        row["Finalisation_Distinctness_Hold"] = {
            "review_date": review_date, "retained_narrower_Link_ID": retained_id,
            "reason": decision["reason"], "source_urls": decision["source_urls"],
            "source_locator": decision["source_locator"],
            "previous_record_sha256": decision["expected_record_sha256"],
            "changes": {k: {"before": before.get(k), "after": v}
                        for k, v in row.items() if before.get(k) != v},
            "student_review_confirmed": False,
            "not_a_duplicate_merger": True,
        }
        for key in ("Capability_Status", "Capability_Supported_Revised", "BMW_Relationship_Status",
                    "BMW_Relationship_Supported_Revised", "Exact_BMW_Technology_Revised",
                    "Capability_Evidence_IDs", "BMW_Evidence_IDs", "Canonical_Link_ID"):
            if row[key] != before[key]:
                raise AssertionError("Distinctness hold altered support or identity")
    return output
