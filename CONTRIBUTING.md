# Contributing to DotSci

Thanks for helping. DotSci is early, so the most useful contributions are the ones that make the spec clearer and the tooling more reliable.

## Where to help

- **Manifest and run specs** in `spec/`: ambiguities, missing fields, and cases the schema cannot express.
- **Runner toolkit** in `packages/runner`: bug fixes, tests, and support for more tolerance rules.
- **Sample claims**: a manifest for a published result with public data and public code, added under `examples/`. See `docs/writing-a-claim.md`.
- **Docs** in `docs/`: anything unclear or out of date.

## Ground rules

1. Open an issue before large changes so we can agree on direction.
2. Keep pull requests focused. One change per PR.
3. Add or update tests when you change runner code.
4. Never commit secrets, keys, tokens, or personal data.
5. Sample claims must use real public data and code, and must describe results neutrally. Outcomes are `reproduced` or `not_reproduced`. Never describe a paper as wrong or a team as careless.
6. Do not add generated images or third-party brand assets to this repository.

## Development setup

```bash
cd packages/runner
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

CI runs the same tests on every pull request.

## Commit messages

Short, present tense, and specific. Examples: `Add relative tolerance to compare`, `Clarify seed handling in manifest spec`.

## Proposing spec changes

Spec changes affect every runner, so include in the issue or PR:

- what problem the change solves
- the exact schema diff
- an example manifest that uses it
- how older manifests are handled

## Code of conduct

Be direct and kind. Critique the work, not the person. Harassment of contributors or of authors of claimed papers is not tolerated.
