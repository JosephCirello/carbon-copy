"""The README's three counts, read from the README and compared with the repository (task 24).

A new Kiro run adds a session record and usually a task, so a test must not pin "26 runs" or "tasks 1 to 22":
it reads the number the README states and checks it against what the repository holds.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / ".kiro" / "specs" / "carbon-copy"


def readme_number(readme: str, pattern: str) -> int:
    """The one number the README states with ``pattern`` (one capture group); a missing or repeated phrase fails."""
    found = re.findall(pattern, readme)
    assert len(found) == 1, f"the README should state this exactly once ({pattern!r}); found {len(found)}"
    return int(found[0])


def readme_counts(readme: str) -> dict[str, int]:
    return {
        "runs": readme_number(readme, r"\((\d+)\s+runs:"),
        "tasks": readme_number(readme, r"tasks\s+1\s+to\s+(\d+)\b"),
        "requirements": readme_number(readme, r"\((\d+)\s+requirements\)"),
    }


def repo_counts(root: Path = ROOT) -> dict[str, int]:
    spec = root / ".kiro" / "specs" / "carbon-copy"
    sessions = root / "docs" / "kiro-sessions"
    tasks = (spec / "tasks.md").read_text(encoding="utf-8")
    reqs = (spec / "requirements.md").read_text(encoding="utf-8")
    return {
        "runs": len([p for p in sessions.glob("*.md") if re.match(r"\d\d_", p.name)]),
        "tasks": len(re.findall(r"^- \[[x ]\] \d+\. ", tasks, re.M)),
        "requirements": len(re.findall(r"^### Requirement \d+", reqs, re.M)),
    }


def assert_readme_counts_match(readme: str, root: Path = ROOT) -> None:
    said, held = readme_counts(readme), repo_counts(root)
    assert said == held, f"the README says {said} but the repository holds {held}"

NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen "
    "nineteen twenty twenty-one twenty-two twenty-three twenty-four twenty-five".split())}


def assert_spec_changes_match(readme: str) -> None:
    """The README says "The spec changed when gaps were found, <number word> times:" and then lists them: the word must equal
    the number of items in the list (task 25: a new spec change must not need a test edited)."""
    found = re.findall(r"The spec changed when gaps were found, ([a-z-]+) times:", readme)
    assert len(found) == 1, "the README should say how many times the spec changed exactly once"
    said = NUMBER_WORDS[found[0]]
    tail = readme.split(found[0] + " times:", 1)[1].split("## Limits we know about", 1)[0]
    listed = len(re.findall(r"^\d+\. \*\*", tail, re.M))
    assert said == listed, f"the README says the spec changed {said} times but lists {listed}"
