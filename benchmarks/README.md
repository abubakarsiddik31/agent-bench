# Benchmarks

This directory contains concrete benchmark assets used to run framework comparisons.

Current contents:

- `intake-triage/`: benchmark package for the `intake_triage` task
  - `prompt-pack.yml` and `fixtures/` are the starter validation split
  - `stress_v1/` is the harder comparison split with richer evidence and ambiguity

Each benchmark package should include:

- A versioned prompt pack
- Versioned fixtures
- Gold expectations
- References to the shared execution contract and rubrics

Guidance:

- Keep a lightweight starter split for harness validation.
- Add one or more harder stress splits that force real policy use, ambiguity handling, and multi-file reasoning.
