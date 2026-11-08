# ShipGuard

ShipGuard is a Python CLI and GitHub integration starter for repeatable
pull-request security, supply-chain, policy, and review checks. Python 3.12 or
newer is required.

## Architecture

```text
                         +------------------------------+
                         | GitHub Actions reusable CI   |
                         | lint / tests / OPA / Syft    |
                         +---------------+--------------+
                                         |
Pull request --HMAC--> FastAPI webhook --+--> GitHub App JWT
                    |                    |       |
                    |                    |       v
                    |                    |  installation token
                    |                    |       |
                    |                    v       v
                    |             trusted base + PR head checkout
                    |                    |
                    |                    v
                    |       shipguard check / policy / reviewers
                    |                    |
                    +--------------------+--> GitHub Check Run

Copier template --> FastAPI health service --> pinned non-root container
```

The webhook checks the GitHub HMAC signature before parsing an event. It reads
policy configuration from the base SHA, checks out the PR SHA without running
its code, and invokes the installed CLI with credentials removed from the
checker process environment.

## Install and run

```powershell
python -m pip install -e ".[dev,app]"
ruff check .
pytest -q
shipguard version
shipguard check --repo . --format text
```

External scanner commands (`gitleaks`, `trivy`, and `syft`) must be installed
when their checks are enabled. A typical `.shipguard.yml` enables configured
checks and sets `fail_on`; see [CLI checks](docs/steps/2-cli-checks.md) and
[policy configuration](docs/steps/3-policy-as-code.md).

## Generate a service

```powershell
copier copy --defaults `
  --data service_name=orders-api `
  --data service_description="Orders API" `
  --data maintainer="Platform team" `
  .\templates\fastapi-service .\orders-api
```

The generated project includes its own `AGENTS.md`, health endpoint, unit
tests, CI workflow, pinned dependencies, and digest-pinned multi-stage
Dockerfile. See [the golden-path template guide](docs/steps/1-golden-path.md).

## Pull-request review and evaluation

`shipguard review` validates structured model output and only posts confident
findings on added diff lines. Configure `GITHUB_TOKEN` and
`SHIPGUARD_LLM_API_KEY` in a trusted service environment; do not expose them to
untrusted pull-request workflow code.

The starter evaluation set contains 30 synthetic diff cases, including 10
clean cases. It is not a real-repository benchmark, and no real model precision
or recall numbers have been recorded yet. Score collected predictions with
`shipguard eval`; the prompt-version history is kept in `eval/scores.csv`.
See [evaluation instructions](docs/steps/6-evaluations.md).

## GitHub integration

The main CI workflow calls `.github/workflows/shipguard.yml`. Its
`ShipGuard checks` job is a pull-request Check Run and adds a job summary; it
also uploads the Syft CycloneDX SBOM. A repository administrator must require
that check in GitHub branch-protection settings. See the [reusable workflow
guide](docs/steps/4-github-actions.md) and [GitHub App guide](docs/steps/7-github-app.md).

## Project status and external proof

The CLI, template, policies, reviewer, scorer, webhook, and risk formula are
implemented with local tests. Connecting a real GitHub App, deploying the
webhook, enabling branch protection, onboarding 3–5 adopters, and recording a
demo require external accounts and user participation. Canary/Argo and DORA
infrastructure remain deferred until those integrations have been exercised
in a deployed environment.
