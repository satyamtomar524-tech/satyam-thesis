# Methodology notes

## Fixed analytical boundary

The project studies a publicly evidenced representation of BMW's supplier technology ecosystem. It does not reconstruct BMW's complete confidential network and does not measure BMW's internal information systems, actual coordination effort, operational failure, delay, cost, or resilience.

## Data architecture

Two evidence streams may be collected but should be integrated through stable identifiers rather than forced into one flat table:

1. supplier-technology relationships from the available supplier data;
2. independently verified public evidence about supplier products, components, OEM/customer relationships, locations, and corporate groups.

The core analytical grain remains one supplier-technology relationship. Evidence and customer relationships are separate linked tables so that one claim can have several sources without duplicating the analytical row.

## Evidence hierarchy

Prefer peer-reviewed literature for theory, official BMW sources for BMW-specific facts, official supplier sources for supplier-specific facts, and authoritative institutional or trade sources for context. General secondary sources are supporting evidence only when their limits are explicit.

## Quality gates

Before a dataset moves to `data/final/`, verify:

- documented provenance and permission status;
- stable row grain and identifiers;
- supplier entity-resolution decisions;
- duplicate and missing-value rules;
- direct evidence for each relationship claim;
- timestamps and evidence recency where available;
- reproducible transformation steps;
- a record of unresolved conflicts and exclusions.

## Analytical sequence

1. Inventory sources and define the admissible sample.
2. Profile completeness, duplicates, inconsistencies, and coverage.
3. Resolve supplier identities without overwriting reported names.
4. Build the supplier-technology bipartite representation.
5. Calculate descriptive and network measures.
6. Define observable-visibility indicators with a transparent rubric.
7. Define structural coordination-complexity proxies.
8. Test weighting, scaling, missing-data decisions, and thresholds.
9. Interpret high-complexity/low-visibility combinations as verification priorities, not confirmed BMW failures.

## Machine-learning gate

Random forest or another supervised method may be used only after defining a valid observed target that is not constructed from the same predictor fields. Sample size, class balance, leakage, train/test separation, cross-validation, baseline performance, explainability, and robustness must be documented. Without those conditions, use transparent descriptive, network, clustering, or sensitivity analysis instead of presenting a black-box output as discovery.

## Open decisions

- final empirical sample and inclusion rule;
- final visibility rubric and evidence-strength rubric;
- supplier-group resolution rule;
- admissible public relationship types;
- model target, if a defensible supervised-learning target becomes available;
- thresholds and weighting scheme after sensitivity analysis.
