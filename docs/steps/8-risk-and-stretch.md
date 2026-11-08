# Step 8: Risk score and stretch work

`shipguard risk --repo PATH --base-ref REF` computes a transparent 0–100
weighted score from added/deleted diff lines, files touched, and a coverage
drop. Defaults weight the components 40/30/30 and normalize at 500 diff lines,
20 files, and a 20-point coverage loss. Weights and normalization limits are
configurable under `risk` in `.shipguard.yml`. Each run is appended as JSONL to
`.shipguard-cache/risk.jsonl` by default.

The optional `kind`/Argo Rollouts canary and DORA dashboard require a deployed
application, cluster, metrics store, and adoption evidence. They are
intentionally deferred until the GitHub App and CI integrations are deployed
and validated.
