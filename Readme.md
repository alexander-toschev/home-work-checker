# Homework Checker (JupyterLab harness)

This repository contains a **JupyterLab-based homework checker** that:
- discovers student submissions in a folder,
- executes each submission with a timeout,
- extracts the **final structured result** from the last output line/cell,
- applies an optional late-penalty (if enabled),
- produces **per-run reports** (CSV/JSON + logs),
- appends results into **global “all runs” gradebooks**.

> ⚠️ Security: this tool executes untrusted student code. Run it in an isolated environment (VM/container), not on a production machine.

---

## Contents
- [Quick start](#quick-start)
- [Project layout](#project-layout)
- [Input formats (submissions)](#input-formats-submissions)
- [Required output contract (what a student must print)](#required-output-contract-what-a-student-must-print)
- [How grading works](#how-grading-works)
- [Outputs (reports and gradebooks)](#outputs-reports-and-gradebooks)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Quick start

### 1) Put submissions into `data/`
By default the checker searches in:

- `data/*.py`
- `data/*.ipynb`

> Note: discovery is **non-recursive** (`Path.glob`). If you have subfolders, either move files to `data/` or extend the code to use `rglob`.

### 2) Run the checker in JupyterLab
1. Open JupyterLab
2. Open `hw_checker.ipynb`
3. Run all cells (or the last “Run checks” cell)

The run produces a timestamped folder under `reports/` and updates the aggregate CSVs in `reports/`.

---

## Project layout

Typical layout:

```
.
├─ hw_checker.ipynb          # main checker notebook (harness)
├─ data/                     # submissions (input)
└─ reports/                  # results (output)
   ├─ <RUN_TIMESTAMP>/
   │  ├─ summary.csv
   │  ├─ grades.csv
   │  ├─ summary.json
   │  ├─ grades.json
   │  └─ logs/
   │     ├─ <file>.stdout.txt
   │     ├─ <file>.stderr.txt
   │     └─ <file>.last.txt
   ├─ submissions/
   │  └─ <RUN_TIMESTAMP>/... # copies of checked submissions
   ├─ <HW_TYPE>-summary_all_runs.csv
   └─ <HW_TYPE>-grades_all_runs.csv
```

---

## Input formats (submissions)

The checker supports:

- **Python scripts**: `*.py`
- **Jupyter notebooks**: `*.ipynb`

Execution details:
- `*.py` files are executed via `subprocess.run([python, file.py])`
- `*.ipynb` files are executed via **nbclient** (preferred). If nbclient is unavailable, it falls back to `jupyter nbconvert --execute`.

Working directory:
- Each submission runs with `cwd = submission.parent`
- Notebooks run with `resources={'metadata': {'path': notebook.parent}}`

Environment variables passed to submissions:
- `CHECK_MODE=1` (for `*.py` runs) — you can use it in student code to switch to a faster “grading mode”.
- `HARN_MTIME_EPOCH=<file_mtime>` — the file modification timestamp (seconds since epoch). Can be used for deadline logic.

---

## Required output contract (what a student must print)

The checker extracts the **last non-empty output** and tries to parse it as JSON.
At minimum, ensure the last output contains:

- `name` (string)
- `group` (string)
- `assignment` (string)
- `score` (number)

### Recommended output (JSON on the last line / last cell output)

Python script example:

```python
import json
result = {
  "name": "Alice Example",
  "group": "208",
  "assignment": "HW-03",
  "score": 9.5
}
print(json.dumps(result, ensure_ascii=False))
```

Notebook example: make your **final cell** print JSON and ensure **nothing prints after it**.

### Fallback formats (less reliable)
If JSON parsing fails, the checker tries these patterns:

- `name: ...`
- `group: ...`
- `assignment: ...`
- `score: 9.5`

or (last two lines):
- line `N-1`: name
- line `N`: score

---

## How grading works

### Statuses
Each submission ends in one of:

- `PASSED` — exit code 0
- `FAILED` — non-zero exit code
- `TIMEOUT` — exceeded the per-file timeout
- `ERROR` — checker-side exception
- `SKIPPED` — unsupported extension (should not happen with default patterns)

### Late penalty (optional / advanced)
The harness contains a penalty helper:

```python
penalty_fraction(start_dt, due_dt, now_dt)
```

and then (inside `run_checks`) applies:

```
final_score = score * (1 - penalty_fraction)
```

**Important note:** in the current implementation, the default payload extractor only keeps
`name/group/assignment/score`. If you want the harness to apply a time-based penalty using
`start_date` / `due_date`, you must extend the payload extraction and grade CSV fields.

A simple, robust alternative is: **let the student notebook compute the penalty itself**
and output the already penalized `score`.

---

## Outputs (reports and gradebooks)

For every run, the checker writes **per-run** files in `reports/<RUN_TIMESTAMP>/`:

### `summary.csv` columns
- `timestamp` — run timestamp
- `file` — relative file name
- `status`
- `exit_code`
- `duration_sec`
- `mtime_epoch`
- `mtime_iso`
- `report_dir`

### `grades.csv` columns
- `timestamp`
- `file`
- `name`
- `group`
- `assignment`
- `score`
- `status`
- `mtime_iso`
- `report_dir`

### Logs (if enabled)
- `reports/<ts>/logs/<file>.stdout.txt`
- `reports/<ts>/logs/<file>.stderr.txt`
- `reports/<ts>/logs/<file>.last.txt` (the extracted last output)

### Aggregators (“all runs” gradebooks)
In `reports/` root, the checker appends rows into:

- `<HW_TYPE>-summary_all_runs.csv`
- `<HW_TYPE>-grades_all_runs.csv`

This makes it easy to track multiple grading sessions over time without merging CSVs manually.

---

## Configuration

At the top of `hw_checker.ipynb` you can change:

- `TARGET_DIR` — folder with submissions (default: `data`)
- `GLOB_PATTERNS` — comma-separated patterns (default: `*.py,*.ipynb`)
- `DEFAULT_TIMEOUT` — timeout per file, in seconds
- `STOP_ON_FAIL` — stop after first failing submission
- `REPORTS_ROOT` — output root folder (default: `reports`)
- `SAVE_LOGS` — write stdout/stderr/last-output logs
- `VERBOSITY` — 0..2
- `HW_TYPE` — prefix for aggregate CSV names (e.g., `tools`)

---

## Troubleshooting

### Notebooks don’t execute (`NBCLIENT_AVAILABLE = False`)
Install dependencies:

```bash
pip install nbclient nbformat jupyter
```

### “No grades extracted” (name/group/score are empty)
- Check `reports/<ts>/logs/<file>.last.txt`
- Ensure the **last output** is valid JSON and includes required keys.

### Timeouts
- Increase `DEFAULT_TIMEOUT`
- Encourage students to use `CHECK_MODE` to skip heavy training and only run lightweight checks.

### Windows / WSL notes
- If running under WSL, make sure `jupyter` is available in the same environment as the kernel.
- If you use browser-based OAuth flows for exports (e.g., Google Sheets), prefer “local server” style auth rather than console-only flows.

---

## License
Add your license here (MIT/Apache-2.0/Proprietary/etc.).
