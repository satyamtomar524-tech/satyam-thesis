"""Pure calculations for the versioned thesis evidence correction.

Public API
----------
calculate_all(root: Path, revised_rows: list[dict], frozen_rows: list[dict])
    returns JSON-serializable populations, networks, profiles, sensitivities,
    old/new comparisons and independently computed checks. It writes nothing.
render_network(payload: dict, outdir: Path, *, replace: bool = False)
    explicitly writes a PNG/SVG only beneath this module's revision directory.

Historical C3/C5 modules supply input-only mathematical helpers. Their fixed
input orchestration functions are never called and their globals are never
modified. Old numerical constants occur only in the labelled baseline fixture.
Revised evidence flags are supplied by the evidence-review orchestrator; this
module neither verifies sources nor infers capability from a P1 code.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import statistics
import types
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, Callable


REVISION_ID = "CORRECTION_REVIEW_V2"
PROFILE_ORDER = ["concentrated / peripheral", "concentrated / embedded",
                 "diversified / peripheral", "diversified / embedded"]
FLAGS = ("Canonical_Representative", "Capability_Supported_Revised",
         "BMW_Relationship_Supported_Revised", "Exact_BMW_Technology_Revised",
         "Non_Excluded_Revised", "Identity_Resolved_Revised", "Primary_Eligible")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _flag(row: dict, name: str) -> bool:
    value = row.get(name)
    if value not in (0, 1, False, True):
        raise ValueError(f"{row.get('Link_ID')}: {name} must be an explicit binary flag")
    return bool(value)


def _helpers(root: Path) -> tuple[Any, Any, dict]:
    """Load source without creating __pycache__ or executing its main runner."""
    modules, hashes = [], {}
    for label, relative in [
        ("c3", "04_ANALYSIS/05_NETWORK_ANALYSIS/C3_construct_network.py"),
        ("c5", "04_ANALYSIS/07_SENSITIVITY_ANALYSIS/C5_run_sensitivity_tests.py"),
    ]:
        path = root / relative
        source = path.read_bytes()
        module = types.ModuleType(f"{REVISION_ID}_{label}")
        module.__file__ = str(path)
        exec(compile(source, str(path), "exec"), module.__dict__)
        modules.append(module)
        hashes[relative] = hashlib.sha256(source).hexdigest().upper()
    return modules[0], modules[1], hashes


def _plain(value: Any) -> Any:
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, set):
        return [_plain(v) for v in sorted(value)]
    return value


def _taxonomy(frozen_rows: list[dict]) -> dict[str, dict[str, str]]:
    mapping = {}
    for row in frozen_rows:
        key = _text(row.get("Taxonomy_ID"))
        item = {"family": _text(row.get("Technology_Family")),
                "category": _text(row.get("Technology_Category"))}
        if key == "TAX-18":
            # The frozen manual-review bucket spans inconsistent source
            # family labels. Its artificial sensitivity group is explicitly
            # unresolved; it never becomes a controlled primary category.
            item = {"family": "Unresolved taxonomy", "category": "other_needs_review"}
        if key in mapping and mapping[key] != item:
            raise ValueError(f"Frozen taxonomy metadata conflict for {key}")
        if key:
            mapping[key] = item
    return mapping


def _prepare(revised: list[dict], frozen: list[dict]) -> tuple[list[dict], dict]:
    frozen_by_id = {_text(r.get("Link_ID")): r for r in frozen}
    revised_ids = [_text(r.get("Link_ID")) for r in revised]
    if "" in revised_ids or len(revised_ids) != len(set(revised_ids)):
        raise ValueError("Revised audit rows need unique populated original Link_ID values")
    if set(revised_ids) != set(frozen_by_id) or len(frozen_by_id) != len(frozen):
        raise ValueError("The revised audit ledger must retain every original Link_ID exactly once")
    taxonomy = _taxonomy(frozen)
    prepared, groups = [], defaultdict(list)
    for original in revised:
        row = dict(original)
        for field in FLAGS:
            _flag(row, field)
        for field in ("Supplier_ID", "Canonical_Link_ID", "Analytical_Taxonomy_ID"):
            if not _text(row.get(field)):
                raise ValueError(f"{row['Link_ID']}: missing {field}")
        canonical = _text(row["Canonical_Link_ID"])
        tax = _text(row["Analytical_Taxonomy_ID"])
        row["_canonical"] = canonical
        row["_tax"] = tax
        row["_family"] = _text(row.get("Analytical_Technology_Family")) or taxonomy.get(tax, {}).get("family", "")
        row["_category"] = _text(row.get("Analytical_Technology_Category")) or taxonomy.get(tax, {}).get("category", tax)
        row["_controlled"] = tax in taxonomy and tax != "TAX-18"
        if _flag(row, "Primary_Eligible") and not (
            _flag(row, "Canonical_Representative")
            and _flag(row, "Capability_Supported_Revised")
            and _flag(row, "Identity_Resolved_Revised")
            and _flag(row, "Non_Excluded_Revised") and row["_controlled"]
            and row.get("Distinctness_Status") != "unresolved_overlap"
        ):
            raise ValueError(f"{row['Link_ID']}: Primary_Eligible contradicts required revised flags")
        # Exact technology evidence entails both constituent claims for the
        # same unit. BMW relationship alone intentionally does not imply capability.
        if _flag(row, "Exact_BMW_Technology_Revised") and not (
            _flag(row, "Capability_Supported_Revised")
            and _flag(row, "BMW_Relationship_Supported_Revised")
            and _flag(row, "Identity_Resolved_Revised")
        ):
            raise ValueError(f"{row['Link_ID']}: exact evidence lacks capability, BMW or resolved-entity support")
        prepared.append(row)
        groups[canonical].append(row)
    for canonical, members in groups.items():
        if sum(_flag(r, "Canonical_Representative") for r in members) != 1:
            raise ValueError(f"Canonical group {canonical} needs exactly one representative")
        if len({(_text(r['Supplier_ID']), r['_tax']) for r in members}) != 1:
            raise ValueError(f"Canonical group {canonical} has incompatible supplier/taxonomy units")
        ids = sorted(_text(r["Link_ID"]) for r in members)
        for row in members:
            row["_provenance_links"] = ids
    return prepared, taxonomy


def _select(rows: list[dict], predicate: Callable[[dict], bool]) -> list[dict]:
    """Filter first, then choose one eligible record per canonical claim."""
    selected = {}
    ordered = sorted(rows, key=lambda r: (not _flag(r, "Canonical_Representative"), _text(r["Link_ID"])))
    for row in ordered:
        if predicate(row):
            selected.setdefault(row["_canonical"], row)
    return [selected[k] for k in sorted(selected)]


def _network(c3: Any, c5: Any, spec: str, population: str, rows: list[dict],
             grain: str = "_tax", method: str = "weighted_jaccard", binary: bool = False) -> dict:
    pair_claims, pair_provenance = defaultdict(set), defaultdict(set)
    info = {}
    seen = set()
    for row in rows:
        key = row["_canonical"]
        if key in seen:
            raise ValueError(f"Duplicate canonical claim in {spec}: {key}")
        seen.add(key)
        supplier, category = _text(row["Supplier_ID"]), _text(row[grain])
        if not supplier or not category:
            raise ValueError(f"Missing supplier/grain value in {spec}")
        pair_claims[supplier, category].add(key)
        pair_provenance[supplier, category].update(row.get("_provenance_links", [row["Link_ID"]]))
        info[category] = {"Technology_Family": row["_family"],
                          "Technology_Category": row["_category"] if grain == "_tax" else category}
    nodes = sorted({s for s, _ in pair_claims})
    categories = sorted({t for _, t in pair_claims})
    vectors = {s: {} for s in nodes}
    pairs = []
    for (supplier, category), claims in sorted(pair_claims.items()):
        weight = 1 if binary else len(claims)
        vectors[supplier][category] = weight
        pairs.append({"Network_Spec_ID": spec, "Pair_Key": f"{supplier}||{category}",
                      "Supplier_ID": supplier, "Taxonomy_ID": category, "Grain_ID": category,
                      **info[category], "Weight": weight, "Weight_Unique_Link_ID": weight,
                      "Canonical_Claim_Count": len(claims), "Canonical_Link_IDs": sorted(claims),
                      "Provenance_Link_IDs": sorted(pair_provenance[supplier, category]),
                      "Population_ID": population})
    zero = Decimal(0) if method == "cosine" else Fraction(0)
    strength = {s: zero for s in nodes}
    adjacency = {s: {} for s in nodes}
    projection = []
    with localcontext() as context:
        context.prec = 100
        for left, right in combinations(nodes, 2):
            a, b = vectors[left], vectors[right]
            union = set(a) | set(b)
            numerator = denominator = None
            if method == "weighted_jaccard":
                numerator = sum(min(a.get(t, 0), b.get(t, 0)) for t in union)
                denominator = sum(max(a.get(t, 0), b.get(t, 0)) for t in union)
                if not numerator:
                    continue
                similarity = Fraction(numerator, denominator)
            elif method == "cosine":
                dot = sum(a.get(t, 0) * b.get(t, 0) for t in union)
                if not dot:
                    continue
                similarity = Decimal(dot) / Decimal(sum(v*v for v in a.values()) * sum(v*v for v in b.values())).sqrt()
            else:
                raise ValueError(f"Unknown similarity method: {method}")
            distance = 1 / similarity
            adjacency[left][right] = adjacency[right][left] = distance
            strength[left] += similarity
            strength[right] += similarity
            projection.append({"Network_Spec_ID": spec, "Projection_Key": f"{left}||{right}",
                               "Supplier_A": left, "Supplier_B": right,
                               "Similarity_Numerator": numerator, "Similarity_Denominator": denominator,
                               "Similarity_Exact_or_High_Precision": _plain(similarity),
                               "Similarity": float(similarity), "Distance_Exact_or_High_Precision": _plain(distance),
                               "Distance": float(distance), "Population_ID": population})
    between = c5.decimal_brandes(adjacency) if method == "cosine" else c3.brandes_normalized(adjacency)
    components = c3.connected_components(adjacency)
    possible = len(nodes) * (len(nodes)-1) // 2
    supplier_rows = [{"Supplier_ID": s, "Strength": float(strength[s]),
                      "Strength_Exact_or_High_Precision": _plain(strength[s]),
                      "Normalized_Betweenness": float(between[s]),
                      "Normalized_Betweenness_Exact_or_High_Precision": _plain(between[s]),
                      "Isolate_Flag": int(not adjacency[s]), "Positive_Edge_Count": len(adjacency[s]),
                      "Population_ID": population} for s in nodes]
    assert sum(p["Canonical_Claim_Count"] for p in pairs) == len(rows)
    assert sum(p["Weight"] for p in pairs) == (len(pairs) if binary else len(rows))
    assert len(projection) <= possible and sum(len(c) for c in components) == len(nodes)
    return {"network_spec_id": spec, "population_id": population,
            "grain_field": "Technology_Family" if grain == "_family" else "Analytical_Taxonomy_ID",
            "similarity_method": method, "weight_rule": "Binary category presence" if binary else "Unique canonical claims per supplier/category",
            "link_n": len(rows), "supplier_n": len(nodes), "pair_n": len(pairs), "grain_n": len(categories),
            "weight_sum": sum(p["Weight"] for p in pairs), "positive_edge_n": len(projection),
            "possible_pair_n": possible, "density": len(projection)/possible if possible else None,
            "component_n": len(components), "component_sizes": [len(c) for c in components],
            "isolate_n": sum(not adjacency[s] for s in nodes),
            "canonical_link_ids": sorted(seen), "pair_rows": pairs, "projection_rows": projection,
            "supplier_rows": supplier_rows, "supplier_nodes": [{"Node_ID": s, "Node_Type": "Supplier"} for s in nodes],
            "taxonomy_nodes": [{"Node_ID": t, "Node_Type": "Technology_Taxonomy", **info[t]} for t in categories],
            "vectors": vectors, "strength": strength, "betweenness": between}


def _independent_primary_check(network: dict, primary: dict) -> dict:
    """Alternative path-count definition plus pairwise ranks; no Brandes helper."""
    vectors = {s: Counter(v) for s, v in network["vectors"].items()}
    nodes = sorted(vectors)
    adjacency = {s: {} for s in nodes}
    strength = {s: Fraction(0) for s in nodes}
    edge_values = {}
    for s, t in combinations(nodes, 2):
        overlap = (vectors[s] & vectors[t]).total()
        if overlap:
            similarity = Fraction(overlap, (vectors[s] | vectors[t]).total())
            edge_values[s, t] = similarity
            adjacency[s][t] = adjacency[t][s] = 1/similarity
            strength[s] += similarity
            strength[t] += similarity
    distances, paths = {}, {}
    for source in nodes:
        dist, queue, settled = {source: Fraction(0)}, [(Fraction(0), source)], set()
        while queue:
            value, node = heapq.heappop(queue)
            if node in settled:
                continue
            settled.add(node)
            for target, length in adjacency[node].items():
                alternative = value + length
                if target not in dist or alternative < dist[target]:
                    dist[target] = alternative
                    heapq.heappush(queue, (alternative, target))
        counts = dict.fromkeys(dist, 0)
        counts[source] = 1
        for node in sorted(dist, key=dist.get):
            for target, length in adjacency[node].items():
                if dist[target] == dist[node]+length:
                    counts[target] += counts[node]
        distances[source], paths[source] = dist, counts
    between = dict.fromkeys(nodes, Fraction(0))
    for source, target in combinations(nodes, 2):
        if target not in distances[source]:
            continue
        for via in distances[source]:
            if via not in (source, target) and distances[source][via]+distances[via][target] == distances[source][target]:
                between[via] += Fraction(paths[source][via]*paths[via][target], paths[source][target])
    if len(nodes) > 2:
        between = {s: b*Fraction(2, (len(nodes)-1)*(len(nodes)-2)) for s, b in between.items()}
    stored_edges = {(r["Supplier_A"], r["Supplier_B"]): Fraction(r["Similarity_Exact_or_High_Precision"]) for r in network["projection_rows"]}
    checks = {"projection_exact_match": edge_values == stored_edges,
              "strength_exact_match": strength == network["strength"],
              "betweenness_exact_match": between == network["betweenness"]}
    breadth = {s: len(v) for s, v in vectors.items()}
    evenness = {}
    with localcontext() as context:
        context.prec = 80
        for supplier, vector in vectors.items():
            values = list(vector.values())
            if len(values) <= 1:
                evenness[supplier] = Decimal(0)
            elif len(set(values)) == 1:
                evenness[supplier] = Decimal(1)
            else:
                proportions = [Decimal(v)/sum(values) for v in values]
                evenness[supplier] = -sum(p*p.ln() for p in proportions)/Decimal(len(values)).ln()

    def ranks(values: dict) -> dict | None:
        if len(set(values.values())) <= 1:
            return None
        return {s: Fraction(100)*(sum(v < values[s] for v in values.values())
                                 + Fraction(sum(v == values[s] for v in values.values())+1, 2)-1)/(len(values)-1)
                for s in values}

    transformed = [ranks(v) for v in (breadth, evenness, strength, between)]
    dimensions = []
    for start in (0, 2):
        usable = [v for v in transformed[start:start+2] if v is not None]
        dimensions.append({s: sum(v[s] for v in usable)/len(usable) for s in nodes} if usable else None)
    mismatches, max_difference = 0, 0.0
    by_supplier = {r["Supplier_ID"]: r for r in primary["supplier_rows"]}
    medians = [statistics.median(v.values()) if v else None for v in dimensions]
    for supplier in nodes:
        for dim, key in zip(dimensions, ("Diversification_Score", "Embeddedness_Score")):
            expected, actual = (None if dim is None else float(dim[supplier])), by_supplier[supplier][key]
            if expected is None or actual is None:
                mismatches += int(expected is not actual)
            else:
                difference = abs(expected-actual)
                max_difference = max(max_difference, difference)
                mismatches += int(difference > 1e-10)
        if all(v is not None for v in dimensions):
            expected_profile = ("concentrated" if dimensions[0][supplier] <= medians[0] else "diversified")
            expected_profile += " / " + ("peripheral" if dimensions[1][supplier] <= medians[1] else "embedded")
            mismatches += int(expected_profile != by_supplier[supplier]["Profile"])
    checks["dimension_and_profile_match"] = mismatches == 0
    if not all(checks.values()):
        raise AssertionError(f"Independent primary calculation disagreement: {checks}")
    return {**checks, "max_dimension_difference": max_difference,
            "checked_suppliers": len(nodes), "checked_projection_edges": len(edge_values),
            "method": "Counter min/max overlap; all-pairs shortest-path counts; pairwise average ranks"}


def _origin_diagnostic(primary_rows: list[dict], primary: dict, vectors: dict) -> list[dict]:
    expansion = {_text(r["Supplier_ID"]) for r in primary_rows if _text(r.get("Origin")).startswith("public_evidence_expansion")}
    profiles = {r["Supplier_ID"]: r["Profile"] for r in primary["supplier_rows"]}
    result = []
    for label, suppliers in [("Any expansion-origin canonical claim", expansion),
                             ("Inherited-origin canonical claims only", set(vectors)-expansion)]:
        n = len(suppliers)
        multiple = sum(len(vectors[s]) > 1 for s in suppliers)
        result.append({"Group": label, "Supplier_N": n, "Multi_Category_N": multiple,
                       "Multi_Category_Share": multiple/n if n else None,
                       "Mean_Recorded_Claims": sum(sum(vectors[s].values()) for s in suppliers)/n if n else None,
                       "Mean_Category_Breadth": sum(len(vectors[s]) for s in suppliers)/n if n else None,
                       "Profile_Counts": dict(Counter(profiles[s] for s in suppliers)),
                       "Status": "POST HOC DIAGNOSTIC",
                       "Interpretation": "Mutually exclusive current-population groups; does not establish a causal effect of data collection."})
    return result


def calculate_all(root: Path, revised_rows: list[dict], frozen_rows: list[dict]) -> dict:
    """Calculate the successor without any output writes or source mutations."""
    root = Path(root).resolve()
    c3, c5, helper_hashes = _helpers(root)
    toy_tests = c3.run_known_graph_tests()
    rows, taxonomy = _prepare(revised_rows, frozen_rows)

    # Historical numerical expectations belong only to this named regression
    # fixture. They are never applied to a corrected population.
    baseline_rows = []
    for source in frozen_rows:
        if int(source.get("Capability_Supported_Layer") or 0) == 1 and _text(source.get("Taxonomy_Review_Flag")) != "Needs manual taxonomy review":
            baseline_rows.append({**source, "_canonical": source["Link_ID"], "_tax": source["Taxonomy_ID"],
                                  "_family": source["Technology_Family"], "_category": source["Technology_Category"],
                                  "_provenance_links": [source["Link_ID"]]})
    baseline_network = _network(c3, c5, "BASELINE", "FROZEN_BASELINE_PRIMARY", baseline_rows)
    baseline = c5.calculate_run("BASELINE", "Frozen baseline fixture", "Historical reference", "baseline", baseline_network)
    baseline_actual = [baseline_network[k] for k in ("link_n", "supplier_n", "pair_n", "positive_edge_n")]
    if baseline_actual != [392, 207, 254, 3522] or [baseline["profile_counts"][p] for p in PROFILE_ORDER] != [100, 88, 4, 15]:
        raise AssertionError("The reusable mathematics did not reproduce the frozen historical fixture")

    resolved = lambda r: _flag(r, "Identity_Resolved_Revised")
    distinct = lambda r: r.get("Distinctness_Status") != "unresolved_overlap"
    capability = lambda r: resolved(r) and distinct(r) and _flag(r, "Capability_Supported_Revised") and _flag(r, "Non_Excluded_Revised")
    populations = {
        "primary": _select(rows, lambda r: _flag(r, "Primary_Eligible")),
        "nonexcluded": _select(rows, lambda r: resolved(r) and distinct(r) and _flag(r, "Non_Excluded_Revised") and r["_controlled"]),
        "same_bmw": _select(rows, lambda r: capability(r) and _flag(r, "BMW_Relationship_Supported_Revised") and r["_controlled"]),
        "exact_bmw": _select(rows, lambda r: capability(r) and _flag(r, "BMW_Relationship_Supported_Revised") and _flag(r, "Exact_BMW_Technology_Revised") and r["_controlled"]),
        "tax18_included": _select(rows, capability),
    }
    populations["inherited_only"] = [r for r in populations["primary"] if _text(r.get("Origin")) == "current_workbook"]
    specs = [
        ("N00", "primary", "_tax", "weighted_jaccard", False),
        ("N01", "primary", "_tax", "cosine", False),
        ("N02", "primary", "_family", "weighted_jaccard", False),
        ("N03", "nonexcluded", "_tax", "weighted_jaccard", False),
        ("N04", "same_bmw", "_tax", "weighted_jaccard", False),
        ("N05", "exact_bmw", "_tax", "weighted_jaccard", False),
        ("N06", "tax18_included", "_tax", "weighted_jaccard", False),
        ("N07", "primary", "_tax", "weighted_jaccard", True),
        ("N08", "inherited_only", "_tax", "weighted_jaccard", False),
    ]
    networks = {spec: _network(c3, c5, spec, f"{REVISION_ID}:{pop}", populations[pop], grain, method, binary)
                for spec, pop, grain, method, binary in specs}
    run_specs = [
        ("R00", "Corrected primary", "Reference", "primary", "N00", {}),
        ("R01", "40th/60th profile bands", "A3.9.1", "boundary", "N00", {"boundary_rule": "40_60"}),
        ("R02", "25th/75th extreme profiles", "A3.9.2", "boundary", "N00", {"boundary_rule": "25_75"}),
        ("R03", "Log1p plus min-max", "A3.9.3", "transformation", "N00", {"transformation": "log1p_minmax"}),
        ("R04", "Diversification weights 60/40", "A3.9.4", "weight", "N00", {"diversification_weights": (Fraction(3,5), Fraction(2,5))}),
        ("R05", "Diversification weights 40/60", "A3.9.4", "weight", "N00", {"diversification_weights": (Fraction(2,5), Fraction(3,5))}),
        ("R06", "Embeddedness weights 60/40", "A3.9.4", "weight", "N00", {"embeddedness_weights": (Fraction(3,5), Fraction(2,5))}),
        ("R07", "Embeddedness weights 40/60", "A3.9.4", "weight", "N00", {"embeddedness_weights": (Fraction(2,5), Fraction(3,5))}),
        ("R08", "Remove evenness", "A3.9.5", "indicator_removal", "N00", {"remove_indicator": "Pielou_Evenness"}),
        ("R09", "Remove betweenness", "A3.9.5", "indicator_removal", "N00", {"remove_indicator": "Normalized_Betweenness"}),
        ("R10", "Cosine similarity", "A3.9.6", "similarity", "N01", {}),
        ("R11", "Technology-family grain", "A3.9.7", "technology_grain", "N02", {}),
        ("R12", "Non-excluded candidate stress test", "A3.9.8, revised eligibility", "evidence_layer", "N03", {}),
        ("R13", "BMW relationship and capability intersection", "A3.9.8, revised eligibility", "evidence_layer", "N04", {}),
        ("R14", "Exact BMW technology with supported capability", "A3.9.8, revised eligibility", "evidence_layer", "N05", {}),
        ("R15", "Include unresolved taxonomy as a review bucket", "A3.9.9", "taxonomy_review", "N06", {}),
        ("PH01", "Binary category-membership weights", "Post hoc audit extension", "posthoc_weight", "N07", {}),
        ("PH02", "Inherited-origin claims only", "Post hoc audit extension", "posthoc_origin", "N08", {}),
    ]
    runs = [c5.calculate_run(run_id, title, item, kind, networks[spec], **options)
            for run_id, title, item, kind, spec, options in run_specs]
    primary = runs[0]
    for run in runs:
        c5.add_stability(run, primary)
        run["Specification_Status"] = "POST HOC DIAGNOSTIC" if run["run_id"].startswith("PH") else "Original A3 method; corrected eligibility where specified"
        run["Distinctness_Gate"] = "Unresolved overlap is excluded from every network, including secondary population sensitivities. Descriptive support counts may still include held register groups."
        if run["run_id"] == "R12":
            run["Interpretation_Caveat"] = "Includes unestablished capability candidates as a stress test only; not a verified-capability network."
        elif run["run_id"] == "R15":
            run["Interpretation_Caveat"] = "Shared review-bucket membership can create artificial technology similarity."
        elif run["run_id"] == "PH02":
            run["Interpretation_Caveat"] = "Removes expansion-origin claims, changes coverage and rescales within the remaining supplier population; does not estimate causality."
    independent = _independent_primary_check(networks["N00"], primary)
    before = {r["Supplier_ID"]: r for r in baseline["supplier_rows"]}
    after = {r["Supplier_ID"]: r for r in primary["supplier_rows"]}
    supplier_comparison = [{"Supplier_ID": supplier,
                            "Baseline_Profile": before.get(supplier, {}).get("Profile"),
                            "Revised_Profile": after.get(supplier, {}).get("Profile"),
                            "Population_Status": "Common" if supplier in before and supplier in after else "Removed" if supplier in before else "Added",
                            "Same_Profile": int(before[supplier]["Profile"] == after[supplier]["Profile"]) if supplier in before and supplier in after else None}
                           for supplier in sorted(set(before) | set(after))]
    metrics = []
    for key in ("link_n", "supplier_n", "pair_n", "grain_n", "weight_sum", "positive_edge_n", "possible_pair_n", "density", "component_n", "isolate_n"):
        old, new = baseline_network[key], networks["N00"][key]
        metrics.append({"Metric": key, "Frozen_Baseline": old, "Revised": new, "Change": new-old})
    population_summary = [{"Population": name, "Canonical_Claim_N": len(rs),
                           "Supplier_N": len({_text(r['Supplier_ID']) for r in rs}),
                           "Taxonomy_N": len({r['_tax'] for r in rs}),
                           "Canonical_Link_IDs": [r['_canonical'] for r in rs]}
                          for name, rs in populations.items()]
    payload = {
        "schema_version": "revision_calculations/1.0", "revision_id": REVISION_ID,
        "method": {"structural_unit": "Supplier derived from unique canonical supplier-technology claims",
                   "weight_unit": "Unique canonical claims per supplier/category; evidence rows never contribute weight",
                   "layer_rule": "Capability and BMW relationship are separate claims; BMW network requires their intersection",
                   "distinctness_rule": "Every network excludes unresolved-overlap holds before canonical grouping. A register group is not automatically a proven distinct capability.",
                   "edge_meaning": "Shared classified technology representation; no observed supplier interaction",
                   "helper_source_sha256": helper_hashes},
        "input_summary": {"frozen_audit_rows": len(frozen_rows), "revised_audit_rows": len(rows),
                          "canonical_claim_groups": len({r['_canonical'] for r in rows}),
                          "original_Link_IDs_retained": True},
        "baseline_fixture": {"status": "PASS", "network_summary": {k: baseline_network[k] for k in ("link_n", "supplier_n", "pair_n", "grain_n", "positive_edge_n", "density", "component_sizes")},
                             "profile_counts": baseline["profile_counts"], "supplier_rows": baseline["supplier_rows"]},
        "populations": population_summary,
        "networks": {name: {k:v for k,v in net.items() if k not in {"strength", "betweenness"}} for name,net in networks.items()},
        "primary": primary, "sensitivity_runs": runs, "metric_comparison": metrics,
        "supplier_comparison": supplier_comparison,
        "origin_diagnostic": _origin_diagnostic(populations["primary"], primary, networks["N00"]["vectors"]),
        "deferred": [{"ID": "G01", "Status": "NOT EXECUTED", "Reason": "No harmonized fine-technology mapping and duplicate rule. Analytical English labels alone do not establish comparable fine-grain units."}],
        "qa": {"known_graph_tests": toy_tests, "baseline_fixture_pass": True,
               "independent_primary": independent, "canonical_weights_reconcile_all_networks": True,
               "source_files_written": False, "random_forest_trained": False},
        "taxonomy_metadata": taxonomy,
    }
    plain = _plain(payload)
    json.dumps(plain, allow_nan=False)
    return plain


def render_network(payload: dict, outdir: Path, *, replace: bool = False) -> dict:
    """Explicit static figure export, restricted to this revision directory.

    Chart contract: show all revised primary supplier/category memberships in
    one bipartite overview. Supplier circles are anonymous; category squares
    are labelled and decoded in a readable side legend. Position is a fixed,
    deterministic drawing aid, not a score or a physical/operational distance.
    Blue/gold plus neutral marks distinguish node types without relying on
    color alone. The caller must visually inspect the exported PNG before use.
    """
    revision_root = Path(__file__).resolve().parent
    output = Path(outdir).resolve()
    if output != revision_root and revision_root not in output.parents:
        raise ValueError("Figure output must remain beneath the revision directory")
    targets = [output / "Revised_Supplier_Technology_Network.png", output / "Revised_Supplier_Technology_Network.svg"]
    if any(p.resolve() != output / p.name for p in targets):
        raise ValueError("Figure files must not redirect through links outside their declared output directory")
    if any(p.exists() for p in targets) and not replace:
        raise FileExistsError("Choose a fresh figure output directory; existing figures are preserved")
    from PIL import Image, ImageDraw, ImageFont
    from html import escape
    import textwrap
    network = payload["networks"]["N00"]
    vectors = network["vectors"]
    categories = sorted(r["Node_ID"] for r in network["taxonomy_nodes"])
    count = len(categories)
    positions = {tax: (math.cos(2*math.pi*i/max(count,1)), math.sin(2*math.pi*i/max(count,1))) for i,tax in enumerate(categories)}
    single = defaultdict(list)
    supplier_positions = {}
    for supplier, vector in sorted(vectors.items()):
        if len(vector) == 1:
            single[next(iter(vector))].append(supplier)
        else:
            weight = sum(vector.values())
            x = sum(positions[t][0]*v for t,v in vector.items())/weight
            y = sum(positions[t][1]*v for t,v in vector.items())/weight
            digest = hashlib.sha256(supplier.encode()).digest()
            angle = int.from_bytes(digest[:4], "big") / 2**32 * math.tau
            supplier_positions[supplier] = (0.66*x+0.035*math.cos(angle), 0.66*y+0.035*math.sin(angle))
    for category, suppliers in single.items():
        cx, cy = positions[category]
        for i,supplier in enumerate(suppliers):
            angle = i*math.pi*(3-math.sqrt(5))
            radius = 0.045 + 0.13*math.sqrt((i+1)/max(len(suppliers),1))
            supplier_positions[supplier] = (1.21*cx+radius*math.cos(angle), 1.21*cy+radius*math.sin(angle))
    width, height = 3400, 2200
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    regular_candidates = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    bold_candidates = ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/arialbd.ttf",
                       "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    font_paths = {"regular": next((p for p in regular_candidates if Path(p).exists()), None),
                  "bold": next((p for p in bold_candidates if Path(p).exists()), None)}
    if not all(font_paths.values()):
        raise FileNotFoundError("A regular/bold Segoe UI, Arial or DejaVu Sans font is needed")
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>']

    def label(x, y, text, size=28, bold=False, fill="#27343E", anchor="la"):
        font = ImageFont.truetype(font_paths["bold" if bold else "regular"], size=size)
        draw.text((x,y),text,font=font,fill=fill,anchor=anchor)
        # SVG uses a top text anchor, matching the raster's ascender anchor.
        alignment = "middle" if anchor.startswith("m") else "start"
        svg.append(f'<text x="{x:.2f}" y="{y:.2f}" dominant-baseline="text-before-edge" text-anchor="{alignment}" '
                   f'font-family="Segoe UI, Arial, sans-serif" font-size="{size}" font-weight="{600 if bold else 400}" fill="{fill}">{escape(text)}</text>')

    def xy(point):
        return (1110+650*point[0], 1110-650*point[1])

    for edge in network["pair_rows"]:
        x,y = xy(supplier_positions[edge["Supplier_ID"]])
        tx,ty = xy(positions[edge["Taxonomy_ID"]])
        draw.line((x,y,tx,ty), fill="#CCD2D7", width=1)
        svg.append(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{tx:.2f}" y2="{ty:.2f}" stroke="#CCD2D7" stroke-width="1"/>')
    for point in supplier_positions.values():
        x,y = xy(point)
        draw.ellipse((x-6,y-6,x+6,y+6),fill="#476882",outline="white",width=1)
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="#476882" stroke="white" stroke-width="1"/>')
    for category,point in positions.items():
        x,y = xy(point)
        draw.rectangle((x-12,y-12,x+12,y+12),fill="#BD912E",outline="#655329",width=2)
        svg.append(f'<rect x="{x-12:.2f}" y="{y-12:.2f}" width="24" height="24" fill="#BD912E" stroke="#655329" stroke-width="2"/>')
        lx,ly = xy((0.90*point[0],0.90*point[1]))
        label(lx,ly-16,category.replace("TAX-","T"),size=25,bold=True,anchor="ma")
    label(2360,300,"Technology categories",size=37,bold=True)
    metadata={r["Node_ID"]:r for r in network["taxonomy_nodes"]}
    lines=[f"{tax.replace('TAX-','T')}   {metadata[tax]['Technology_Category']}" for tax in categories]
    y=380
    for line in lines:
        wrapped=textwrap.wrap(line,46,break_long_words=False)
        for text in wrapped:
            label(2360,y,text,size=28)
            y+=39
        y+=15
    if y > 1950:
        raise ValueError("Technology legend does not fit; revise the figure layout before export")
    label(100,55,"Revised supplier–technology category network",size=54,bold=True)
    label(100,143,f"{network['supplier_n']} suppliers · {network['grain_n']} categories · {network['pair_n']} supplier/category pairs · {network['link_n']} canonical claims",size=34,fill="#485761")
    label(100,2015,"Circles: suppliers. Squares: technology categories. Lines: recorded category membership. Positions are drawing aids.",size=29)
    label(100,2070,"Source: corrected derived evidence view. Shared technology does not establish supplier interaction or BMW operational coordination.",size=27,fill="#485761")
    svg.append('</svg>')
    output.mkdir(parents=True,exist_ok=True)
    canvas.save(targets[0],dpi=(220,220))
    targets[1].write_text("\n".join(svg)+"\n",encoding="utf-8")
    return {"files":[str(p) for p in targets],"supplier_nodes":network["supplier_n"],
            "taxonomy_nodes":network["grain_n"],"edges":network["pair_n"],
            "font_sha256":{role:hashlib.sha256(Path(path).read_bytes()).hexdigest().upper() for role,path in font_paths.items()},
            "visual_inspection":"REQUIRED before thesis use"}
