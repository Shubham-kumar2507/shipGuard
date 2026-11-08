from shipguard.models import Finding, Report, Severity


def test_blocking_includes_findings_at_or_above_threshold() -> None:
    report = Report(
        findings=[
            Finding(rule_id="a", source="test", severity=Severity.MEDIUM, message="m"),
            Finding(rule_id="b", source="test", severity=Severity.HIGH, message="h"),
            Finding(
                rule_id="c",
                source="test",
                severity=Severity.CRITICAL,
                message="c",
            ),
        ]
    )

    assert [finding.rule_id for finding in report.blocking(Severity.HIGH)] == ["b", "c"]
    assert report.blocking(Severity.INFO) == report.findings


def test_merge_returns_new_report_with_combined_contents() -> None:
    first = Report(
        head_sha="base",
        findings=[
            Finding(rule_id="a", source="test", severity=Severity.LOW, message="a")
        ],
        errors=["first error"],
    )
    second = Report(
        head_sha="head",
        findings=[
            Finding(rule_id="b", source="test", severity=Severity.HIGH, message="b")
        ],
        errors=["second error"],
    )

    merged = first.merge(second)

    assert merged is not first
    assert merged.head_sha == "head"
    assert [finding.rule_id for finding in merged.findings] == ["a", "b"]
    assert merged.errors == ["first error", "second error"]
    assert first.head_sha == "base"


def test_merge_keeps_existing_head_sha_when_other_is_missing() -> None:
    first = Report(head_sha="existing")

    assert first.merge(Report()).head_sha == "existing"
