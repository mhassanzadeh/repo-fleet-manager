package rfm

# The CLI evaluates data.rfm.deny with the normalized RFM policy input.
default deny := []

public_repositories := [repo |
  some repo in input.repositories
  repo.visibility == "public"
]

deny contains {
  "rule_id": "rego-no-public-repositories",
  "severity": "error",
  "subject": repo.repo,
  "repository": repo.repo,
  "message": "public repositories are not allowed"
} if {
  some repo in public_repositories
}
