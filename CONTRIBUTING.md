# Contributing

Thanks for contributing to Agent Bench.

## Scope

This project is focused on public, reusable benchmark infrastructure for
evaluating agent frameworks. Contributions should improve one or more of:

- benchmark tasks
- evaluation quality
- framework implementations
- reproducibility
- documentation

## Development Setup

```bash
uv sync --locked
cp .env.example .env
```

## Running the Tests

The suite is hermetic — no API keys, no network calls, no agent runs:

```bash
uv run python -m unittest discover -s tests -t . -v
```

Please run it before opening a pull request. If you change the scoreboard, its
canonical run list, or the README tables, regenerate them:

```bash
uv run python scripts/build_scoreboard.py --write
```

## Contribution Guidelines

- Keep benchmark tasks domain-neutral and suitable for public release.
- Prefer shared utilities in `common/` for reusable helpers.
- Keep framework-specific logic inside `frameworks/<framework>/<task>/`.
- Do not add confidential datasets, customer data, or private planning docs.
- Keep evaluation changes reproducible and easy to audit.
- Never let an agent implementation read `gold-expected.json`; the workspace
  preparation in `common/benchmark_utils.py` is responsible for excluding it.
- Do not hand-edit the scoreboard tables in `README.md`; change
  `evaluation/scoreboard.yml` and regenerate.
- Update public docs when behavior, commands, or scores change.

## Pull Request Checklist

- The change is domain-neutral and appropriate for a public repository.
- Commands in `README.md` still work from the repo root.
- `uv run python -m unittest discover -s tests -t .` passes.
- New framework code is isolated to its framework folder.
- Shared helpers are placed in `common/` when appropriate.
- Any new benchmark behavior is reflected in evaluation artifacts or docs.
- The license constraints are respected.

## License

By contributing, you agree that your contributions will be licensed under the
terms in [LICENSE](./LICENSE).
