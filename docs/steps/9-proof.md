# Step 9: Proof it works

Local verification currently covers the generated template, mocked scanner and
GitHub API paths, webhook signature and App-token flow, Rego tests, and the
evaluation scorer. The starter eval dataset is synthetic; it does not support
claims about model performance on real pull requests.

To complete external proof:

1. Onboard 3–5 consenting repositories or maintainers and record their
   confusion points and resulting changes.
2. Record a short demo showing a bad PR blocked and a clean PR passing.
3. Configure GitHub branch protection to require `ShipGuard checks`.
4. Run the LLM evaluator against labeled real-repository cases and record
   prompt-version precision, recall, and false positives in `eval/scores.csv`.

These steps require a deployed GitHub App, account permissions, test
repositories, and user participation; they cannot be completed by editing this
local checkout alone.
