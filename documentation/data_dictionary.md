# Data dictionary

This is the controlled field specification for the unified supplier-technology evidence dataset. Fields may be added only when their meaning, source, and admissible interpretation are documented.

## Core supplier-technology table

Recommended file: `data/final/supplier_technology_links.csv`

Unit of analysis: one distinct supplier-technology relationship in the available evidence representation.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `supplier_technology_link_id` | string | Yes | Stable unique identifier for the analytical row |
| `supplier_id` | string | Yes | Stable supplier identifier after entity resolution |
| `supplier_name_reported` | string | Yes | Supplier name exactly as shown in the source |
| `supplier_name_normalized` | string | Yes | Derived name used for matching and aggregation |
| `supplier_group_id` | string | No | Group or parent-company identifier when verified |
| `technology_path_reported` | string | Yes | Full technology path exactly as represented |
| `technology_category` | string | No | Derived top-level or harmonized category |
| `technology_role` | string | No | Evidence-supported description of what is supplied or enabled |
| `source_record_id` | string | Yes | Link to the evidence register |
| `verification_status` | category | Yes | `verified`, `partially_verified`, `unverified`, or `conflicting` |
| `identity_confidence` | number | No | Transparent confidence score with documented rubric |
| `role_confidence` | number | No | Transparent confidence score for the stated technology role |
| `notes` | string | No | Concise qualification or unresolved ambiguity |

## Evidence register

Recommended file: `data/final/evidence_register.csv`

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `source_record_id` | string | Yes | Stable unique evidence identifier |
| `entity_id` | string | Yes | Supplier or organization supported by the source |
| `claim_type` | category | Yes | Identity, technology role, OEM/customer relationship, location, or other defined claim |
| `claim_text` | string | Yes | Narrow factual claim being evaluated |
| `source_title` | string | Yes | Page, document, or database title |
| `source_url` | string | Yes when online | Direct source link |
| `source_type` | category | Yes | Official OEM, official supplier, institutional, trade, academic, or secondary |
| `publisher` | string | Yes | Organization responsible for the source |
| `publication_date` | date | No | Publication or last-update date when available |
| `retrieved_at` | date | Yes | Date the evidence was accessed |
| `evidence_excerpt` | string | No | Short compliant extract or structured paraphrase |
| `supports_claim` | boolean | Yes | Whether the source directly supports the narrow claim |
| `independent_source_count` | integer | No | Count of independent sources supporting the claim |
| `evidence_strength` | category | Yes | Rubric-based strength, not a claim of truth by itself |
| `review_status` | category | Yes | `pending`, `accepted`, `rejected`, or `needs_review` |

## Customer or OEM relationship evidence

Recommended file: `data/final/customer_relationship_evidence.csv`

Keep this separate from the supplier-technology table. A shared technology category is not a commercial link.

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `relationship_evidence_id` | string | Yes | Stable unique relationship-evidence identifier |
| `supplier_id` | string | Yes | Verified supplier entity |
| `customer_entity_id` | string | Yes | OEM or other customer named by the evidence |
| `relationship_type` | category | Yes | Direct supply, project award, product use, partnership, or other defined type |
| `product_or_component` | string | No | Paint, body system, door module, electronics, machinery, or other supported item |
| `relationship_start` | date | No | Start date only when directly evidenced |
| `relationship_end` | date | No | End date only when directly evidenced |
| `source_record_id` | string | Yes | Link to the evidence register |
| `verification_status` | category | Yes | Verification outcome for this relationship claim |

## Analytical outputs

Derived metrics may include supplier degree, technology degree, category breadth, path depth, evidence completeness, recency, and sensitivity-tested visibility or complexity scores. Every metric requires a formula, data grain, missing-value rule, and interpretation boundary in `methodology_notes.md` before thesis use.
