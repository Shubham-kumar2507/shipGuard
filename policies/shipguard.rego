package shipguard

import rego.v1

deny contains {
	"rule_id": "POLICY-NO-LATEST",
	"severity": "high",
	"file": dockerfile.file,
	"message": sprintf("Dockerfile uses an unpinned latest image: %s", [image]),
} if {
	some dockerfile in input.dockerfiles
	some image in dockerfile.tags
	is_latest(image)
}

is_latest(image_ref) if {
	image := split(image_ref, "@")[0]
	endswith(image, ":latest")
}

is_latest(image_ref) if {
	not contains(image_ref, "@")
	segments := split(image_ref, "/")
	last_segment := segments[count(segments) - 1]
	not contains(last_segment, ":")
}

deny contains {
	"rule_id": "POLICY-TESTS-CHANGED",
	"severity": "high",
	"file": source_file,
	"message": "Changed source code requires a changed test file",
} if {
	some source_file in input.changed_source_files
	not input.tests_changed
}

deny contains {
	"rule_id": "POLICY-CODEOWNERS",
	"severity": "high",
	"message": "A CODEOWNERS file must exist in the repository",
} if {
	not input.codeowners_exists
}
