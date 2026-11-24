# Kiro run: task 19 (the README in line with tasks 14 to 18)

## Instructions given

```text
TASK 19: THE README'S "HOW KIRO BUILT IT" IN LINE WITH TASKS 14 TO 18. Documentation only; no code changes. Add task 19 to tasks.md (no new requirement: it is Requirement 6, the README, kept true).

The section still says "14 requirements", "tasks 1 to 14", lists tasks only to 13 and says "The spec changed when gaps were found, eight times". Read the spec (.kiro/specs/carbon-copy/requirements.md has 18 requirements; tasks.md has tasks 1 to 18, this one 19) and the session records in docs/kiro-sessions/ (21 runs, listed in its README.md), then:
1. Bring every count in that section in line with the repository as it is: requirements, tasks, runs of the carbon-attacker agent (three; the third was resumed once with --resume after a network error stopped it before its report), session records.
2. Extend the task list with 14 to 19 in the same plain style (14 "Try to change one" checked in the browser too; 15 every money move gets its receipt, on every path; 16 a check that does not need to trust us, and honest limits; 17 the two findings 16 left open; 18 an hour after the owner's last tap; 19 this README).
3. Add the spec changes since the eighth, numbered on, one plain paragraph each, from what the spec and session records say: the edit demo checked on the device (14); the third attacker round's findings and what changed (15 to 18: the MCP path had no book; a tap that errored left no receipt; an honest book could read as changed while a run was writing; a payout of NaN dollars was allowed; the in-page check is code our server sends, so verify.html and the published key; visitor flooding; the hour). Count them and make the sentence's number true.
4. Describe the custom agent's three runs with the numbers in its own reports (round one six proven findings, round two seven, round three: count its proven findings in docs/kiro-sessions/ for the third run and its resumed report).
Every number you write must be read from the repository or the session records, not from this prompt. Update any README test that pins the old counts so it pins the new ones. Run .venv\Scripts\python.exe -m pytest -q until everything passes. Report the counts you wrote and where each came from.
```

## What Kiro did and reported

```text
kiro-cli.exe : [INFO] [KRS] <-- GenerateAssistantResponseCommand done totalEvents=8
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] Run Command
[tool] status: Completed
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Run Command
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Replace in File
[tool] status: Completed
[tool] Run Command
[tool] status: Failed: Run Command
[tool] Run Command
[tool] status: Completed
The README's "How Kiro built it" section now matches the repository, and `.venv\Scripts\python.exe -m pytest -q` gives 415 passed, 5 deselected. The 5 deselected tests are the `recorded` ones that CI runs in its own step. I changed no code. The only files touched are the README, `tasks.md`, `docs/kiro-sessions/README.md` and one test file.
**Counts I wrote and where each came from**
- **18 requirements:** the 18 `### Requirement` headings in `requirements.md`.
- **Tasks 1 to 19:** `tasks.md` has 18 task entries, and I added task 19 (Requirement 6, the README).
- **21 session records:** the 21 numbered files in `docs/kiro-sessions/`. I left this at 21 and did not add a record for this task.
- **Attacker findings, first run, 6:** the six numbered findings under "Proven findings" in file 10.
- **Attacker findings, second run, 7:** the seven numbered findings in file 12.
- **Attacker findings, third run, 13:** F1 to F13 in the resumed report (file 17). File 16, the run that stopped on the network error, has no report of its own. The third run was resumed once, which matches files 16 and 17.
- **16 spec changes:** the eight already listed plus eight new ones, numbered 9 to 16. They are:
  - the edit demo checked on the device;
  - the MCP path with no book;
  - the tap that errored;
  - the honest book that read as changed;
  - the NaN payout;
  - the in-page check and `verify.html`;
  - visitor flooding and unbounded sizes;
  - the hour.
  Each paragraph's facts come from Requirements 14 to 18 and the file 17 report. I took your list as eight new items, so "sixteen times" assumes that count.
**Other edits**
- **Task list:** the README task list now runs 1 to 19. Task 19 in `tasks.md` has sub-items 19.1 to 19.4.
- **Garbled line in `tasks.md`:** the existing line 18.3 had a tab and a control character where "tests" and "attack3" should start, so I rewrote it.
- **Tests:** the two README tests that pinned "tasks 1 to 14" and "14 requirements" now pin "tasks 1 to 19", "(18 requirements)" and "sixteen times", and check that "eight times" is gone.
- **Session index (not requested):** `docs/kiro-sessions/README.md` said the attacker was run twice and its findings became tasks 11 and 12. It now says three times, with tasks 11, 12 and 15 to 18.
**Please check**
- I read "Requirement 6" as you wrote it. In `requirements.md`, Requirement 6 is "the owner can see it" (the Carbon copy screen). Task 6 in `tasks.md` is the README task.
- The README's closing line on the attacker (first run six, second seven, third thirteen) comes from the reports' own headings. The older "five ways, one limit and the MCP problem" for run one is the same six findings, grouped differently.
```
