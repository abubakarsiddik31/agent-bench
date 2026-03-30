# Benchmarks

This directory contains concrete benchmark assets used to run framework comparisons.

Current contents:

- `intake-triage/`: benchmark package for the `intake_triage` task
  - `stress_v1/` is the default comparison split with richer evidence and ambiguity

Each benchmark package should include:

- A versioned prompt pack
- Versioned fixtures
- Gold expectations
- References to the shared execution contract and rubrics

Guidance:

- Default to harder stress splits that force real policy use, ambiguity handling, and multi-file reasoning.
