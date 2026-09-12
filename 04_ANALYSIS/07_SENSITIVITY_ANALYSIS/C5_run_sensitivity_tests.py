"""Run the A3-pre-specified C5 sensitivity analyses.

The script is deterministic and read-only with respect to every authoritative
workbook. It reconstructs each population-changing network from unique frozen
Link_ID records, recalculates transformations and thresholds inside that run,
and reports non-estimable specifications instead of inventing tie-breaking or
zero-variance rules.

Visibility remains a link-level ordinal construct. This script does not create
a supplier-level visibility score, a visibility-complexity association, an
overall cross-dimension score, an inferential test, or a Random Forest model.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import importlib.util
import json
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "03_DATA_AND_EVIDENCE/01_FINAL_MASTER/04_SUPPLIER_EVIDENCE_ANALYTICAL_MASTER_FINAL.xlsx"
C3_SCRIPT = ROOT / "04_ANALYSIS/05_NETWORK_ANALYSIS/C3_construct_network.py"
C4_SCRIPT = ROOT / "04_ANALYSIS/06_COORDINATION_COMPLEXITY_SCORES/C4_calculate_scores.py"
C4_WORKBOOK = ROOT / "04_ANALYSIS/06_COORDINATION_COMPLEXITY_SCORES/C4_COORDINATION_COMPLEXITY_SCORES_WORKING.xlsx"
B1_REGISTER = ROOT / "04_ANALYSIS/02_DATA_PREPARATION/B1_TAXONOMY_REVIEW_REGISTER.xlsx"
B4_REGISTER = ROOT / "04_ANALYSIS/02_DATA_PREPARATION/B4_DENOMINATOR_REGISTER.xlsx"

EXPECTED_HASHES = {
    "analytical_master": "8C5B3439CFFF00A2110C575E101CD32C4988BDDC3269DDDDD46497F2A950C16D",
    "c4_workbook": "4AFD6920D3B6E630848EAB765046B0EDABCAEC0AF030264AB704C55FC3D5DB2B",
    "b1_register": "0AC5DB0E1171D98E2DC7C919522B2EEA18D4283972FCCA04B61215A3278EFA51",
    "b4_register": "348C384002B1D54E50293238EF48621CF7FA45293AF92CBC29A32C652DAF933E",
}

PROFILE_ORDER = [
    "concentrated / peripheral",
    "concentrated / embedded",
    "diversified / peripheral",
    "diversified / embedded",
]

EXPECTED_NETWORKS = {
    "N00": {"link_n": 392, "supplier_n": 207, "pair_n": 254, "grain_n": 17, "positive_edge_n": 3522},
    "N01": {"link_n": 392, "supplier_n": 207, "pair_n": 254, "grain_n": 17, "positive_edge_n": 3522},
    "N02": {"link_n": 392, "supplier_n": 207, "pair_n": 221, "grain_n": 3, "positive_edge_n": 16509},
    "N03": {"link_n": 410, "supplier_n": 220, "pair_n": 269, "grain_n": 17},
    "N04": {"link_n": 157, "supplier_n": 49, "pair_n": 81, "grain_n": 17},
    "N05": {"link_n": 39, "supplier_n": 35, "pair_n": 35, "grain_n": 13, "positive_edge_n": 56},
    "N06": {"link_n": 426, "supplier_n": 231, "pair_n": 284, "grain_n": 18},
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require_private_output(path: Path) -> Path:
    """Restrict row-level JSON exports to the repository's ignored tmp tree."""

    resolved = path.resolve()
    private_root = (ROOT / "tmp").resolve()
    if resolved != private_root and private_root not in resolved.parents:
        raise ValueError(f"Full C5 output must stay under the ignored local directory: {private_root}")
    return resolved


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_decimal(value: Fraction | Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Fraction):
        with localcontext() as context:
            context.prec = 100
            return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(str(value))


def display_number(value: Fraction | Decimal | int | float | None, places: int = 15) -> float | None:
    if value is None:
        return None
    return round(float(as_decimal(value)), places)


def exact_text(value: Fraction | Decimal | int) -> str:
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def type7_quantile(values: Iterable[Decimal], probability: Fraction) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Quantile is undefined for an empty sequence")
    if probability < 0 or probability > 1:
        raise ValueError("Quantile probability must be between zero and one")
    if len(ordered) == 1:
        return ordered[0]
    h = Fraction(len(ordered) - 1) * probability
    lower = h.numerator // h.denominator
    upper = lower if h.denominator == 1 else lower + 1
    if lower == upper:
        return ordered[lower]
    fraction = as_decimal(h - lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def midrank_percentiles(values: dict[str, Any]) -> dict[str, Decimal]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    n = len(ordered)
    if n <= 1:
        raise ValueError("Midrank percentile requires N > 1")
    transformed: dict[str, Decimal] = {}
    index = 0
    while index < n:
        end = index + 1
        while end < n and ordered[end][1] == ordered[index][1]:
            end += 1
        midrank = Fraction((index + 1) + end, 2)
        percentile = Fraction(100, 1) * (midrank - 1) / (n - 1)
        decimal_value = as_decimal(percentile)
        for position in range(index, end):
            transformed[ordered[position][0]] = decimal_value
        index = end
    return transformed


def log1p_minmax(values: dict[str, Any]) -> dict[str, Decimal]:
    if len(set(values.values())) <= 1:
        raise ValueError("Log-minmax transformation is undefined for a constant indicator")
    with localcontext() as context:
        context.prec = 100
        logged = {key: (Decimal(1) + as_decimal(value)).ln() for key, value in values.items()}
        minimum = min(logged.values())
        maximum = max(logged.values())
        span = maximum - minimum
        return {key: Decimal(100) * (value - minimum) / span for key, value in logged.items()}


def numeric_equal(left: Decimal, right: Decimal) -> bool:
    tolerance = Decimal("1e-70") * max(Decimal(1), abs(left), abs(right))
    return abs(left - right) <= tolerance


def decimal_brandes(adjacency: dict[str, dict[str, Decimal]]) -> dict[str, Decimal]:
    """High-precision weighted Brandes for the cosine-distance run."""

    nodes = sorted(adjacency)
    centrality = {node: Decimal(0) for node in nodes}
    with localcontext() as context:
        context.prec = 100
        for source in nodes:
            stack: list[str] = []
            predecessors: dict[str, list[str]] = {node: [] for node in nodes}
            sigma = {node: 0 for node in nodes}
            sigma[source] = 1
            distance: dict[str, Decimal | None] = {node: None for node in nodes}
            distance[source] = Decimal(0)
            queue: list[tuple[Decimal, str]] = [(Decimal(0), source)]

            while queue:
                current_distance, vertex = heapq.heappop(queue)
                known = distance[vertex]
                if known is None or not numeric_equal(current_distance, known):
                    continue
                stack.append(vertex)
                for neighbor in sorted(adjacency[vertex]):
                    candidate = current_distance + adjacency[vertex][neighbor]
                    neighbor_distance = distance[neighbor]
                    if neighbor_distance is None or candidate < neighbor_distance and not numeric_equal(candidate, neighbor_distance):
                        distance[neighbor] = candidate
                        heapq.heappush(queue, (candidate, neighbor))
                        sigma[neighbor] = sigma[vertex]
                        predecessors[neighbor] = [vertex]
                    elif neighbor_distance is not None and numeric_equal(candidate, neighbor_distance):
                        sigma[neighbor] += sigma[vertex]
                        predecessors[neighbor].append(vertex)

            dependency = {node: Decimal(0) for node in nodes}
            while stack:
                successor = stack.pop()
                if sigma[successor] == 0:
                    continue
                coefficient = (Decimal(1) + dependency[successor]) / Decimal(sigma[successor])
                for predecessor in predecessors[successor]:
                    dependency[predecessor] += Decimal(sigma[predecessor]) * coefficient
                if successor != source:
                    centrality[successor] += dependency[successor]

        n = len(nodes)
        if n <= 2:
            return {node: Decimal(0) for node in nodes}
        scale = Decimal(1) / Decimal((n - 1) * (n - 2))
        return {node: value * scale for node, value in centrality.items()}


def select_population(rows: list[dict[str, Any]], population_key: str) -> list[dict[str, Any]]:
    def flag(row: dict[str, Any], field: str) -> bool:
        return int(row.get(field) or 0) == 1

    def controlled(row: dict[str, Any]) -> bool:
        return norm(row.get("Taxonomy_Review_Flag")) != "Needs manual taxonomy review"

    selectors = {
        "primary": lambda row: flag(row, "Capability_Supported_Layer") and controlled(row),
        "nonexcluded": lambda row: flag(row, "Non_Excluded_Layer") and controlled(row),
        "same_bmw": lambda row: flag(row, "Same_Entity_BMW_Relationship_Layer") and controlled(row),
        "exact_bmw": lambda row: flag(row, "Exact_BMW_Technology_Layer") and controlled(row),
        "tax18_included": lambda row: flag(row, "Capability_Supported_Layer"),
    }
    if population_key not in selectors:
        raise ValueError(f"Unknown population key: {population_key}")
    selected = [row for row in rows if selectors[population_key](row)]
    selected_ids = [norm(row["Link_ID"]) for row in selected]
    if any(not link_id for link_id in selected_ids) or len(selected_ids) != len(set(selected_ids)):
        raise ValueError(f"{population_key} does not have unique populated Link_ID values")
    return sorted(selected, key=lambda row: norm(row["Link_ID"]))


def build_network(
    c3: Any,
    spec_id: str,
    population_id: str,
    link_rows: list[dict[str, Any]],
    grain_field: str,
    similarity_method: str,
) -> dict[str, Any]:
    pair_links: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in link_rows:
        supplier_id = norm(row["Supplier_ID"])
        grain_id = norm(row[grain_field])
        link_id = norm(row["Link_ID"])
        if not supplier_id or not grain_id or not link_id:
            raise ValueError(f"Blank network identifier in {spec_id}: {row}")
        pair_links[(supplier_id, grain_id)].add(link_id)

    suppliers = sorted({supplier_id for supplier_id, _ in pair_links})
    grains = sorted({grain_id for _, grain_id in pair_links})
    vectors: dict[str, dict[str, int]] = {supplier_id: {} for supplier_id in suppliers}
    pair_rows: list[dict[str, Any]] = []
    for supplier_id, grain_id in sorted(pair_links):
        link_ids = sorted(pair_links[(supplier_id, grain_id)])
        weight = len(link_ids)
        vectors[supplier_id][grain_id] = weight
        pair_rows.append(
            {
                "Network_Spec_ID": spec_id,
                "Population_ID": population_id,
                "Supplier_ID": supplier_id,
                "Grain_Field": grain_field,
                "Grain_ID": grain_id,
                "Weight_Unique_Link_ID": weight,
                "Link_IDs": ", ".join(link_ids),
                "Pair_Key": f"{spec_id}||{supplier_id}||{grain_id}",
            }
        )
    if sum(row["Weight_Unique_Link_ID"] for row in pair_rows) != len(link_rows):
        raise ValueError(f"{spec_id} pair weights do not sum to link N")

    if similarity_method == "weighted_jaccard":
        zero: Fraction | Decimal = Fraction(0, 1)
    elif similarity_method == "cosine":
        zero = Decimal(0)
    else:
        raise ValueError(f"Unknown similarity method: {similarity_method}")

    strength: dict[str, Fraction | Decimal] = {supplier_id: zero for supplier_id in suppliers}
    adjacency_fraction: dict[str, dict[str, Fraction]] = {supplier_id: {} for supplier_id in suppliers}
    adjacency_decimal: dict[str, dict[str, Decimal]] = {supplier_id: {} for supplier_id in suppliers}
    projection_rows: list[dict[str, Any]] = []

    with localcontext() as context:
        context.prec = 100
        for left_index, left in enumerate(suppliers):
            left_vector = vectors[left]
            for right in suppliers[left_index + 1 :]:
                right_vector = vectors[right]
                grain_union = set(left_vector) | set(right_vector)
                numerator: int | None = None
                denominator: int | None = None
                dot: int | None = None
                left_norm_sq: int | None = None
                right_norm_sq: int | None = None

                if similarity_method == "weighted_jaccard":
                    numerator = sum(min(left_vector.get(grain, 0), right_vector.get(grain, 0)) for grain in grain_union)
                    denominator = sum(max(left_vector.get(grain, 0), right_vector.get(grain, 0)) for grain in grain_union)
                    if denominator <= 0:
                        raise ValueError(f"Invalid Jaccard denominator in {spec_id}")
                    if numerator == 0:
                        continue
                    similarity: Fraction | Decimal = Fraction(numerator, denominator)
                    distance: Fraction | Decimal = Fraction(denominator, numerator)
                    adjacency_fraction[left][right] = distance
                    adjacency_fraction[right][left] = distance
                else:
                    dot = sum(left_vector.get(grain, 0) * right_vector.get(grain, 0) for grain in grain_union)
                    if dot == 0:
                        continue
                    left_norm_sq = sum(weight * weight for weight in left_vector.values())
                    right_norm_sq = sum(weight * weight for weight in right_vector.values())
                    similarity = Decimal(dot) / (Decimal(left_norm_sq) * Decimal(right_norm_sq)).sqrt()
                    distance = Decimal(1) / similarity
                    adjacency_decimal[left][right] = distance
                    adjacency_decimal[right][left] = distance

                strength[left] += similarity
                strength[right] += similarity
                projection_rows.append(
                    {
                        "Network_Spec_ID": spec_id,
                        "Population_ID": population_id,
                        "Projection_Key": f"{spec_id}||{left}||{right}",
                        "Supplier_A": left,
                        "Supplier_B": right,
                        "Similarity_Method": similarity_method,
                        "Jaccard_Numerator": numerator,
                        "Jaccard_Denominator": denominator,
                        "Cosine_Dot": dot,
                        "Cosine_Left_Norm_Sq": left_norm_sq,
                        "Cosine_Right_Norm_Sq": right_norm_sq,
                        "Numeric_Representation": "Exact rational" if similarity_method == "weighted_jaccard" else "High-precision decimal (100 digits)",
                        "Similarity_Exact_or_High_Precision": exact_text(similarity),
                        "Similarity": display_number(similarity),
                        "Distance_Exact_or_High_Precision": exact_text(distance),
                        "Distance": display_number(distance),
                    }
                )

    if similarity_method == "weighted_jaccard":
        betweenness = c3.brandes_normalized(adjacency_fraction)
        adjacency: dict[str, dict[str, Any]] = adjacency_fraction
    else:
        betweenness = decimal_brandes(adjacency_decimal)
        adjacency = adjacency_decimal

    components = c3.connected_components(adjacency)
    isolates = sorted(supplier_id for supplier_id in suppliers if not adjacency[supplier_id])
    possible_pairs = len(suppliers) * (len(suppliers) - 1) // 2
    supplier_rows = [
        {
            "Network_Spec_ID": spec_id,
            "Population_ID": population_id,
            "Supplier_ID": supplier_id,
            "Numeric_Representation": "Exact rational" if similarity_method == "weighted_jaccard" else "High-precision decimal (100 digits)",
            "Strength_Exact_or_High_Precision": exact_text(strength[supplier_id]),
            "Strength": display_number(strength[supplier_id]),
            "Normalized_Betweenness_Exact_or_High_Precision": exact_text(betweenness[supplier_id]),
            "Normalized_Betweenness": display_number(betweenness[supplier_id]),
            "Isolate_Flag": int(supplier_id in isolates),
            "Positive_Edge_Count": len(adjacency[supplier_id]),
        }
        for supplier_id in suppliers
    ]

    actual = {
        "link_n": len(link_rows),
        "supplier_n": len(suppliers),
        "pair_n": len(pair_rows),
        "grain_n": len(grains),
        "positive_edge_n": len(projection_rows),
    }
    for key, expected in EXPECTED_NETWORKS[spec_id].items():
        if actual[key] != expected:
            raise ValueError(f"{spec_id} {key}: expected {expected}, found {actual[key]}")
    if len(projection_rows) > possible_pairs:
        raise ValueError(f"{spec_id} projection has too many edges")

    return {
        "network_spec_id": spec_id,
        "population_id": population_id,
        "grain_field": grain_field,
        "similarity_method": similarity_method,
        "link_n": len(link_rows),
        "supplier_n": len(suppliers),
        "pair_n": len(pair_rows),
        "grain_n": len(grains),
        "positive_edge_n": len(projection_rows),
        "possible_pair_n": possible_pairs,
        "density": 0 if possible_pairs == 0 else len(projection_rows) / possible_pairs,
        "component_n": len(components),
        "component_sizes": [len(component) for component in components],
        "isolate_n": len(isolates),
        "pair_rows": pair_rows,
        "projection_rows": projection_rows,
        "supplier_rows": supplier_rows,
        "vectors": vectors,
        "strength": strength,
        "betweenness": betweenness,
    }


def evenness_for_weights(weights: Iterable[int]) -> Decimal:
    ordered = sorted(weights)
    breadth = len(ordered)
    if breadth <= 1:
        return Decimal(0)
    if len(set(ordered)) == 1:
        return Decimal(1)
    with localcontext() as context:
        context.prec = 100
        total = Decimal(sum(ordered))
        entropy = Decimal(0)
        for weight in ordered:
            proportion = Decimal(weight) / total
            entropy -= proportion * proportion.ln()
        return entropy / Decimal(breadth).ln()


def summarize(values: list[Any]) -> dict[str, Any]:
    if not values:
        return {"valid_n": 0, "missing_n": 0, "zero_n": 0, "distinct_n": 0, "min": None, "median": None, "mean": None, "max": None}
    decimals = [as_decimal(value) for value in values]
    return {
        "valid_n": len(decimals),
        "missing_n": 0,
        "zero_n": sum(value == 0 for value in decimals),
        "distinct_n": len(set(decimals)),
        "min": display_number(min(decimals)),
        "median": display_number(type7_quantile(decimals, Fraction(1, 2))),
        "mean": display_number(sum(decimals, Decimal(0)) / Decimal(len(decimals))),
        "max": display_number(max(decimals)),
    }


def calculate_run(
    run_id: str,
    title: str,
    a3_item: str,
    run_type: str,
    network: dict[str, Any],
    transformation: str = "midrank_percentile",
    diversification_weights: tuple[Fraction, Fraction] = (Fraction(1, 2), Fraction(1, 2)),
    embeddedness_weights: tuple[Fraction, Fraction] = (Fraction(1, 2), Fraction(1, 2)),
    remove_indicator: str | None = None,
    boundary_rule: str = "median",
) -> dict[str, Any]:
    supplier_ids = sorted(network["vectors"])
    breadth = {supplier_id: len(network["vectors"][supplier_id]) for supplier_id in supplier_ids}
    evenness = {supplier_id: evenness_for_weights(network["vectors"][supplier_id].values()) for supplier_id in supplier_ids}
    indicators: dict[str, dict[str, Any]] = {
        "Category_Breadth": breadth,
        "Pielou_Evenness": evenness,
        "Strength": network["strength"],
        "Normalized_Betweenness": network["betweenness"],
    }
    zero_variance = {name: len(set(values.values())) <= 1 for name, values in indicators.items()}
    transformed: dict[str, dict[str, Decimal] | None] = {}
    for name, values in indicators.items():
        if zero_variance[name]:
            transformed[name] = None
        elif transformation == "midrank_percentile":
            transformed[name] = midrank_percentiles(values)
        elif transformation == "log1p_minmax":
            transformed[name] = log1p_minmax(values)
        else:
            raise ValueError(f"Unknown transformation: {transformation}")

    dimension_components = {
        "Diversification": [
            ("Category_Breadth", diversification_weights[0]),
            ("Pielou_Evenness", diversification_weights[1]),
        ],
        "Embeddedness": [
            ("Strength", embeddedness_weights[0]),
            ("Normalized_Betweenness", embeddedness_weights[1]),
        ],
    }
    if remove_indicator:
        for dimension in dimension_components:
            dimension_components[dimension] = [
                item for item in dimension_components[dimension] if item[0] != remove_indicator
            ]

    effective_weights: dict[str, dict[str, Decimal]] = {}
    dimension_scores: dict[str, dict[str, Decimal] | None] = {}
    for dimension, components in dimension_components.items():
        usable = [(name, weight) for name, weight in components if transformed[name] is not None]
        if not usable:
            effective_weights[dimension] = {}
            dimension_scores[dimension] = None
            continue
        total_weight = sum((weight for _, weight in usable), Fraction(0, 1))
        effective_weights[dimension] = {name: as_decimal(weight / total_weight) for name, weight in usable}
        scores: dict[str, Decimal] = {}
        for supplier_id in supplier_ids:
            scores[supplier_id] = sum(
                effective_weights[dimension][name] * transformed[name][supplier_id]  # type: ignore[index]
                for name, _ in usable
            )
        dimension_scores[dimension] = scores

    thresholds: dict[str, dict[str, Decimal | None]] = {
        "Diversification": {"low": None, "high": None},
        "Embeddedness": {"low": None, "high": None},
    }
    for dimension, scores in dimension_scores.items():
        if scores is None:
            continue
        values = list(scores.values())
        if boundary_rule == "median":
            value = type7_quantile(values, Fraction(1, 2))
            thresholds[dimension] = {"low": value, "high": value}
        elif boundary_rule == "40_60":
            thresholds[dimension] = {
                "low": type7_quantile(values, Fraction(2, 5)),
                "high": type7_quantile(values, Fraction(3, 5)),
            }
        elif boundary_rule == "25_75":
            thresholds[dimension] = {
                "low": type7_quantile(values, Fraction(1, 4)),
                "high": type7_quantile(values, Fraction(3, 4)),
            }
        else:
            raise ValueError(f"Unknown boundary rule: {boundary_rule}")

    band_overlap = boundary_rule != "median" and any(
        threshold["low"] is not None and threshold["high"] is not None and threshold["low"] >= threshold["high"]
        for threshold in thresholds.values()
    )
    dimension_missing = any(scores is None for scores in dimension_scores.values())
    if dimension_missing:
        status = "NOT ESTIMABLE"
        status_reason = "At least one dimension has no nonconstant approved indicator"
    elif band_overlap:
        status = "NOT ESTIMABLE"
        status_reason = "Low and high percentile cut-offs coincide; mutually exclusive profiles cannot be assigned"
    else:
        status = "COMPLETE"
        status_reason = "All approved run-specific calculations are estimable"

    supplier_rows: list[dict[str, Any]] = []
    profile_counts: Counter[str] = Counter()
    diagnostic_counts: Counter[str] = Counter()
    middle_n = 0
    ambiguous_n = 0
    unclassified_n = 0

    for supplier_id in supplier_ids:
        d_score = None if dimension_scores["Diversification"] is None else dimension_scores["Diversification"][supplier_id]
        e_score = None if dimension_scores["Embeddedness"] is None else dimension_scores["Embeddedness"][supplier_id]
        d_position = "Unclassified"
        e_position = "Unclassified"
        profile = "Unclassified - incomplete structural measures"
        classification_status = "Unclassified"

        def band_position(value: Decimal, low: Decimal, high: Decimal) -> str:
            if low >= high:
                if value < low:
                    return "Low"
                if value > high:
                    return "High"
                return "Ambiguous - coincident cut-offs"
            if value <= low:
                return "Low"
            if value >= high:
                return "High"
            return "Middle"

        if boundary_rule == "median":
            if d_score is not None:
                d_position = "Concentrated" if d_score <= thresholds["Diversification"]["low"] else "Diversified"  # type: ignore[operator]
            if e_score is not None:
                e_position = "Peripheral" if e_score <= thresholds["Embeddedness"]["low"] else "Embedded"  # type: ignore[operator]
            if d_score is None or e_score is None:
                unclassified_n += 1
            else:
                profile = f"{d_position.lower()} / {e_position.lower()}"
                classification_status = "Classified"
                profile_counts[profile] += 1
        else:
            if d_score is not None:
                d_position = band_position(d_score, thresholds["Diversification"]["low"], thresholds["Diversification"]["high"])  # type: ignore[arg-type]
            if e_score is not None:
                e_position = band_position(e_score, thresholds["Embeddedness"]["low"], thresholds["Embeddedness"]["high"])  # type: ignore[arg-type]
            if d_score is None or e_score is None:
                unclassified_n += 1
            elif "Ambiguous" in d_position or "Ambiguous" in e_position:
                profile = "Not estimable - coincident cut-offs"
                classification_status = "Ambiguous cut-off"
                ambiguous_n += 1
            elif d_position == "Middle" or e_position == "Middle":
                profile = "Middle band - no extreme-profile assignment"
                classification_status = "Middle band"
                middle_n += 1
            else:
                d_label = "concentrated" if d_position == "Low" else "diversified"
                e_label = "peripheral" if e_position == "Low" else "embedded"
                profile = f"{d_label} / {e_label}"
                classification_status = "Diagnostic extreme profile"
                diagnostic_counts[profile] += 1

        supplier_rows.append(
            {
                "Run_ID": run_id,
                "Network_Spec_ID": network["network_spec_id"],
                "Population_ID": network["population_id"],
                "Supplier_ID": supplier_id,
                "Category_Breadth": breadth[supplier_id],
                "Pielou_Evenness": display_number(evenness[supplier_id]),
                "Strength": display_number(network["strength"][supplier_id]),
                "Normalized_Betweenness": display_number(network["betweenness"][supplier_id]),
                "Breadth_Transformed": None if transformed["Category_Breadth"] is None else display_number(transformed["Category_Breadth"][supplier_id]),
                "Evenness_Transformed": None if transformed["Pielou_Evenness"] is None else display_number(transformed["Pielou_Evenness"][supplier_id]),
                "Strength_Transformed": None if transformed["Strength"] is None else display_number(transformed["Strength"][supplier_id]),
                "Betweenness_Transformed": None if transformed["Normalized_Betweenness"] is None else display_number(transformed["Normalized_Betweenness"][supplier_id]),
                "Diversification_Score": display_number(d_score),
                "Embeddedness_Score": display_number(e_score),
                "Diversification_Position": d_position,
                "Embeddedness_Position": e_position,
                "Profile": profile,
                "Classification_Status": classification_status,
            }
        )

    classified_n = sum(profile_counts.values())
    diagnostic_assigned_n = sum(diagnostic_counts.values())
    if boundary_rule == "median" and classified_n + unclassified_n != len(supplier_ids):
        raise ValueError(f"{run_id} profile population does not reconcile")
    if boundary_rule != "median" and diagnostic_assigned_n + middle_n + ambiguous_n + unclassified_n != len(supplier_ids):
        raise ValueError(f"{run_id} band population does not reconcile")

    return {
        "run_id": run_id,
        "title": title,
        "a3_item": a3_item,
        "run_type": run_type,
        "network_spec_id": network["network_spec_id"],
        "population_id": network["population_id"],
        "transformation": transformation,
        "boundary_rule": boundary_rule,
        "remove_indicator": remove_indicator,
        "requested_diversification_weights": [display_number(value) for value in diversification_weights],
        "requested_embeddedness_weights": [display_number(value) for value in embeddedness_weights],
        "effective_weights": {
            dimension: {name: display_number(value) for name, value in weights.items()}
            for dimension, weights in effective_weights.items()
        },
        "status": status,
        "status_reason": status_reason,
        "link_n": network["link_n"],
        "supplier_n": network["supplier_n"],
        "pair_n": network["pair_n"],
        "grain_n": network["grain_n"],
        "positive_edge_n": network["positive_edge_n"],
        "possible_pair_n": network["possible_pair_n"],
        "density": network["density"],
        "component_n": network["component_n"],
        "component_sizes": network["component_sizes"],
        "isolate_n": network["isolate_n"],
        "zero_variance": zero_variance,
        "raw_summary": {name: summarize(list(values.values())) for name, values in indicators.items()},
        "dimension_summary": {
            dimension: summarize([] if scores is None else list(scores.values()))
            for dimension, scores in dimension_scores.items()
        },
        "thresholds": {
            dimension: {name: display_number(value) for name, value in values.items()}
            for dimension, values in thresholds.items()
        },
        "profile_counts": {profile: profile_counts.get(profile, 0) for profile in PROFILE_ORDER},
        "diagnostic_extreme_profile_counts": {profile: diagnostic_counts.get(profile, 0) for profile in PROFILE_ORDER},
        "classified_n": classified_n,
        "diagnostic_extreme_assigned_n": diagnostic_assigned_n,
        "middle_band_n": middle_n,
        "ambiguous_cutoff_n": ambiguous_n,
        "unclassified_n": unclassified_n,
        "supplier_rows": supplier_rows,
    }


def add_stability(run: dict[str, Any], primary: dict[str, Any]) -> None:
    primary_by_supplier = {row["Supplier_ID"]: row for row in primary["supplier_rows"]}
    run_by_supplier = {row["Supplier_ID"]: row for row in run["supplier_rows"]}
    common_ids = sorted(set(primary_by_supplier) & set(run_by_supplier))
    comparable = []
    d_comparable = []
    e_comparable = []
    for supplier_id in common_ids:
        primary_row = primary_by_supplier[supplier_id]
        run_row = run_by_supplier[supplier_id]
        if run_row["Profile"] in PROFILE_ORDER and primary_row["Profile"] in PROFILE_ORDER:
            comparable.append(supplier_id)
        if run_row["Diversification_Position"] in {"Concentrated", "Diversified", "Low", "High"}:
            d_comparable.append(supplier_id)
        if run_row["Embeddedness_Position"] in {"Peripheral", "Embedded", "Low", "High"}:
            e_comparable.append(supplier_id)

    def normalized_d(position: str) -> str:
        return "Concentrated" if position in {"Concentrated", "Low"} else "Diversified"

    def normalized_e(position: str) -> str:
        return "Peripheral" if position in {"Peripheral", "Low"} else "Embedded"

    same_profile_n = sum(run_by_supplier[supplier_id]["Profile"] == primary_by_supplier[supplier_id]["Profile"] for supplier_id in comparable)
    d_same_n = sum(
        normalized_d(run_by_supplier[supplier_id]["Diversification_Position"])
        == normalized_d(primary_by_supplier[supplier_id]["Diversification_Position"])
        for supplier_id in d_comparable
    )
    e_same_n = sum(
        normalized_e(run_by_supplier[supplier_id]["Embeddedness_Position"])
        == normalized_e(primary_by_supplier[supplier_id]["Embeddedness_Position"])
        for supplier_id in e_comparable
    )
    profiles_estimable = run["status"] == "COMPLETE"
    diagnostic_profile_n = len(comparable) if not profiles_estimable and run["boundary_rule"] != "median" else 0
    diagnostic_profile_same_n = same_profile_n if diagnostic_profile_n else 0
    run["stability"] = {
        "common_supplier_n": len(common_ids),
        "profile_comparison_n": len(comparable) if profiles_estimable else 0,
        "same_profile_n": same_profile_n if profiles_estimable else 0,
        "same_profile_rate": None if not profiles_estimable or not comparable else same_profile_n / len(comparable),
        "diagnostic_subset_profile_comparison_n": diagnostic_profile_n,
        "diagnostic_subset_same_profile_n": diagnostic_profile_same_n,
        "diagnostic_subset_same_profile_rate": None if not diagnostic_profile_n else diagnostic_profile_same_n / diagnostic_profile_n,
        "diagnostic_subset_coverage_rate": None if not diagnostic_profile_n else diagnostic_profile_n / len(common_ids),
        "diversification_side_comparison_n": len(d_comparable),
        "diversification_side_same_n": d_same_n,
        "diversification_side_same_rate": None if not d_comparable else d_same_n / len(d_comparable),
        "embeddedness_side_comparison_n": len(e_comparable),
        "embeddedness_side_same_n": e_same_n,
        "embeddedness_side_same_rate": None if not e_comparable else e_same_n / len(e_comparable),
        "primary_only_supplier_n": len(set(primary_by_supplier) - set(run_by_supplier)),
        "sensitivity_only_supplier_n": len(set(run_by_supplier) - set(primary_by_supplier)),
    }


def calculate_all() -> dict[str, Any]:
    if sha256_file(SOURCE_PATH) != EXPECTED_HASHES["analytical_master"]:
        raise ValueError("Frozen analytical-master hash mismatch")
    if sha256_file(C4_WORKBOOK) != EXPECTED_HASHES["c4_workbook"]:
        raise ValueError("C4 workbook hash mismatch")
    if sha256_file(B1_REGISTER) != EXPECTED_HASHES["b1_register"]:
        raise ValueError("B1 taxonomy-register hash mismatch")
    if sha256_file(B4_REGISTER) != EXPECTED_HASHES["b4_register"]:
        raise ValueError("B4 denominator-register hash mismatch")

    c3 = load_module(C3_SCRIPT, "c3_for_c5")
    c4 = load_module(C4_SCRIPT, "c4_for_c5")
    c4_result = c4.calculate_scores()
    source_rows = c3.read_sheet(SOURCE_PATH, "Link_Master_500")
    b4_rows = c3.read_sheet(B4_REGISTER, "Link_Eligibility_500")
    if len(source_rows) != 500 or len({norm(row["Link_ID"]) for row in source_rows}) != 500:
        raise ValueError("Frozen Link_Master_500 grain changed")
    if len(b4_rows) != 500 or len({norm(row["Link_ID"]) for row in b4_rows}) != 500:
        raise ValueError("B4 Link_Eligibility_500 grain changed")

    populations = {
        "primary": select_population(source_rows, "primary"),
        "nonexcluded": select_population(source_rows, "nonexcluded"),
        "same_bmw": select_population(source_rows, "same_bmw"),
        "exact_bmw": select_population(source_rows, "exact_bmw"),
        "tax18_included": select_population(source_rows, "tax18_included"),
    }
    b4_field_by_population = {
        "primary": "Structural_Primary_Eligible",
        "nonexcluded": "Visibility_Tax_CTL_Eligible",
        "same_bmw": "Same_Entity_CTL_Eligible",
        "exact_bmw": "Exact_CTL_Eligible",
        "tax18_included": "B1_TAX18_Sensitivity_Eligible",
    }
    for population_key, b4_field in b4_field_by_population.items():
        calculated_ids = {norm(row["Link_ID"]) for row in populations[population_key]}
        authoritative_ids = {norm(row["Link_ID"]) for row in b4_rows if int(row.get(b4_field) or 0) == 1}
        if calculated_ids != authoritative_ids:
            missing = sorted(authoritative_ids - calculated_ids)[:10]
            extra = sorted(calculated_ids - authoritative_ids)[:10]
            raise ValueError(f"{population_key} differs from B4 {b4_field}; missing={missing}, extra={extra}")
    network_specs = {
        "N00": build_network(c3, "N00", "POP-LINK-CAP-CTL-392", populations["primary"], "Taxonomy_ID", "weighted_jaccard"),
        "N01": build_network(c3, "N01", "POP-LINK-CAP-CTL-392", populations["primary"], "Taxonomy_ID", "cosine"),
        "N02": build_network(c3, "N02", "POP-LINK-CAP-CTL-392", populations["primary"], "Technology_Family", "weighted_jaccard"),
        "N03": build_network(c3, "N03", "POP-LINK-NONEX-CTL-410", populations["nonexcluded"], "Taxonomy_ID", "weighted_jaccard"),
        "N04": build_network(c3, "N04", "POP-LINK-SAMEBMW-CTL-157", populations["same_bmw"], "Taxonomy_ID", "weighted_jaccard"),
        "N05": build_network(c3, "N05", "POP-LINK-EXACTBMW-CTL-39", populations["exact_bmw"], "Taxonomy_ID", "weighted_jaccard"),
        "N06": build_network(c3, "N06", "POP-LINK-CAP-TAX18-426", populations["tax18_included"], "Taxonomy_ID", "weighted_jaccard"),
    }

    run_specs = [
        ("C5-R00", "Primary C4 reproduction", "Reference", "reference", "N00", {}),
        ("C5-R01", "40th/60th profile bands", "A3.9.1", "boundary", "N00", {"boundary_rule": "40_60"}),
        ("C5-R02", "25th/75th extreme profiles", "A3.9.2", "boundary", "N00", {"boundary_rule": "25_75"}),
        ("C5-R03", "Log1p plus min-max transformation", "A3.9.3", "transformation", "N00", {"transformation": "log1p_minmax"}),
        ("C5-R04", "Diversification weights 60/40", "A3.9.4", "weight", "N00", {"diversification_weights": (Fraction(3, 5), Fraction(2, 5))}),
        ("C5-R05", "Diversification weights 40/60", "A3.9.4", "weight", "N00", {"diversification_weights": (Fraction(2, 5), Fraction(3, 5))}),
        ("C5-R06", "Embeddedness weights 60/40", "A3.9.4", "weight", "N00", {"embeddedness_weights": (Fraction(3, 5), Fraction(2, 5))}),
        ("C5-R07", "Embeddedness weights 40/60", "A3.9.4", "weight", "N00", {"embeddedness_weights": (Fraction(2, 5), Fraction(3, 5))}),
        ("C5-R08", "Remove evenness", "A3.9.5", "indicator_removal", "N00", {"remove_indicator": "Pielou_Evenness"}),
        ("C5-R09", "Remove betweenness", "A3.9.5", "indicator_removal", "N00", {"remove_indicator": "Normalized_Betweenness"}),
        ("C5-R10", "Cosine similarity", "A3.9.6", "similarity", "N01", {}),
        ("C5-R11", "Technology-family grain", "A3.9.7", "technology_grain", "N02", {}),
        ("C5-R12", "Non-excluded evidence layer", "A3.9.8", "evidence_layer", "N03", {}),
        ("C5-R13", "Same-entity BMW evidence layer", "A3.9.8", "evidence_layer", "N04", {}),
        ("C5-R14", "Exact BMW-technology evidence layer", "A3.9.8", "evidence_layer", "N05", {}),
        ("C5-R15", "Include TAX-18 as one bucket", "A3.9.9", "taxonomy_review", "N06", {}),
    ]
    runs = [
        calculate_run(run_id, title, a3_item, run_type, network_specs[network_id], **options)
        for run_id, title, a3_item, run_type, network_id, options in run_specs
    ]
    primary = runs[0]
    for run in runs:
        add_stability(run, primary)

    c4_by_supplier = {row["Supplier_ID"]: row for row in c4_result["supplier_scores"]}
    primary_by_supplier = {row["Supplier_ID"]: row for row in primary["supplier_rows"]}
    if set(c4_by_supplier) != set(primary_by_supplier):
        raise ValueError("C4 and C5 primary supplier sets differ")
    primary_mismatch: list[str] = []
    for supplier_id in sorted(c4_by_supplier):
        expected = c4_by_supplier[supplier_id]
        actual = primary_by_supplier[supplier_id]
        numeric_pairs = [
            ("Category_Breadth", "Category_Breadth"),
            ("Pielou_Evenness", "Pielou_Evenness"),
            ("Strength", "Strength"),
            ("Normalized_Betweenness", "Normalized_Betweenness"),
            ("Diversification_Score", "Diversification_Score"),
            ("Embeddedness_Score", "Embeddedness_Score"),
        ]
        if any(abs(float(expected[left]) - float(actual[right])) > 1e-12 for left, right in numeric_pairs):
            primary_mismatch.append(supplier_id)
        if expected["Structural_Profile"] != actual["Profile"]:
            primary_mismatch.append(supplier_id)
    if primary_mismatch:
        raise ValueError(f"C5 primary reproduction differs for {sorted(set(primary_mismatch))[:10]}")

    ordered_rows = [row for row in source_rows if int(row.get("Non_Excluded_Layer") or 0) == 1]
    ordered_ids = {norm(row["Link_ID"]) for row in ordered_rows}
    b4_ordered_ids = {norm(row["Link_ID"]) for row in b4_rows if int(row.get("Non_Excluded_Layer") or 0) == 1}
    non_x1_ids = {norm(row["Link_ID"]) for row in source_rows if norm(row["Evidence_Code"]) != "X1"}
    if ordered_ids != b4_ordered_ids or ordered_ids != non_x1_ids:
        raise ValueError("Non-excluded visibility population differs from B4 or the frozen evidence-code boundary")
    exact_positive = sum(norm(row["Evidence_Code"]) in {"V1", "V2"} for row in ordered_rows)
    bmw_positive = sum(norm(row["Evidence_Code"]) in {"V1", "V2", "P1"} for row in ordered_rows)
    visibility_contrasts = [
        {
            "Run_ID": "C5-V01",
            "A3_Item": "A3.9.10",
            "Contrast": "Exact evidence contrast",
            "Population_ID": "POP-LINK-NONEX-446",
            "Unit": "supplier-technology link",
            "Denominator_N": len(ordered_rows),
            "Positive_Definition": "V1/V2",
            "Positive_N": exact_positive,
            "Other_Definition": "P1/P2/U1",
            "Other_N": len(ordered_rows) - exact_positive,
            "Positive_Share": exact_positive / len(ordered_rows),
            "Status": "COMPLETE - descriptive only",
        },
        {
            "Run_ID": "C5-V02",
            "A3_Item": "A3.9.10",
            "Contrast": "BMW-relationship evidence contrast",
            "Population_ID": "POP-LINK-NONEX-446",
            "Unit": "supplier-technology link",
            "Denominator_N": len(ordered_rows),
            "Positive_Definition": "V1/V2/P1",
            "Positive_N": bmw_positive,
            "Other_Definition": "P2/U1",
            "Other_N": len(ordered_rows) - bmw_positive,
            "Positive_Share": bmw_positive / len(ordered_rows),
            "Status": "COMPLETE - descriptive only",
        },
    ]
    if (len(ordered_rows), exact_positive, bmw_positive) != (446, 40, 160):
        raise ValueError("Visibility contrasts do not reconcile")

    link_input = []
    population_membership = {
        key: {norm(row["Link_ID"]) for row in rows} for key, rows in populations.items()
    }
    for row in sorted(source_rows, key=lambda item: norm(item["Link_ID"])):
        link_id = norm(row["Link_ID"])
        link_input.append(
            {
                "Link_ID": link_id,
                "Supplier_ID": norm(row["Supplier_ID"]),
                "Taxonomy_ID": norm(row["Taxonomy_ID"]),
                "Technology_Family": norm(row["Technology_Family"]),
                "Evidence_Code": norm(row["Evidence_Code"]),
                "Candidate_Layer": int(row["Candidate_Layer"] or 0),
                "Non_Excluded_Layer": int(row["Non_Excluded_Layer"] or 0),
                "Capability_Supported_Layer": int(row["Capability_Supported_Layer"] or 0),
                "Same_Entity_BMW_Relationship_Layer": int(row["Same_Entity_BMW_Relationship_Layer"] or 0),
                "Exact_BMW_Technology_Layer": int(row["Exact_BMW_Technology_Layer"] or 0),
                "Taxonomy_Review_Flag": norm(row["Taxonomy_Review_Flag"]),
                "N00_Primary_Eligible": int(link_id in population_membership["primary"]),
                "N03_Nonexcluded_Eligible": int(link_id in population_membership["nonexcluded"]),
                "N04_SameBMW_Eligible": int(link_id in population_membership["same_bmw"]),
                "N05_ExactBMW_Eligible": int(link_id in population_membership["exact_bmw"]),
                "N06_TAX18_Included_Eligible": int(link_id in population_membership["tax18_included"]),
            }
        )

    expected_profile_counts = {
        "C5-R00": [100, 88, 4, 15],
        "C5-R03": [118, 70, 11, 8],
        "C5-R04": [100, 88, 4, 15],
        "C5-R05": [100, 88, 4, 15],
        "C5-R06": [109, 79, 6, 13],
        "C5-R07": [134, 54, 2, 17],
        "C5-R08": [100, 88, 4, 15],
        "C5-R09": [88, 100, 17, 2],
        "C5-R10": [106, 82, 2, 17],
        "C5-R11": [167, 27, 7, 6],
        "C5-R12": [109, 90, 5, 16],
        "C5-R13": [23, 16, 3, 7],
        "C5-R15": [131, 80, 5, 15],
    }
    by_run = {run["run_id"]: run for run in runs}
    for run_id, counts in expected_profile_counts.items():
        actual = [by_run[run_id]["profile_counts"][profile] for profile in PROFILE_ORDER]
        if actual != counts:
            raise ValueError(f"{run_id} profile counts: expected {counts}, found {actual}")
    if by_run["C5-R01"]["status"] != "NOT ESTIMABLE" or by_run["C5-R01"]["ambiguous_cutoff_n"] != 188:
        raise ValueError("C5-R01 collapsed-cutoff result changed")
    if by_run["C5-R02"]["status"] != "NOT ESTIMABLE" or by_run["C5-R02"]["ambiguous_cutoff_n"] != 188:
        raise ValueError("C5-R02 collapsed-cutoff result changed")
    if by_run["C5-R14"]["status"] != "NOT ESTIMABLE" or by_run["C5-R14"]["unclassified_n"] != 35:
        raise ValueError("C5-R14 zero-variance result changed")
    if by_run["C5-R01"]["stability"]["profile_comparison_n"] != 0 or by_run["C5-R01"]["stability"]["diagnostic_subset_profile_comparison_n"] != 16:
        raise ValueError("C5-R01 diagnostic agreement scope changed")
    if by_run["C5-R02"]["stability"]["profile_comparison_n"] != 0 or by_run["C5-R02"]["stability"]["diagnostic_subset_profile_comparison_n"] != 9:
        raise ValueError("C5-R02 diagnostic agreement scope changed")
    if (
        by_run["C5-R14"]["stability"]["diversification_side_comparison_n"] != 0
        or by_run["C5-R14"]["stability"]["embeddedness_side_comparison_n"] != 35
        or by_run["C5-R14"]["stability"]["embeddedness_side_same_n"] != 10
    ):
        raise ValueError("C5-R14 partial embeddedness comparison changed")

    expected_networks = {
        "N00": (3522, 21321, [193, 8, 4, 2], 0),
        "N01": (3522, 21321, [193, 8, 4, 2], 0),
        "N02": (16509, 21321, [207], 0),
        "N03": (4093, 24090, [206, 8, 4, 2], 0),
        "N04": (210, 1176, [36, 8, 2, 2, 1], 1),
        "N05": (56, 595, [8, 6, 3, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1], 4),
        "N06": (3945, 26565, [217, 8, 4, 2], 0),
    }
    for spec_id, expected in expected_networks.items():
        network = network_specs[spec_id]
        actual = (
            network["positive_edge_n"],
            network["possible_pair_n"],
            network["component_sizes"],
            network["isolate_n"],
        )
        if actual != expected:
            raise ValueError(f"{spec_id} network diagnostics: expected {expected}, found {actual}")

    emitted_schema_fields = set(link_input[0]) | set(visibility_contrasts[0])
    for run in runs:
        emitted_schema_fields.update(run["supplier_rows"][0])
    for network in network_specs.values():
        emitted_schema_fields.update(network["pair_rows"][0])
        if network["projection_rows"]:
            emitted_schema_fields.update(network["projection_rows"][0])
    forbidden_output_fields = {
        "Overall_Score",
        "Supplier_Visibility_Score",
        "Visibility_Complexity_Association",
        "P_Value",
        "Outcome",
        "Target",
        "Random_Forest_Prediction",
    }
    forbidden_schema_fields = emitted_schema_fields & forbidden_output_fields
    if forbidden_schema_fields:
        raise ValueError(f"Forbidden C5 output fields emitted: {sorted(forbidden_schema_fields)}")

    qa_checks = {
        "frozen_analytical_master_hash_match": True,
        "c4_workbook_hash_match": True,
        "b1_register_hash_match": True,
        "b4_register_hash_match": True,
        "b4_population_link_id_sets_match": True,
        "visibility_nonexcluded_link_id_set_match": True,
        "frozen_link_rows_500_unique": len(link_input) == 500 and len({row["Link_ID"] for row in link_input}) == 500,
        "network_spec_count_7": len(network_specs) == 7,
        "structural_run_count_16": len(runs) == 16,
        "visibility_contrast_count_2": len(visibility_contrasts) == 2,
        "primary_reproduces_c4": not primary_mismatch,
        "boundary_40_60_not_estimable": by_run["C5-R01"]["status"] == "NOT ESTIMABLE",
        "boundary_25_75_not_estimable": by_run["C5-R02"]["status"] == "NOT ESTIMABLE",
        "exact_layer_profiles_not_estimable": by_run["C5-R14"]["status"] == "NOT ESTIMABLE",
        "exact_layer_diversification_both_constant": by_run["C5-R14"]["zero_variance"]["Category_Breadth"] and by_run["C5-R14"]["zero_variance"]["Pielou_Evenness"],
        "tax18_adds_34_capability_links": by_run["C5-R15"]["link_n"] - primary["link_n"] == 34,
        "visibility_exact_40_of_446": exact_positive == 40 and len(ordered_rows) == 446,
        "visibility_bmw_160_of_446": bmw_positive == 160 and len(ordered_rows) == 446,
        "emitted_schema_forbidden_fields_absent": not forbidden_schema_fields,
        "design_declaration_no_overall_cross_dimension_score": True,
        "design_declaration_no_supplier_visibility_aggregation": True,
        "design_declaration_no_visibility_complexity_association": True,
        "design_declaration_no_inferential_test": True,
        "design_declaration_random_forest_not_run": True,
        "finer_normalized_technology_gate_not_run": True,
    }
    if not all(qa_checks.values()):
        raise ValueError(f"C5 QA failure: {qa_checks}")

    serializable_networks = {}
    for spec_id, network in network_specs.items():
        serializable_networks[spec_id] = {
            key: value
            for key, value in network.items()
            if key not in {"vectors", "strength", "betweenness"}
        }

    return {
        "manifest": {
            "checklist_step": "C5",
            "calculation_date": "2026-08-28",
            "source_sha256": sha256_file(SOURCE_PATH),
            "c4_workbook_sha256": sha256_file(C4_WORKBOOK),
            "b1_register_sha256": sha256_file(B1_REGISTER),
            "b4_register_sha256": sha256_file(B4_REGISTER),
            "sensitivity_design": "One factor at a time; no full factorial combinations and no post-result alternatives",
            "quantile_method": "Hyndman-Fan Type 7 / Excel PERCENTILE.INC",
            "cosine_precision": "Decimal precision 100; equal shortest-path tolerance 1e-70 relative to scale",
            "numeric_representation": "Weighted-Jaccard quantities are exact rationals; cosine quantities are 100-digit high-precision Decimal approximations",
            "band_overlap_rule": "If lower >= upper for a required dimension, full extreme profiles are not estimable; no tie precedence is invented",
            "visibility_rule": "Two link-level descriptive contrasts only; no supplier aggregation or association",
            "finer_normalized_technology_status": "NOT EXECUTED - exact frozen field and duplicate rule remain outside the approved specification",
        },
        "link_input": link_input,
        "network_specs": serializable_networks,
        "runs": runs,
        "visibility_contrasts": visibility_contrasts,
        "deferred_register": [
            {
                "Run_ID": "C5-G01",
                "A3_Item": "A3.9.7 conditional extension",
                "Specification": "Finer normalized-technology grain",
                "Status": "NOT EXECUTED",
                "Reason": "No approved exact frozen field or duplicate-handling rule; no new semantic remapping is permitted",
            }
        ],
        "qa_checks": qa_checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Ignored local path for the full deterministic JSON payload; requires --full-output")
    parser.add_argument("--full-output", action="store_true", help="Permit a row-level JSON export under the repository tmp directory")
    parser.add_argument("--summary-only", action="store_true", help="Deprecated compatibility flag; compact output is now the default")
    args = parser.parse_args()

    if args.output and not args.full_output:
        parser.error("--output contains row-level records and therefore requires --full-output")
    if args.full_output and not args.output:
        parser.error("--full-output requires --output under the repository tmp directory")

    result = calculate_all()
    if args.output:
        output_path = require_private_output(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    printable = {
        "manifest": result["manifest"],
        "runs": [
            {
                key: run[key]
                for key in [
                    "run_id", "title", "status", "status_reason", "link_n", "supplier_n", "pair_n",
                    "grain_n", "positive_edge_n", "isolate_n", "thresholds", "profile_counts",
                    "diagnostic_extreme_profile_counts", "classified_n", "diagnostic_extreme_assigned_n",
                    "middle_band_n", "ambiguous_cutoff_n", "unclassified_n", "stability",
                ]
            }
            for run in result["runs"]
        ],
        "visibility_contrasts": result["visibility_contrasts"],
        "deferred_register": result["deferred_register"],
        "qa_checks": result["qa_checks"],
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
