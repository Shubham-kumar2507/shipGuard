# Step 2: CLI and CI checks

`shipguard check` runs enabled checkers and returns the shared `Report` model.
By default, the built-in checks run; `.shipguard.yml` can disable checks or set
the blocking severity threshold. The command prints a readable report and
supports `--format json`. Checker errors and findings at or above `fail_on`
produce a non-zero exit status.

The built-in checks invoke `gitleaks`, `trivy`, and `syft` for secrets,
vulnerabilities/misconfigurations, and CycloneDX SBOM generation. The custom
pinning checker inspects Python dependency declarations and GitHub workflow
`uses:` references. Install the external scanner executables on `PATH` or
disable a scanner under `checkers` in `.shipguard.yml`.

Example:

```yaml
version: 1
fail_on: high
checkers:
  vulnerabilities:
    enabled: false
  sbom:
    enabled: true
    output: artifacts/shipguard-sbom.cdx.json
```

```powershell
shipguard check --repo . --format json
```

Unit tests mock scanner subprocesses. The fake AWS-style credential used by the
CLI test is assembled at runtime and never committed as a literal secret.
