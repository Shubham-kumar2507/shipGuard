# Step 3: Policy as code

`shipguard facts --repo PATH [--base-ref REF] [--head-ref REF]` emits JSON
containing parsed Dockerfile image references, changed files, changed source
files, whether tests changed, and whether a supported `CODEOWNERS` file exists.
`shipguard check` passes the same facts to OPA when policy is enabled.

The starter rules in `policies/shipguard.rego` deny explicit `:latest` image
tags, source changes without a corresponding changed test file, and repositories
without a `CODEOWNERS` file. `policies/shipguard_test.rego` contains OPA unit
tests; run them with `opa test policies --verbose`.

Configure policy evaluation in `.shipguard.yml`:

```yaml
policy:
  enabled: true
  path: policies
```

Git-based changed-file facts use `--base-ref` and `--head-ref`; without a base
ref, the changed-file list is empty.
