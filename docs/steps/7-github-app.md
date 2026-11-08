# Step 7: GitHub App webhook receiver

`shipguard webhook` starts the FastAPI receiver. It checks the raw-body
`X-Hub-Signature-256` HMAC before parsing events, accepts supported
`pull_request` actions, creates a short-lived GitHub App JWT, exchanges it for
an installation token, and reports a ShipGuard Check Run.

The runner fetches the PR head and base SHA without executing PR code. It reads
`.shipguard.yml` and Rego policies from a separate base-SHA worktree, then runs
the installed ShipGuard CLI against the head checkout with credentials removed
from the checker process environment. The GitHub token is supplied only to Git
for checkout and to the GitHub App API client.

Required environment variables:

- `SHIPGUARD_WEBHOOK_SECRET`
- `SHIPGUARD_APP_ID`
- `SHIPGUARD_APP_PRIVATE_KEY` (PEM content; newlines may be escaped)

Grant the App read access to repository contents and pull requests, plus write
access to checks and pull requests if inline comments are enabled. For local
development, expose `/webhook` through smee.io or ngrok and configure the same
secret in the App. A production deployment also needs TLS, persistent job
processing, and deployment-specific secret management; those external services
are not configured in this repository.

Build and run the non-root container with:

```powershell
docker build --tag shipguard-app .
docker run --rm -p 8000:8000 `
  -e SHIPGUARD_WEBHOOK_SECRET `
  -e SHIPGUARD_APP_ID `
  -e SHIPGUARD_APP_PRIVATE_KEY `
  shipguard-app
```
