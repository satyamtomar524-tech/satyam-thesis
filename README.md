# Beyond Blind Spots: Using Business Analytics to Assess Visibility and Coordination Complexity in BMW's Supplier Technology Ecosystem

This repository is the reproducible research workspace for Satyam Tomar's master's thesis. It connects evidence collection, data preparation, analysis, figures, tables, and chapter writing while keeping the thesis's evidential limits explicit.

## Research boundary

The empirical object is a publicly evidenced representation of a supplier technology ecosystem. Repository outputs may identify observable evidence gaps and structural coordination-complexity proxies. They must not be presented as proof of BMW's complete supplier network, BMW's internal visibility, supplier performance, coordination failure, or verified supplier-to-supplier commercial relationships.

## Working flow

```text
Research question
      ↓
Public evidence and provenance log
      ↓
Raw/local and external evidence → cleaning scripts → cleaned data
      ↓
Notebooks and reproducible analyses → validated final data
      ↓
Figures and tables → results → discussion → conclusion
      ↓
Reviewed commit and GitHub history
```

## Repository map

| Path | Purpose |
| --- | --- |
| `data/raw/` | Local-only source material; contents are ignored by Git |
| `data/external/` | Public external evidence or documented extracts that are safe to retain |
| `data/cleaned/` | Script-generated, normalized data |
| `data/final/` | Validated analysis-ready tables |
| `scripts/` | Reusable Python, R, and SQL transformations |
| `notebooks/` | Reproducible exploration and model experiments |
| `analysis/` | Descriptive, supplier, complexity, and statistical outputs |
| `figures/` and `tables/` | Thesis-ready visual and tabular outputs |
| `thesis/` | Chapter working files |
| `documentation/` | Data dictionary, methodology decisions, workflow, and analysis log |
| `powerbi/`, `spss/`, `knime/` | Tool-specific project artifacts |
| `references/` | Reference-management exports and source notes |

## Reproducibility rules

1. Preserve reported source values; perform normalization only in derived data.
2. Give every supplier-technology record a stable identifier and provenance record.
3. Record source URL, source type, publication date when known, retrieval date, and verification status.
4. Generate cleaned and final data with scripts or documented notebook steps.
5. Keep model features separate from any observed target variable and document leakage checks.
6. Record every consequential analytical decision in `documentation/analysis_log.md`.
7. Commit only material that is public, licensed, authorized, or safely derived.

## Confidentiality

Do not commit BMW-origin workbooks, project briefs, personal records, or other restricted material without written authorization. The known local thesis workbook, thesis document, and official confirmation are intentionally excluded from Git tracking by `.gitignore`.

## Current status

The project structure and governance files are initialized. Data ingestion, source verification, quality assessment, and modeling remain separate controlled steps.
