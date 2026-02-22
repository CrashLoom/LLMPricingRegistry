# LLM Pricing Registry

Open-source versioned pricing registry and deterministic cost estimation API for LLM usage billing.

54 models · 9 providers · Decimal-precise arithmetic · Zero database

## Providers

OpenAI · Anthropic · Google · DeepSeek · xAI · Groq · Kimi · OpenRouter · AWS Bedrock

## Stack

- Python 3.12+ · FastAPI · Pydantic v2
- `Decimal`-only billing engine (no float rounding errors)
- JSON Schema (Draft 2020-12) validated pricing data
- Lazy-loading provider cache

## Quick start

```bash
uv run uvicorn app.main:app --reload
```

## Docker

```bash
docker build -t llm-pricing-registry .
docker run -p 8080:8080 llm-pricing-registry
```

Or pull the published image:

```bash
docker pull ghcr.io/YOUR_ORG/llmpricingregistry:latest
docker run -p 8080:8080 ghcr.io/YOUR_ORG/llmpricingregistry:latest
```

## API

### Estimate cost

```bash
curl -X POST http://localhost:8080/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "usage": {
      "input_tokens_uncached": 1000000,
      "output_tokens": 500000
    }
  }'
```

```json
{
  "pricing_version": "2026-02-22",
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "breakdown": [
    { "dimension": "input_tokens_uncached", "quantity": 1000000, "rate": "0.8000", "cost": "0.800000" },
    { "dimension": "output_tokens",         "quantity":  500000, "rate": "3.2000", "cost": "1.600000" }
  ],
  "total": { "currency": "USD", "cost": "2.400000" },
  "warnings": [],
  "meta": { "computed_at": "...", "engine_version": "0.1.0" }
}
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/estimate` | Single cost estimate |
| `POST` | `/v1/estimate/batch` | Up to 100 estimates, partial success |
| `GET`  | `/v1/providers` | List providers and capabilities |
| `GET`  | `/v1/models?provider=openai&include_rates=true` | List models with optional rates |
| `GET`  | `/v1/versions` | Current pricing version |

### Override rates

Pass a custom ratecard to bypass the registry:

```json
{
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "usage": { "input_tokens_uncached": 1000000 },
  "overrides": {
    "ratecard": {
      "currency": "USD",
      "billable": { "input_tokens_uncached": { "per_1m": "0.50" } }
    }
  }
}
```

### Strict vs lenient mode

```json
{ "options": { "mode": "lenient" } }
```

- `strict` (default): unknown dimensions → 400 error
- `lenient`: unknown dimensions → skipped with a warning

## Pricing data

Pricing files live in [`pricing/providers/`](pricing/providers/) as versioned JSON, validated against [`schema/pricing_provider.schema.json`](schema/pricing_provider.schema.json) at startup.

To add or update a provider, edit the relevant JSON file and open a PR. The `[Unreleased]` section in [CHANGELOG.md](CHANGELOG.md) must be updated.

## Development

```bash
uv sync
uv run pytest tests/ -v
```

## Release process

1. Add changes under `## [Unreleased]` in [CHANGELOG.md](CHANGELOG.md)
2. When ready: move entries to a new versioned section, e.g. `## [0.2.0] - 2026-03-01`
3. Push a tag: `git tag v0.2.0 && git push origin v0.2.0`

GitHub Actions will:
- Run tests
- Verify the changelog entry exists
- Bump the version in `pyproject.toml`
- Build and push the Docker image to `ghcr.io` with `latest`, `0.2`, and `0.2.0` tags
- Create a GitHub Release with the changelog notes

## License

MIT
