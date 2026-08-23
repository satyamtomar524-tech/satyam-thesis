# Scripts

Store reusable transformations by language:

- `python/` for data preparation, quality checks, network analysis, and modeling;
- `r/` for statistical workflows where R is selected;
- `sql/` for reproducible queries against structured sources.

Scripts should read from an earlier data stage and write to a later stage. They should not silently overwrite raw inputs.
