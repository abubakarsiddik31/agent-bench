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

Current examples use:

- `<task-id>` = `intake-triage`
- `<dataset-split>` = `stress_v1`

Each `run_result.json` should follow the current evaluation output contract used by the scripts in `evaluation/`.
Each `framework_snapshot.json` should follow the current framework snapshot structure written during evaluation.
