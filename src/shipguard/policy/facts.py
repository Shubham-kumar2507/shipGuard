from __future__ import annotations

import re
from pathlib import Path

from shipguard.checkers.process import run_tool

_FROM = re.compile(
    r"^\s*FROM\s+(?:--platform=\S+\s+)?(.+)$",
    re.IGNORECASE,
)
_SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".swift",
    ".ts",
    ".tsx",
}
_SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "dist", "build"}


def _is_test_file(path: str) -> bool:
    parts = {part.lower() for part in Path(path).parts}
    filename = Path(path).name.lower()
    return (
        bool(parts & {"test", "tests", "spec", "specs"})
        or filename.startswith("test_")
        or ".test." in filename
        or ".spec." in filename
    )


def _changed_files(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str | None,
    head_ref: str | None,
) -> list[str]:
    if changed_files:
        return [Path(path).as_posix() for path in changed_files]
    if base_ref is None:
        return []

    comparison = f"{base_ref}...{head_ref or 'HEAD'}"
    result = run_tool("git", ["diff", "--name-only", comparison], cwd=repo_path)
    return [line for line in result.stdout.splitlines() if line]


def _dockerfiles(repo_path: Path) -> list[dict[str, object]]:
    documents: list[dict[str, object]] = []
    for path in repo_path.rglob("Dockerfile*"):
        if not path.is_file() or _SKIP_PARTS.intersection(path.parts):
            continue
        images: list[str] = []
        stage_names: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _FROM.match(line.split("#", maxsplit=1)[0])
            if match:
                parts = match.group(1).split()
                if not parts:
                    continue
                image = parts[0]
                if image.lower() != "scratch":
                    images.append(image)
                if (
                    len(parts) >= 3
                    and parts[-2].lower() == "as"
                ):
                    stage_names.add(parts[-1].lower())
        tags = [image for image in images if image.lower() not in stage_names]
        documents.append(
            {
                "file": path.relative_to(repo_path).as_posix(),
                "tags": tags,
            }
        )
    return documents


def _has_codeowners(repo_path: Path) -> bool:
    return any(
        (repo_path / candidate).is_file()
        for candidate in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
    )


def collect_repo_facts(
    repo_path: Path,
    *,
    changed_files: list[str] | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> dict[str, object]:
    files = _changed_files(repo_path, changed_files or [], base_ref, head_ref)
    source_files = [
        path
        for path in files
        if Path(path).suffix.lower() in _SOURCE_SUFFIXES and not _is_test_file(path)
    ]
    return {
        "dockerfiles": _dockerfiles(repo_path),
        "changed_files": files,
        "changed_source_files": source_files,
        "tests_changed": any(_is_test_file(path) for path in files),
        "codeowners_exists": _has_codeowners(repo_path),
    }
