# Kiro run: task 24 (count tests that compare the README with the repository)

## Instructions given

```text
TASK 24: COUNT TESTS THAT COMPARE, NOT PIN. Add task 24 to tasks.md (Requirement 6's README kept true; no new requirement).

Every Kiro run adds one session record and usually one task, and several README tests pin literal counts ("26 runs", "exactly 26 numbered files", "tasks 1 to 22", the task count in tasks.md), so each new run breaks them and needs another run to fix them. Change those tests (tests/test_carbon_round6.py, test_carbon_round7.py and any other test that pins the number of session records, tasks or requirements) so they READ the README's numbers and COMPARE them with the repository instead: the README's "(N runs:" equals the number of numbered files in docs/kiro-sessions/; the README's "tasks 1 to N" equals the number of tasks in tasks.md; the README's "(N requirements)" equals the number of "### Requirement" headings. Keep the assertions that check specific sentences and files exist. Do NOT change the README or any non-test file except tasks.md: after you finish, the README will be brought in line (it will say tasks 1 to 24 and the runs including this one), and your tests must then pass with no further edit. Prove it: in a scratch copy, set the README's numbers to the correct counts for a repository with one more session record and one more task, and show the tests pass there and fail when the README's number is wrong.

Run .venv\Scripts\python.exe -m pytest -q and report the count. It is expected that the README's current counts may not match until it is brought in line; report which assertions fail now and why.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=9
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Write File
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Now add task 24 to tasks.md, and fix task 23's now-stale "26 runs" wording only by adding task 24 (leave 23 as history).
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
Task 24 is added to `tasks.md`, and the count tests now compare instead of pin. The full run is 3 failed, 500 passed, 5 deselected. The 3 failures are expected until the README is brought in line.
**Changes**
- **New helper:** `tests/readme_counts.py` reads three numbers from the README: "(N runs:", "tasks 1 to N" (lowercase) and "(N requirements)". It compares each with the repository:
  - the numbered files in `docs/kiro-sessions/`;
  - the `- [x] N.` tasks in `tasks.md`;
  - the `### Requirement` headings.
  A phrase missing or repeated in the README fails the check. The capital-T "Tasks 1 to 9" in the README is not mistaken for the task count.
- **Tests changed:** `test_carbon_round6.py`, `test_carbon_round7.py` and `test_carbon_app.py` now call `assert_readme_counts_match`. I dropped the literals `== 26`, `== 23`, `== 19`, "tasks 1 to 22" and "(19 requirements)". The checks that specific sentences and files exist stay. That includes the fourth-run `23_` sentence, the `23_…` file, "seventeen times" and Requirement 19.
- **No other file changed:** The README and all other non-test files are untouched.
**Failing now**
The three failures are `test_readme_is_in_line_with_task_11`, `test_the_spec_has_requirement_19_task_21_and_the_readme_counts_are_true` and `test_the_readme_no_longer_names_the_gap_and_the_counts_are_true`. All three fail the same way: the README says `{runs: 26, tasks: 22, requirements: 19}` and the repository holds `{runs: 26, tasks: 24, requirements: 19}`. The README's "tasks 1 to 22" is stale, because `tasks.md` now has tasks 23 and 24.
**Scratch-copy proof**
I made a copy of the repository in the temp folder, added one session file, and set the README to "(27 runs:" and "tasks 1 to 24". The four README-count tests (the three above plus `test_readme_is_in_line_with_task_10`) then passed: 4 passed. With any one number wrong, they failed with the message "README says … but the repository holds …":
- a runs count of 28 failed;
- a tasks count of 23 failed;
- a requirements count of 20 failed.
I deleted the scratch copy afterwards.
When the README says tasks 1 to 24 and counts the session record for this run, the tests should pass with no further edit. I only ran the scratch check against the number of files I had added, so check that the README's run count matches the files once this run's record exists.
```
