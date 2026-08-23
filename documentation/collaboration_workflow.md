# GitHub, ChatGPT, and Codex workflow

## Roles

- **GitHub** is the versioned source of truth for safe project files, decisions, code, and reproducible outputs.
- **ChatGPT** supports research planning, explanation, drafting discussion, and source-aware reasoning.
- **Codex** edits workspace files, runs scripts and checks, prepares commits, and synchronizes reviewed changes with GitHub.

## Smooth working cycle

```text
Question or evidence found
        ↓
Record the source and narrow claim
        ↓
Add or update data through a reproducible script
        ↓
Run data-quality and analytical checks
        ↓
Review figures, tables, interpretation, and limitations
        ↓
Update the relevant thesis chapter and analysis log
        ↓
Commit one coherent, reviewed change to GitHub
```

## Commit discipline

A commit should answer one question: what changed and why? Do not mix unrelated data, analysis, and writing changes. Before pushing, inspect the staged file list and confirm that no restricted binary or raw source file is included.

Suggested branch names include `data/source-audit`, `analysis/visibility-scores`, `analysis/network-metrics`, and `thesis/chapter-03-methodology`.

## Evidence rule

Research planning may begin from a hypothesis, but repository claims must end at the strongest verified evidence actually available. Missing public evidence is recorded as an observable evidence gap, not as proof of missing internal BMW information.
