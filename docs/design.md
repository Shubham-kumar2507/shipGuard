# ShipGuard design

ShipGuard gates pull requests with repeatable security, dependency,
supply-chain, policy, and code-review checks. Its users are maintainers who
need one clear pass/fail decision for changes written by people or AI agents.

The product is available as a local Python CLI, a GitHub Action, and a
GitHub App. A pull-request event supplies the base and head revisions. The
runner loads trusted configuration, gathers repository and change facts, and
executes enabled checks. Findings are normalized into one versioned report;
the configured severity threshold determines whether the gate passes or
fails. GitHub integrations publish the report on the pull request and in a
check run.

The initial architecture separates shared models and configuration from
checker registration and CLI commands. Later steps plug in checkers,
reporting, review, hosted integrations, and optional release metrics without
changing the shared report contract.

Non-goals include replacing maintainers' review judgment, guaranteeing that
automated checks find every defect, or allowing untrusted pull-request code to
change the policy used to gate itself.
