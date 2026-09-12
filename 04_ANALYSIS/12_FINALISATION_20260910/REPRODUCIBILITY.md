# V5 local calculation rerun

This is the current **V5 calculation path**, not the historical D4/392-claim pipeline. It does not recreate supplier source decisions or certify the thesis. Private inputs and results stay local; never publish them to make a checkout runnable.

## Requirements

The core rerun was verified with **Python 3.12.14 and openpyxl 3.1.5**. No Excel, Word, C4 runner or confidential original workbook is opened by this path. The C3 helper imports openpyxl even though the V5 orchestrator supplies preserved JSON tables. Separate Word-equation tests need python-docx and lxml; figures and PDF export have additional presentation dependencies.

The code checkout must contain the six finalisation modules `recalculate_finalisation.py`, `apply_reviewed_corrections.py`, `date_sensitivity.py`, `apply_scope_amendments.py`, `evidence_holds.py` and `distinctness_holds.py`, plus:

- `04_ANALYSIS/11_CORRECTION_REVIEW_V2/revision_calculations.py`
- `04_ANALYSIS/05_NETWORK_ANALYSIS/C3_construct_network.py`
- `04_ANALYSIS/07_SENSITIVITY_ANALYSIS/C5_run_sensitivity_tests.py`

An authorised local custodian must restore these **private** dependencies at their preserved relative paths:

- `04_ANALYSIS/11_CORRECTION_REVIEW_V2/revision_inputs.json` and `revision_config.json`;
- `local/v4/revised_decisions.json` beneath this folder;
- `local/semantic_review_20260911/reviewed_corrections_v5.json` and every file named in its `required_files` list (11 reviewed evidence files).

The correction package checks the input-ledger/input-table hashes and every required evidence-file hash. A public checkout alone is intentionally insufficient. Do not substitute other workbooks or live webpages for those pinned inputs.

## Run without replacing frozen results

From the repository root, use an authorised Python environment with the requirements above. Choose a **new, nonexistent** output folder under this folder's ignored `local/` tree:

```powershell
python -B 04_ANALYSIS/12_FINALISATION_20260910/recalculate_finalisation.py --revision v5 --output 04_ANALYSIS/12_FINALISATION_20260910/local/v5_rerun_20260912
```

If that destination already exists, choose a different name. Existing files/directories, the `local/` root itself, destinations inside frozen `v3`/`v4`/`v5` subtrees, and destinations outside that private tree are rejected. Relative paths resolve from the current directory. Omitting `--output` retains the historical destination `local/<revision>` and refuses to overwrite it. **Omitting `--revision` still selects V4 for backward compatibility, not V5.**

The new directory contains the revised ledger, calculation JSON, date analysis, validation summary and `execution_receipt.json`. The receipt records all nine code hashes, actual runtime, input and output hashes, and separate canonical-content hashes. It is local execution provenance, not independent source or mathematical verification.

## Compare results correctly

The independently executed local rerun reproduced the complete V5 numerical JSON content: 316 primary claims, 177 suppliers, 218 memberships, 2,577/15,576 positive/possible overlap pairs and profiles 96/64/2/15. The ledger and date output were byte-identical.

The calculation JSON can have a different raw SHA-256 solely because the unchanged engine constructs two origin-profile count dictionaries from sets. Compare parsed JSON or the receipt's `semantic_json_sha256` as well as preserving raw hashes. The frozen V5 calculation's canonical-content SHA-256 is:

```text
979ad7898a5b115e3f6139f42b6ca7bd031b904f3affac3c331d6fbff3334a27
```

Canonical content uses UTF-8 `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`. No historical JSON is rewritten. The frozen validation summary embeds raw output hashes, so that summary can also differ when only serialization order changes.

**Presentation limitation:** the existing local V5 figure/table builder pins the frozen raw calculation hash and therefore rejects some numerically identical fresh reruns. It also depends on predecessor figure/DOCX files and a machine-specific Node/sharp runtime. It is not an end-to-end rerun command. Do not overwrite its pins or outputs; a separately reviewed successor input/output contract is required for fresh figure regeneration. The verified thesis figures remain bound to their existing manifests.

## Synthetic checks

```powershell
python -B -m unittest discover -s 04_ANALYSIS/12_FINALISATION_20260910 -p test_recalculation_cli.py
```

These tests use synthetic temporary paths/data and check output containment, no-overwrite behavior, V4 compatibility, the nine-file closure and semantic hashing. They do not load private thesis records. On Windows without symlink privilege, the symlink-specific test reports a skip; the other containment tests still run.

## Current distinct-score metadata supplement

The separate sensitivity audit verified N01–N06 centralities and R01–R15 scores, profiles and agreement outputs. It found a diagnostic-count limitation: Decimal arithmetic can represent mathematically equal weighted-midrank scores differently, overcounting `dimension_summary.Embeddedness.distinct_n`. This does not change the verified displayed scores, profiles, thresholds or agreement percentages.

`correct_midrank_distinct_metadata.py` reconstructs exact rational midranks and weighted scores, checks the stored transformed/displayed values, and creates a supplementary metadata patch. It preserves the input and verifies by full-tree comparison that only the allowed `distinct_n` leaves change. Select runs explicitly; the primary duplicate is included when R00 is selected. Non-midrank transformations are skipped. For the frozen V5 input, use a new output filename:

```powershell
python -B 04_ANALYSIS/12_FINALISATION_20260910/correct_midrank_distinct_metadata.py --input 04_ANALYSIS/12_FINALISATION_20260910/local/v5/calculation_output.json --output 04_ANALYSIS/12_FINALISATION_20260910/local/v5/sensitivity_audit_20260912/new_distinct_metadata_supplement.json --expected-input-sha256 ad695c653f873f8da54ec481176bce3899b545a37861b883bde742711829e7ef --run-ids R00 R01 R02 R03 R04 R05 R06 R07 R08 R09 R10 R11 R12 R13 R14 R15
```

The verified current supplement is `local/v5/sensitivity_audit_20260912/current_distinct_metadata_corrections_v2.json`; it corrects 12 metadata leaves, including primary/R00 duplicates and ten other runs. It is not a replacement calculation dataset. Original numerical JSON, scores, profiles, thresholds and every other field remain unchanged. A fresh engine rerun can reproduce the old distinct counts: resolve the underlying arithmetic through a separately validated algorithm successor while preserving the frozen engine. Do not apply this patch to a different raw input hash.

Synthetic controls are in `test_midrank_distinct_metadata.py`, covering rational ties, unequal weights, indicator removal, constant indicators, non-estimable dimensions, input preservation, idempotence and fail-closed display checks. The private sensitivity audit and correction JSON remain local; publish only safe code, synthetic tests and these instructions.
