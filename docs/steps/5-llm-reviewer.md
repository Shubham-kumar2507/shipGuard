# Step 5: LLM reviewer

`shipguard review --repository OWNER/NAME --pull-request NUMBER` fetches the PR
metadata and per-file patches through GitHub's API. It skips lockfiles and
common generated paths, reads `AGENTS.md` from the base SHA, redacts common
credential patterns, and sends one file at a time to the OpenAI chat-completions
API. The prompt marks patch content as untrusted and provides no model tools.
Pydantic validates the JSON response; only high-confidence findings on newly
added diff lines are posted as inline comments.

Set `GITHUB_TOKEN` and `SHIPGUARD_LLM_API_KEY` in the trusted execution
environment, never in the repository or command line. The reviewer reserves a
conservative per-PR token budget using UTF-8 prompt size plus each response
limit. Its model, confidence threshold, file limit, and token limits can be
configured under `review` in `.shipguard.yml`.

The reviewer is intended to run from a trusted GitHub App service using base
revision policy. Do not expose its secrets to arbitrary pull-request workflow
code.
