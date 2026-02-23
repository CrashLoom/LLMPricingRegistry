# Contributing to LLM Pricing Registry

Thanks for contributing. This project is intentionally focused: it provides
deterministic LLM cost estimation from a pricing snapshot registry.

## Ways to contribute

- Add or update provider/model pricing data
- Report and fix estimation mismatches
- Improve API behavior, tests, and docs
- Improve CI/release automation

## Development setup

```bash
uv sync --extra dev
pre-commit run -a
uv run pytest tests/ -v
```

Python 3.12+ is required.

## Pricing data contribution rules

Pricing data is stored in `pricing/providers/*.json` and validated by
`schema/pricing_provider.schema.json`.

Required for every provider file:

- `source.url`: official pricing source URL
- `source.last_verified`: verification date in `YYYY-MM-DD`

When submitting pricing changes:

1. Update the relevant file in `pricing/providers/`.
2. Keep all rates as decimal strings (for deterministic Decimal math).
3. Update aliases in `pricing/aliases/` if model/provider naming changed.
4. Add/adjust tests when behavior changes.
5. Update docs if API behavior or supported providers changed.

## Pull requests

- Use conventional commit style in PR title (`feat:`, `fix:`, `docs:`, etc.).
- Keep PRs focused and small when possible.
- Fill the PR template checklist.

## Issues and labels

Use issue forms for:

- Add provider/model requests
- Pricing corrections
- Estimation logic bugs

We maintain onboarding labels:

- `good first issue`
- `help wanted`

## Code of conduct

Be respectful and constructive in issues and pull requests.
