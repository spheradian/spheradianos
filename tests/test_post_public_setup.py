"""Guards the main-branch ruleset in scripts/post-public-setup.sh against drift.

The ruleset requires status checks by job name. If a job in ci.yml is renamed
or removed without updating the script, every merge to main blocks, and the
ruleset has no bypass actor by design.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "post-public-setup.sh"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GITHUB_ACTIONS_APP_ID = 15368


def ruleset():
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"cat <<'EOF'\n(.*?)\nEOF\n", text, re.S)
    if match is None:
        raise AssertionError("ruleset heredoc not found in post-public-setup.sh")
    return json.loads(match.group(1))


def ci_job_names():
    """Names of ci.yml jobs (a `name:` directly under a two-space job key)."""
    names = []
    lines = CI.read_text(encoding="utf-8").splitlines()
    for previous, line in zip(lines, lines[1:], strict=False):
        if re.fullmatch(r"  [A-Za-z0-9_-]+:", previous):
            match = re.fullmatch(r"    name: (.+)", line)
            if match:
                names.append(match.group(1).strip().strip("\"'"))
    return names


def required_checks():
    for rule in ruleset()["rules"]:
        if rule["type"] == "required_status_checks":
            return rule["parameters"]["required_status_checks"]
    raise AssertionError("ruleset has no required_status_checks rule")


class PostPublicSetupTests(unittest.TestCase):
    def test_required_checks_are_exactly_the_ci_jobs(self) -> None:
        contexts = sorted(check["context"] for check in required_checks())
        self.assertEqual(contexts, sorted(ci_job_names()))

    def test_required_checks_come_from_github_actions(self) -> None:
        for check in required_checks():
            self.assertEqual(check.get("integration_id"), GITHUB_ACTIONS_APP_ID, check["context"])

    def test_main_cannot_be_rewritten_or_deleted(self) -> None:
        rules = ruleset()
        types = {rule["type"] for rule in rules["rules"]}
        self.assertLessEqual({"deletion", "non_fast_forward", "pull_request"}, types)
        self.assertEqual(rules["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(rules["enforcement"], "active")


if __name__ == "__main__":
    unittest.main()
