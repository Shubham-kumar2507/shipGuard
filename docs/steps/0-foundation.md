# Step 0: Foundation

## Built

- Added the Python 3.12 package metadata, CLI entry point, runtime dependencies,
  and `dev` and `app` extras.
- Added the shared report and checker models, YAML configuration loader,
  checker registry, and auto-discovered Typer CLI.
- Added repository guidance, design notes, CI, and core unit tests.

## Run

```powershell
python -m pip install -e ".[dev,app]"
ruff check .
pytest -q
shipguard version
```

## Deviations and known gaps

- No Step 0 acceptance items were intentionally omitted.
- Validation ran on Python 3.13.6; Python 3.12 is not installed in the current
  environment. CI is configured to run on Python 3.12.
- Steps 1–9 remain outside this branch's ownership and have not been built or
  verified here.
