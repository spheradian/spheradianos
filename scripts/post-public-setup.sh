#!/bin/sh
# Apply the GitHub protections that ADR-010 §5 defers until the repository
# is public: a ruleset on main, secret scanning with push protection,
# Dependabot alerts, private vulnerability reporting, and approval for
# fork PR workflow runs. Run it once, by the approver, right after the
# visibility switch. It is idempotent: an existing "main" ruleset is updated.
#
# Usage: scripts/post-public-setup.sh [owner/repo]
set -eu

repo=${1:-spheradian/spheradianos}
case "$repo" in
*[!A-Za-z0-9._/-]* | */*/* | /* | */ | *..*)
	echo "error: '$repo' is not an owner/repo name." >&2
	exit 1
	;;
*/*) ;;
*)
	echo "error: '$repo' is not an owner/repo name." >&2
	exit 1
	;;
esac

visibility=$(gh repo view "$repo" --json visibility --jq .visibility)
if [ "$visibility" != "PUBLIC" ]; then
	echo "error: $repo is $visibility; switch it to public first (ADR-010 §4)." >&2
	exit 1
fi

# Required checks are the jobs of ci.yml, which run on every PR to main.
# image-boot.yml is path-filtered and the Claude review skips fork PRs, so
# requiring them would block PRs on which they never run.
# There is no bypass actor (ENGINEERING-PLAN §2.3: no bypass for the
# maintainer). If a required job is renamed or removed, merges block until
# this list is updated: an org owner can always edit or disable the ruleset
# under Settings -> Rules -> Rulesets, then rerun this script.
# integration_id 15368 is the GitHub Actions app: a status with the same name
# posted by any other app or token does not satisfy the check.
ruleset=$(
	cat <<'EOF'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "bypass_actors": [],
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["squash"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          { "context": "Static & Config Checks", "integration_id": 15368 },
          { "context": "Workflow Security (actionlint & zizmor)", "integration_id": 15368 },
          { "context": "SAST (Opengrep)", "integration_id": 15368 },
          { "context": "Secret Scan (gitleaks)", "integration_id": 15368 }
        ]
      }
    }
  ]
}
EOF
)

existing=$(gh api "repos/$repo/rulesets" --jq '.[] | select(.name == "main") | .id' | head -n 1)
if [ -n "$existing" ]; then
	printf '%s' "$ruleset" | gh api -X PUT "repos/$repo/rulesets/$existing" --input - >/dev/null
	echo "updated ruleset main ($existing)"
else
	printf '%s' "$ruleset" | gh api -X POST "repos/$repo/rulesets" --input - >/dev/null
	echo "created ruleset main"
fi

gh api -X PATCH "repos/$repo" --input - >/dev/null <<'EOF'
{
  "delete_branch_on_merge": true,
  "allow_merge_commit": false,
  "allow_rebase_merge": false,
  "allow_squash_merge": true,
  "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" }
  }
}
EOF
echo "enabled secret scanning and push protection; squash-only merges"

gh api -X PUT "repos/$repo/vulnerability-alerts" >/dev/null
echo "enabled Dependabot alerts"

gh api -X PUT "repos/$repo/private-vulnerability-reporting" >/dev/null
echo "enabled private vulnerability reporting"

printf '{"approval_policy":"all_external_contributors"}' |
	gh api -X PUT "repos/$repo/actions/permissions/fork-pr-contributor-approval" --input - >/dev/null
echo "fork PR workflows now need approval for all external contributors"
