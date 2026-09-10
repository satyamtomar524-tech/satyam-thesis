"""Publication-window sensitivity using retained evidence, without editing inputs.

This is a post-review sensitivity, not a pre-specified historical analysis.
Recorded publication dates are not independently authenticated by this script.
Run with the bundled Python runtime; all dependencies are standard library.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path


def publication_interval(value: object) -> tuple[date, date] | None:
    """Preserve partial-date precision; never replace an unknown date with retrieval."""
    value = str(value or "").strip()
    if not re.fullmatch(r"\d{4}(?:-\d{2}){0,2}", value):
        return None
    try:
        parts = [int(part) for part in value.split("-")]
        year = parts[0]
        if len(parts) == 1:
            return date(year, 1, 1), date(year, 12, 31)
        month = parts[1]
        if len(parts) == 2:
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        day = date(*parts)
        return day, day
    except (ValueError, calendar.IllegalMonthError):
        return None


def date_class(value: object, start: date, cutoff: date, event_only: bool = False) -> str:
    if event_only:
        return "event_or_related_item_date_not_publication"
    interval = publication_interval(value)
    if interval is None:
        return "unknown_or_invalid"
    lower, upper = interval
    if start <= lower and upper <= cutoff:
        return "wholly_within_window"
    if upper < start or lower > cutoff:
        return "outside_window"
    return "interval_crosses_boundary"


def describe_network(rows: list[dict]) -> dict:
    """Category membership topology, independently derived from canonical claims."""
    ids = [row["Canonical_Link_ID"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate canonical claim in selected population")
    vectors = defaultdict(Counter)
    for row in rows:
        vectors[row["Supplier_ID"]][row["Analytical_Taxonomy_ID"]] += 1
    adjacency = {supplier: set() for supplier in vectors}
    for left, right in combinations(vectors, 2):
        # Positive weighted Jaccard is equivalent to a nonempty category intersection.
        if vectors[left].keys() & vectors[right].keys():
            adjacency[left].add(right)
            adjacency[right].add(left)
    remaining = set(vectors)
    sizes = []
    while remaining:
        todo = [min(remaining)]
        component = set()
        while todo:
            current = todo.pop()
            if current not in component:
                component.add(current)
                todo.extend(adjacency[current] - component)
        remaining -= component
        sizes.append(len(component))
    n = len(vectors)
    possible = n * (n - 1) // 2
    edges = sum(map(len, adjacency.values())) // 2
    return {
        "claims": len(rows), "suppliers": n,
        "categories": len({category for vector in vectors.values() for category in vector}),
        "memberships": sum(map(len, vectors.values())),
        "positive_overlap_pairs": edges, "possible_pairs": possible,
        "density": edges / possible if possible else None,
        "components": len(sizes), "component_sizes": sorted(sizes, reverse=True),
        "isolates": sum(not neighbors for neighbors in adjacency.values()),
        "single_category_suppliers": sum(len(vector) == 1 for vector in vectors.values()),
        "category_claim_counts": dict(sorted(Counter(
            row["Analytical_Taxonomy_ID"] for row in rows).items())),
        "origin_claim_counts": dict(sorted(Counter(row["Origin"] for row in rows).items())),
    }


def analyse(rows: list[dict], evidence: list[dict], start: date, cutoff: date) -> dict:
    evidence_by_id = {item["Evidence_ID"]: item for item in evidence}
    if len(evidence_by_id) != len(evidence):
        raise ValueError("Evidence identifiers are not unique")
    primary = [row for row in rows if row["Primary_Eligible"] == 1]
    dated = []
    decisions = []
    for row in primary:
        ids = row["Capability_Evidence_IDs"]
        if not isinstance(ids, list) or not ids:
            raise ValueError(f"Missing capability evidence for {row['Link_ID']}")
        event_only = (row.get("Publication_Date_Interpretation") == "event_date_not_publication"
                      or "publication_date_may_be_related_item_date" in row.get("Issue_Tags", []))
        classified = [{"evidence_id": eid, "recorded_date": evidence_by_id[eid].get("Published_Date"),
                       "classification": date_class(evidence_by_id[eid].get("Published_Date"),
                                                    start, cutoff, event_only)} for eid in ids]
        eligible = any(item["classification"] == "wholly_within_window" for item in classified)
        if eligible:
            dated.append(row)
        decisions.append({"link_id": row["Link_ID"], "date_restricted_eligible": eligible,
                          "capability_sources": classified})
    primary_suppliers = {row["Supplier_ID"] for row in primary}
    dated_suppliers = {row["Supplier_ID"] for row in dated}
    return {
        "specification": "Post-review recorded-publication-window sensitivity",
        "rule": "Retain an otherwise primary-eligible claim only if a selected capability source's entire recorded date interval falls within the window and is not flagged as an event or related-item date.",
        "window": {"start": start.isoformat(), "cutoff": cutoff.isoformat()},
        "non_temporal_primary": describe_network(primary),
        "recorded_date_restricted": describe_network(dated),
        "common_suppliers": len(primary_suppliers & dated_suppliers),
        "claim_retention": len(dated) / len(primary) if primary else None,
        "date_decisions": decisions,
        "limitations": [
            "Date values and source interpretations are retained review inputs, not fresh authentication of publication metadata.",
            "Later retrieval does not prove that the same content was online at the historical cutoff.",
            "The restricted sample is selected by publication-date availability and is not a less biased population estimate.",
            "Density changes have different supplier-pair denominators; they are specification contrasts, not temporal trends.",
            "This run describes topology only and does not estimate supplier profiles or a visibility-complexity association.",
            "Both populations remain subject to source, identity, taxonomy and distinctness review.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    source = args.root / "04_ANALYSIS/11_CORRECTION_REVIEW_V2"
    paths = [source / name for name in ("revised_decisions.json", "revision_inputs.json", "revision_config.json")]
    before = {str(path.relative_to(args.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    rows, inputs, config = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    result = analyse(rows, inputs["Evidence_Log"], date.fromisoformat(config["evidence_start"]),
                     date.fromisoformat(config["evidence_cutoff"]))
    result["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["input_sha256"] = before
    result["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    after = {str(path.relative_to(args.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    if before != after:
        raise RuntimeError("Input changed during analysis")
    result["inputs_unchanged"] = True
    out = args.root / "04_ANALYSIS/12_FINALISATION_20260910/local"
    out.mkdir(parents=True, exist_ok=True)
    (out / "date_sensitivity.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"date_decisions", "input_sha256"}}, indent=2))


if __name__ == "__main__":
    main()
