# Open Source Checklist

Use this checklist before publishing or tagging a release.

## Public Content

- No confidential planning files are included.
- No private datasets, customer data, or internal notes are included.
- Benchmark tasks are domain-neutral and public-safe.
- Public docs describe the project as a framework benchmark, not a private internal initiative.

## Documentation

- `README.md` is current and root-level commands work.
- `CONTRIBUTING.md` is present and accurate.
- `SECURITY.md` is present.
- `LICENSE` is present and matches the intended usage restrictions.
- Framework README files only reference public implementation details.

## Repository Hygiene

- `.env`, `results/`, `.venv/`, and `.plans/` are ignored.
- No generated caches or local artifacts are committed.
- Example environment variables are in `.env.example`.
- Public-facing file names and folder names are clear.

## Benchmark Integrity

- Current score tables reflect saved evaluation artifacts.
- Tool metrics align with `framework_evaluation.json` files.
- Commands run from the repo root.
- Shared evaluation logic is in `common/` or `evaluation/`, not duplicated per framework.

## Release Readiness

- Dependencies install with `uv sync`.
- At least one documented benchmark run exists for each published framework.
- The current limitations and known gaps are documented honestly.
