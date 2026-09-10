# Thesis finalisation progress

Updated 10 September 2026. Status: active; not submission-ready.

## Objective and authority

Complete every thesis section to a defensible academic standard, with traceable evidence, justified methods, reproducible calculations and consistent conclusions. Necessary revisions and routine decisions were authorized on 10 September 2026. This supersedes earlier workflow pauses, but does not authorize invented findings, declarations of personal review, signatures or disclosure of restricted material.

The registered thesis title remains unchanged. Submission, publication permissions and student declarations must be supported by actual evidence, not inferred from this authorization.

## Current work

- Preserve the original evidence, correction snapshots and historical manuscript versions.
- Independently check the corrected calculation rather than relying solely on previous validation reports.
- Recheck the primary sources behind evidence decisions, recording access limits and precise claim boundaries.
- Add a publication-window sensitivity with explicit treatment of unknown, partial and event-only dates. This is a post-review test, not a pre-specified historical result.
- Integrate the approved evidence model, results, mathematical definitions and limitations throughout the manuscript, figures and appendices.
- Review every section and citation, verify the final rendered Word and PDF versions, and reconcile the submission requirements.

## Work completed in this phase

The new date-sensitivity implementation and synthetic regression tests are in `04_ANALYSIS/12_FINALISATION_20260910/`. The implementation reads the retained review files without changing them. It compares the non-temporal eligible population with a population restricted to recorded capability-publication intervals wholly inside the study window. Tests cover partial dates, cutoff boundaries, invalid dates, event dates, duplicate claims, missing evidence and empty graph denominators.

Three previously identified technology mismatches have been checked against the live official sources. Their local evidence record distinguishes the activity the source supports from the different candidate technology it does not establish. This sample is not verification of every evidence record.

An independent implementation has reproduced every primary supplier's four indicators, percentile transformations, two dimension scores and profile label, plus the binary-weight and inherited-origin sensitivity comparisons. No arithmetic defect was found within that scope. Exact rational similarity sums and shortest-path ties matter; numerical agreement does not clear unresolved source interpretations. The remaining sensitivity specifications are not covered by this independent check.

Manuscript-source insertions for the date test and mathematical definitions, including a hypothetical worked example, are saved locally under `02_MANUSCRIPT_APA/revision_source/`. They still require integration into the Word manuscript and final cross-artifact verification.

## Completion requirements

| Requirement | Current status | Evidence needed for completion |
|---|---|---|
| Every manuscript section reviewed | In progress | Section-by-section coverage with resolved material findings |
| Each retained empirical claim supported | In progress | Claim-specific source review with identity, technology, relationship, date and distinctness decisions |
| Method choices justified | In progress | Explicit constructs, eligibility rules, formulas, assumptions and sensitivity rationale |
| Calculations verified | In progress | Independent recomputation from selected rows and relevant boundary tests |
| Results, figures and conclusions consistent | Pending integration | Cross-artifact reconciliation against the final selected dataset |
| Academic citations support their passages | Pending full audit | Full-text support and accurate bibliographic and pinpoint information |
| Word and PDF ready | Not ready | Final pagination, complete visual review, cross-references and word-count verification |
| Declarations and submission requirements | Open | Accurate AI-use record, student review and required personal/official confirmations |
| GitHub updated safely | In progress | Reviewed commits and verified remote state, with restricted files excluded |
| Final no-known-unresolved-issue audit | Not achieved | Requirement-level evidence; unavoidable limitations explicitly documented |

## Repository boundary

The repository is private, but privacy does not itself establish university or third-party publication permission. Manuscripts, raw inputs, row-level evidence, administrative documents and detailed audit outputs remain local under the existing ignore rules. Only reviewed code, synthetic tests and disclosure-safe documentation are eligible for commits. Existing uncommitted folder-reorganization changes are preserved and are not automatically included in a new commit.

## Resume

Use the current local finalisation evidence alongside the September 7 correction snapshot. Do not infer that an old `DONE`, `PASS` or manuscript filename means that finalisation is complete. Computational checks do not independently verify source meaning, and completed source checks do not establish student understanding.
