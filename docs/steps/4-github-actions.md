# Step 4: GitHub Actions integration

The repository's CI workflow calls `.github/workflows/shipguard.yml` as a
reusable workflow. It runs lint and tests, executes the configured ShipGuard
check, tests the Rego rules with OPA, generates a CycloneDX SBOM with Syft, and
uploads that SBOM as a workflow artifact. The workflow's `ShipGuard checks` job
is also the pull-request Check Run; the human-readable report is added to the
job summary.

The repository's `.shipguard.yml` enables the local pinning checker and
explicitly disables scanner checks that require separately installed binaries.
Configure secrets, vulnerability, SBOM, and policy checkers for your own runner
once those tools and project policies are available.

Branch protection cannot be changed by a repository file. In GitHub settings,
require the `ShipGuard checks` status check before merging. A repository admin
must enable that rule.
