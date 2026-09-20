# Homework Checker: local checks and assistant handoff

The checker reads a local submission snapshot, archives originals **before execution**, runs `.py` / `.ipynb` checks, and writes local reports. It does **not** authenticate with Google, upload files, clear an inbox, or modify a spreadsheet. The assistant/operator handles Drive intake, verified archival, identity reconciliation and score updates separately.

Run student code in an isolated environment without Google credentials. Only synthetic fixtures are used by the test suite. Keep a protected original Drive archive outside the execution environment.

## Run

Clone the repository so `home-work-checker.ipynb`, `submission_review.py` and `checker_handoff.py` are together. Install `nbformat`, `nbclient`, `ipykernel` and the assignment's dependencies in the isolated environment. Open the checker notebook from the repository directory, configure the first cell and run it.

- `TARGET_DIR`: local snapshot (`data` by default), with uniquely named files.
- `GLOB_PATTERNS`: `*.py,*.ipynb`. Discovery is nonrecursive.
- `DEFAULT_TIMEOUT`: execution timeout; notebook timeout applies per cell.
- `REPORTS_ROOT`: private archive/reports directory, **one directory per course and semester**.
- `HW_TYPE`: assignment family label for historical CSVs.
- `STOP_ON_FAIL=False`: one failure does not stop the batch.
- `REVIEW_TEMPLATES`: assignment ID to trusted original template path.
- `SUBMISSION_RECEIPTS`: instructor/assistant-controlled metadata, keyed by relative inbox filename. Do not derive trusted identity, dates or policies from student output.
- `ASSIGNMENT_POLICIES`: explicit approved grading policy per assignment.
- `REVIEW_IDENTITIES`: confirmed historical identity overrides, keyed by absolute archive path.

## Result contract

The submission prints final JSON containing `name`, `group`, `assignment`, `score`. Scores must be finite numbers, not booleans. A successful process without a numeric score is marked `FAILED`. Execution success is not full marks and is not proof of an untampered self-check. The assistant must inspect grading logic against the instructor template before accepting self-reported points.

## Trusted receipts and penalties

Example configuration (illustrative, not a course policy):

```python
ASSIGNMENT_POLICIES = {
    'EXAMPLE': {'score_kind': 'raw', 'max_score': 100, 'penalty_mode': 'none'},
}
SUBMISSION_RECEIPTS = {
    'drive-id__submission.ipynb': {
        'sha256': '<verified snapshot SHA-256>',
        'student_id': '<confirmed roster identity>',
        'expected_name': 'Иван Иванов',
        'expected_group': '11-601',
        'assignment': 'EXAMPLE',
        'submitted_at': '2026-09-20T10:00:00+03:00',
        'drive_file_id': '<original file ID>',
        'drive_revision': '<snapshot version>',
    }
}
```

`penalty_mode='none'` must be explicitly approved. Optional `linear` preserves the original harness formula: `fraction = min(1, max(0, submitted_at-due)/(due-start))`, `final = raw*(1-fraction)`. It requires timezone-aware ISO `start`, `due` and a trusted receipt timestamp. Other formulas remain manual review until implemented and approved. The legacy student-date-based penalty is no longer applied by the runner.

Unknown policy, non-raw score, invalid scale, missing/mismatched receipt, unknown identity or unresolved review signals result in `NEEDS_REVIEW`. The checker never silently invents a deadline or applies a second penalty. `grades.csv` preserves extracted scores; only `assistant_handoff.json` contains independently calculated proposed final scores.

## Similarity review

The runner reads archived source from current and earlier runs of the same assignment, without executing historical files. It compares added comments, docstrings and Markdown explanations, excluding exact text from supplied instructor templates. Notebook outputs do not count. A single shared long explanation (at least 80 characters and 10 words), or two substantive shared snippets (each at least 40 characters and 6 words), generates a review signal. These are transparent heuristics, not a plagiarism verdict.

The report includes file pairs, student claims, evidence text and cell/line locations. It flags retained template names, embedded author-name discrepancies, and conflicts with trusted receipt identity. Exact template subtraction does not recognise every paraphrased instruction, so the instructor must review evidence. Without the original template, shared prose is labelled `TEMPLATE_REQUIRED`.

Code AST similarity is context only: short identical solutions **never trigger a case by themselves**. Confirmed same-student revisions are excluded from pairwise similarity accusations. Cyrillic/Latin normalisation produces candidate matches, not automatic identity merges. Unknown same-name attempts require identity review; use roster IDs and confirmed aliases to resolve homonyms and transliteration variants.

## Outputs

`reports/<run>/` contains:

- `assistant_handoff.json`: claims, trusted receipt, hash, execution status, independent penalty calculation, holds and review signals.
- `similarity_review.json` and `.md`: private evidence for teacher decisions.
- `review_identities.json`: confirmed identity metadata used in this run.
- `summary.csv/json`, `grades.csv/json`, and execution logs.

`reports/submissions/<run>/` keeps original source bytes. Historical `*-all_runs.csv` files are append-only attempt logs, **not** a spreadsheet replacement and not the best-score table. Do not publish archives or private evidence to the public repository.

The assistant receives the report, reads the existing Google Sheet, resolves identities against the roster and confirmed aliases, then updates only a strictly better approved final score for the same course/semester/assignment/student. Failed or pending attempts never erase an existing mark. Keep all attempts and decisions until semester end. The assistant verifies the written cells by reading them back.

No current student work is processed merely by installing this update. The operator chooses the batch explicitly.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests cover execution failures, invalid scores, penalty boundaries/timezones/caps, missing trusted metadata, boilerplate exclusion, retained names, transliteration candidates, same-student revisions, historical comparisons and short-code false positives. They do not access Google or execute real submissions.
