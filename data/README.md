# Data workflow

Data moves forward through four controlled stages. A file should never be edited in place across stages.

| Stage | Meaning | Git policy |
| --- | --- | --- |
| `raw/` | Original files exactly as received or downloaded | Local-only and ignored |
| `external/` | Public evidence, documented extracts, or manifests | Commit only when safe and permitted |
| `cleaned/` | Script-generated normalized records | Commit when reproducible and non-restricted |
| `final/` | Validated tables used in analysis | Commit when provenance and QA are complete |

Every promoted dataset must be traceable to source records and to the script or notebook that produced it. Never overwrite the source file to correct names or categories.
