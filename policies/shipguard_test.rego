package shipguard

import rego.v1

test_latest_image_is_denied if {
	some finding in deny with input as {
		"dockerfiles": [{"file": "Dockerfile", "tags": ["python:latest"]}],
		"changed_source_files": [],
		"tests_changed": false,
		"codeowners_exists": true,
	}
	finding.rule_id == "POLICY-NO-LATEST"
}

test_untagged_image_is_denied if {
	some finding in deny with input as {
		"dockerfiles": [{"file": "Dockerfile", "tags": ["python"]}],
		"changed_source_files": [],
		"tests_changed": false,
		"codeowners_exists": true,
	}
	finding.rule_id == "POLICY-NO-LATEST"
}

test_latest_tag_with_digest_is_denied if {
	some finding in deny with input as {
		"dockerfiles": [
			{"file": "Dockerfile", "tags": ["python:latest@sha256:abc"]}
		],
		"changed_source_files": [],
		"tests_changed": false,
		"codeowners_exists": true,
	}
	finding.rule_id == "POLICY-NO-LATEST"
}

test_digest_pinned_untagged_image_is_allowed if {
	count(deny) == 0 with input as {
		"dockerfiles": [
			{"file": "Dockerfile", "tags": ["python@sha256:abc"]}
		],
		"changed_source_files": [],
		"tests_changed": false,
		"codeowners_exists": true,
	}
}

test_source_change_requires_tests if {
	some finding in deny with input as {
		"dockerfiles": [],
		"changed_source_files": ["src/app.py"],
		"tests_changed": false,
		"codeowners_exists": true,
	}
	finding.rule_id == "POLICY-TESTS-CHANGED"
}

test_codeowners_is_required if {
	some finding in deny with input as {
		"dockerfiles": [],
		"changed_source_files": [],
		"tests_changed": false,
		"codeowners_exists": false,
	}
	finding.rule_id == "POLICY-CODEOWNERS"
}
