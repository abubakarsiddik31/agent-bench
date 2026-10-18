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
uv sync
cp .env.example .env
```

## Contribution Guidelines

- Keep benchmark tasks domain-neutral and suitable for public release.
- Prefer shared utilities in `common/` for reusable helpers.
- Keep framework-specific logic inside `frameworks/<framework>/<task>/`.
- Do not add confidential datasets, customer data, or private planning docs.
- Keep evaluation changes reproducible and easy to audit.
- Update public docs when behavior, commands, or scores change.

## Pull Request Checklist

- The change is domain-neutral and appropriate for a public repository.
- Commands in `README.md` still work from the repo root.
- New framework code is isolated to its framework folder.
- Shared helpers are placed in `common/` when appropriate.
- Any new benchmark behavior is reflected in evaluation artifacts or docs.
- The license constraints are respected.

## License

By contributing, you agree that your contributions will be licensed under the
terms in [LICENSE](./LICENSE).
