Le sandbox semble bloquer le téléchargement.
Voici le **fichier complet en Markdown** — tu peux le copier directement dans `SPEC.md`.

---

````md
# LLM Pricing Registry & Estimation API

Version: 0.1.0
Status: Draft (v1 scope)
License: MIT (recommended)

---

# 1. Overview

## Purpose

This project provides:

1. A canonical open LLM pricing registry (versioned JSON dataset)
2. A deterministic billing engine
3. A FastAPI HTTP API for cost estimation

The system computes cost estimates given:

- Provider
- Model
- Billable usage dimensions (tokens, images, audio, etc.)
- Optional pricing version
- Optional custom rate overrides

The system does NOT:

- Scrape provider pricing automatically
- Proxy LLM requests
- Guarantee correctness of token counting
- Perform usage metering

---

# 2. Architecture

Pricing Registry (JSON, versioned)
↓
Billing Engine (Python library)
↓
FastAPI HTTP API

Stateless service
No database
No rate limiting (v1)
No authentication (v1)

---

# 3. Directory Structure

pricing/
registry_meta.json
providers/
openai.json
anthropic.json
google.json
deepseek.json
openrouter.json
aliases/
openai_aliases.json
openrouter_mappings.json

schema/
pricing_provider.schema.json
pricing_registry_meta.schema.json

app/
main.py
api/
engine/
pricing/

---

# 4. Pricing Registry Specification

## 4.1 registry_meta.json

```json
{
  "pricing_version": "2026-02-22",
  "published_at": "2026-02-22T00:00:00Z",
  "currency": "USD",
  "schema_version": 1
}
```
````

Rules:

- pricing_version MUST increment on any pricing change
- currency is USD in v1
- historical versions optional (future)

---

## 4.2 Provider Pricing File Example

pricing/providers/openai.json

```json
{
  "provider": "openai",
  "models": [
    {
      "model": "gpt-4o-mini",
      "effective_from": "2025-01-01",
      "billable": {
        "input_tokens_uncached": { "per_1m": "0.1500" },
        "input_tokens_cached": { "per_1m": "0.0750" },
        "output_tokens": { "per_1m": "0.6000" }
      },
      "capabilities": ["token_pricing", "cached_input"]
    }
  ]
}
```

---

# 5. Supported Billable Dimensions

| Dimension             | Unit    |
| --------------------- | ------- |
| input_tokens_uncached | tokens  |
| input_tokens_cached   | tokens  |
| output_tokens         | tokens  |
| reasoning_tokens      | tokens  |
| embedding_tokens      | tokens  |
| tool_calls            | count   |
| image_count           | count   |
| image_megapixels      | MP      |
| audio_input_seconds   | seconds |
| audio_output_seconds  | seconds |
| requests              | count   |

Rate formats:

per_1m:

```json
{ "per_1m": "0.1500" }
```

per_unit:

```json
{ "per_unit": "0.0025" }
```

All rates stored as decimal strings.

---

# 6. Billing Engine Rules

- Use decimal.Decimal only
- No float usage allowed
- Round final cost to 6 decimal places
- Deterministic output

## Cost Formula

For per_1m:

cost = (quantity / 1_000_000) \* rate_per_1m

For per_unit:

cost = quantity \* rate_per_unit

Total = sum(all dimension costs)

---

# 7. API Specification

Base URL: /v1

---

## POST /v1/estimate

### Request

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "usage": {
    "input_tokens_uncached": 1200,
    "input_tokens_cached": 800,
    "output_tokens": 350
  },
  "options": {
    "pricing_version": "latest",
    "mode": "strict",
    "gateway_pricing_mode": "prefer_gateway",
    "currency": "USD"
  },
  "overrides": {
    "ratecard": null
  }
}
```

---

### Response

```json
{
  "pricing_version": "2026-02-22",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "breakdown": [
    {
      "dimension": "input_tokens_uncached",
      "quantity": 1200,
      "rate": "0.1500",
      "cost": "0.000180"
    }
  ],
  "total": {
    "currency": "USD",
    "cost": "0.000450"
  },
  "warnings": [],
  "meta": {
    "computed_at": "ISO-8601",
    "engine_version": "0.1.0"
  }
}
```

---

## POST /v1/estimate/batch

Constraints:

- Max 100 items
- Max body size: 1MB

---

## GET /v1/providers

Returns supported providers and capabilities.

---

## GET /v1/models?provider=openai

Returns models for provider.

Optional query:

- include_rates=true|false

---

## GET /v1/versions

Returns:

```json
{
  "pricing_version": "2026-02-22"
}
```

---

# 8. Modes

strict:

- Unsupported non-zero dimension → 400 error

lenient:

- Unsupported dimension ignored
- Warning returned

Default: strict

---

# 9. Overrides

Users may override ratecard:

```json
{
  "overrides": {
    "ratecard": {
      "currency": "USD",
      "billable": {
        "input_tokens_uncached": { "per_1m": "0.1000" },
        "output_tokens": { "per_1m": "0.4000" }
      }
    }
  }
}
```

If provided:

- Registry lookup is bypassed
- Schema validation still required

---

# 10. Validation Rules

- All quantities must be integers ≥ 0
- Max per dimension: 10,000,000,000
- Max batch size: 100
- Max request body: 1MB

---

# 11. Error Model

Standard format:

```json
{
  "error": {
    "code": "MODEL_NOT_FOUND",
    "message": "Model not found",
    "details": {}
  }
}
```

Error Codes:

- INVALID_REQUEST
- PROVIDER_NOT_SUPPORTED
- MODEL_NOT_FOUND
- PRICING_VERSION_NOT_FOUND
- UNSUPPORTED_DIMENSION
- INTERNAL_ERROR

---

# 12. Implementation Requirements

- Python 3.12+
- FastAPI
- Pydantic v2
- decimal.Decimal
- Structured logging
- No DB
- No rate limiting (v1)

---

# 13. Contribution Rules

- Pricing changes must:
  - Increment pricing_version
  - Pass JSON schema validation
  - Be sorted deterministically
  - Include official source reference in PR description

- One provider per file

```

```
