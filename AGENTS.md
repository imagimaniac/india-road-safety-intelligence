# AGENTS.md — working rules for this repository

These rules are binding for any agent or contributor touching this project.

## Non-negotiables

1. **Never fabricate** data, citations, statistics, crash-test ratings, scraping
   results, or findings. If it is not collected and traceable, it does not go in
   the report.
2. **Unavailable = `None`, never `0`.** Missing data is reported as missing, not
   filled in.
3. **Provenance is mandatory.** Every metric must trace back to entries in
   `config/sources.yaml`. Collection is blocked for any source whose `status` is
   not `verified`.
4. **Separate evidence types.** Accident counts, official statistics, news claims
   and crash-test scores are distinct entities/tables. Never merge them into one
   table as if equivalent.
5. **No premature causation.** A police-recorded factor is a recorded factor, not
   proof of cause. Observational correlation is not causation.
6. **Never compare crash-test star ratings** across different protocols, years,
   vehicle classes or markets without explicit qualification.
7. **Do not infer model-specific crashworthiness from a news article alone.**
   A headline mentioning a model is not reliable vehicle-identification evidence.

## Security & ethics

- No secrets in the repo. Secrets live in `.env` (gitignored) or environment
  variables; `.env.example` is the only committed template.
- Do not inspect or copy secrets/private data from other projects. This project is
  self-contained.
- Respect robots directives, terms of use, rate limits, copyright and access
  controls. No CAPTCHA/auth bypass, no stealth scraping, no paywall circumvention.
- Do not commit bulk copyrighted datasets, personal data, or data whose
  redistribution rights are unclear. Raw snapshots are gitignored.

## Engineering conventions

- Python 3.11+. Type hints. Keep dependencies minimal.
- Deterministic, dependency-free pure functions where possible (normalizers,
  hashing) so they are unit-testable without network.
- Network access is injectable (see the `HttpFetcher` pattern) so tests never hit
  the network; integration tests use small fixtures/mocks.
- Parameterised SQL only. Schema changes only via versioned, additive migrations.
- No file comments are required; prefer clear names and docstrings.
- Every step: smallest useful change → targeted tests → independent verification of
  the diff and behavior → report changed files, test results, unresolved issues.

## Git

- Do not commit, push, or publish without explicit human approval.
- Do not run destructive git commands. Preserve unrelated working-tree changes.

## Attribution

Reusable patterns are adapted (not copied wholesale) from the author's other local
projects; attribution is recorded in `docs/sources.md`.
