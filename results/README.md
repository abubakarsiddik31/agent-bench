# Results

This directory stores benchmark outputs.

Recommended layout:

```text
results/
├── <framework>/
│   └── <task-id>/
│       └── <dataset-split>/
│           └── <run-id>/
│               ├── triage_decision.json
│               ├── candidate_match_table.json
│               ├── gap_analysis.md
│               ├── next_actions.md
│               ├── run_result.json
│               └── framework_snapshot.json
```

For the starter benchmark, use:

- `<task-id>` = `intake-triage`
- `<dataset-split>` = `starter_v1`

Each `run_result.json` should follow the per-run output contract from the PRD.
Each `framework_snapshot.json` should follow the per-task framework snapshot contract from the PRD.
