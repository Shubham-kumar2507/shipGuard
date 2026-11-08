# ShipGuard contributor instructions

## Setup and commands

- Use Python 3.12 or newer.
- Install the project and development dependencies with
  `python -m pip install -e ".[dev,app]"`.
- Run `ruff check .` and `pytest -q` before submitting changes.
- Run the CLI with `shipguard version`.

## Code style

- Use type hints and clear, focused functions.
- Follow Ruff's configured style and the existing package layout under `src/`.
- Keep dependencies in the appropriate `pyproject.toml` extra.

## Tests

- Put tests in `tests/<area>/` with the code area they cover.
- Unit tests must not use the network; mock HTTP and subprocess calls.
- Mark real-tool tests as integration tests and skip them when the tool is
  unavailable.
- Create fake secrets in test code at runtime; never commit secrets.

## What never to touch

- Do not change the frozen shared contract in `src/shipguard/models.py` after
  Step 0, or change the published interfaces between steps.
- Respect the file ownership in the project specification. If a shared file
  appears wrong but is outside your ownership, describe the issue in your
  step notes instead of editing it.
- Never commit secrets, push directly to `main`, or weaken a pull-request gate
  to make a check pass.
