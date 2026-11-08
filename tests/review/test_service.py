import json
from types import SimpleNamespace

from shipguard.review.github import PullRequestFile
from shipguard.review.models import ReviewSettings
from shipguard.review.service import PullRequestReviewer, added_lines


class FakeGitHub:
    def __init__(self, files: list[PullRequestFile]) -> None:
        self.files = files
        self.comments: list[dict[str, object]] = []

    def get_pull_request(self, _owner: str, _repository: str, _number: int):
        return SimpleNamespace(base_sha="base-sha", head_sha="head-sha")

    def get_pull_request_files(self, *_args, **_kwargs):
        return self.files

    def get_base_agents(self, *_args):
        return "Use type hints and test public behavior."

    def post_inline_comment(self, *_args, finding, **_kwargs):
        self.comments.append(finding)


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []
        self.limits: list[int] = []

    def review(self, prompt: str, *, max_tokens: int) -> str:
        self.prompts.append(prompt)
        self.limits.append(max_tokens)
        return self.response


def test_added_lines_tracks_only_added_new_file_lines() -> None:
    patch = (
        "@@ -4,3 +4,4 @@\n"
        " context\n"
        "-old line\n"
        "+new line\n"
        "+second new line\n"
    )

    assert added_lines(patch) == {5, 6}


def test_review_redacts_secrets_skips_low_confidence_and_lockfiles() -> None:
    fake_secret = "AKIA" + "IOSFODNN7EXAMPLE"
    github = FakeGitHub(
        [
            PullRequestFile(
                filename="src/app.py",
                patch=f"@@ -1 +1,2 @@\n+credential = '{fake_secret}'\n+return value\n",
            ),
            PullRequestFile(filename="uv.lock", patch="@@ -1 +1 @@\n+package"),
            PullRequestFile(
                filename="src/generated/client.py",
                patch="@@ -1 +1 @@\n+generated",
            ),
        ]
    )
    llm = FakeLLM(
        json.dumps(
            {
                "findings": [
                    {
                        "file": "src/app.py",
                        "line": 1,
                        "severity": "high",
                        "comment": "Credential is committed.",
                        "confidence": 0.96,
                        "category": "hardcoded-secret",
                    },
                    {
                        "file": "src/app.py",
                        "line": 2,
                        "severity": "low",
                        "comment": "Low confidence suggestion.",
                        "confidence": 0.2,
                        "category": "style",
                    },
                ]
            }
        )
    )

    result = PullRequestReviewer(
        github,
        llm,
        ReviewSettings(min_confidence=0.75),
    ).review("owner", "repo", 7)

    assert fake_secret not in llm.prompts[0]
    assert "untrusted data" in llm.prompts[0]
    assert "Use type hints" in llm.prompts[0]
    assert result.reviewed_files == ["src/app.py"]
    assert result.skipped_files == ["uv.lock", "src/generated/client.py"]
    assert result.posted_comments == 1
    assert github.comments[0]["line"] == 1
    assert github.comments[0]["file"] == "src/app.py"


def test_review_respects_total_token_budget() -> None:
    github = FakeGitHub(
        [
            PullRequestFile(
                filename="src/app.py",
                patch="@@ -1 +1 @@\n+return 1\n",
            )
        ]
    )
    llm = FakeLLM('{"findings":[]}')

    result = PullRequestReviewer(
        github,
        llm,
        ReviewSettings(max_tokens_per_pr=256),
    ).review("owner", "repo", 7)

    assert llm.prompts == []
    assert result.skipped_files == ["src/app.py"]
    assert result.reserved_tokens == 0


def test_review_rejects_non_diff_line_from_model() -> None:
    github = FakeGitHub(
        [
            PullRequestFile(
                filename="src/app.py",
                patch="@@ -1,2 +1,2 @@\n context\n-old\n+new\n",
            )
        ]
    )
    llm = FakeLLM(
        json.dumps(
            {
                "findings": [
                    {
                        "file": "src/app.py",
                        "line": 1,
                        "severity": "high",
                        "comment": "Not on an added line.",
                        "confidence": 0.99,
                        "category": "bug",
                    }
                ]
            }
        )
    )

    try:
        PullRequestReviewer(github, llm, ReviewSettings()).review("owner", "repo", 7)
    except RuntimeError as exc:
        assert "not an added diff line" in str(exc)
    else:
        raise AssertionError("A finding outside the diff should be rejected")
