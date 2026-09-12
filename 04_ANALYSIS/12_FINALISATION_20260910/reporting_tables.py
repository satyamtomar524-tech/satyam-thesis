"""Pure reporting summaries with explicit canonical and primary denominators.

No files are opened and no row-level identifiers are returned by evidence_views.
Capability and customer-relationship flags are independent, not an ordinal scale.
"""
from collections import Counter


def percent(n, denominator, digits=2):
    return f"{100 * n / denominator:.{digits}f}%" if denominator else "Not estimable"


def evidence_views(rows, taxonomy):
    canonical = [r for r in rows if r["Canonical_Representative"] == 1]
    if len({r["Canonical_Link_ID"] for r in canonical}) != len(canonical):
        raise ValueError("Canonical representatives must have unique counting identifiers")
    primary = [r for r in rows if r["Primary_Eligible"] == 1]
    if any(r["Canonical_Representative"] != 1 for r in primary):
        raise ValueError("Primary claims must be canonical representatives")
    flags = ("Capability_Supported_Revised", "BMW_Relationship_Supported_Revised",
             "Exact_BMW_Technology_Revised")
    if any(r[f] not in (0, 1) for r in canonical for f in flags):
        raise ValueError("Support flags must be binary")
    combinations = [(1, 1), (1, 0), (0, 1), (0, 0)]
    labels = ["Both supported", "Capability only", "BMW relationship only", "Neither established"]
    partition = Counter((r[flags[0]], r[flags[1]]) for r in canonical)
    composition = Counter(r["Analytical_Taxonomy_ID"] for r in primary)
    category_rows = []
    for tax in sorted(taxonomy):
        selected = [r for r in canonical if r["Analytical_Taxonomy_ID"] == tax]
        if not selected:
            continue
        parts = Counter((r[flags[0]], r[flags[1]]) for r in selected)
        category_rows.append({
            "id": tax, "label": taxonomy[tax]["category"], "canonical_n": len(selected),
            "primary_n": composition[tax],
            "capability_n": sum(r[flags[0]] for r in selected),
            "bmw_n": sum(r[flags[1]] for r in selected),
            "exact_n": sum(r[flags[2]] for r in selected),
            "partition": [parts[c] for c in combinations],
        })
    if sum(r["canonical_n"] for r in category_rows) != len(canonical):
        raise ValueError("Every canonical claim must have a declared taxonomy state")
    return {
        "candidate_n": len(rows), "canonical_n": len(canonical), "primary_n": len(primary),
        "partition_labels": labels, "partition": [partition[c] for c in combinations],
        "capability_n": sum(r[flags[0]] for r in canonical),
        "bmw_n": sum(r[flags[1]] for r in canonical),
        "exact_n": sum(r[flags[2]] for r in canonical),
        "categories": category_rows,
    }


def agreement_label(run):
    """Never turn a diagnostic subset or missing full profile into overall accuracy."""
    st = run["stability"]
    n = st["profile_comparison_n"]
    if not n:
        return "Not estimable"
    same = st["same_profile_n"]
    if not 0 <= same <= n <= st["common_supplier_n"]:
        raise ValueError("Invalid profile agreement denominator")
    return f"{same}/{n} ({percent(same, n)})"
