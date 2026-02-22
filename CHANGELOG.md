# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial pricing registry with 9 providers (OpenAI, Anthropic, Google, DeepSeek, xAI, Groq, Kimi, OpenRouter, AWS Bedrock)
- Deterministic billing engine using Python `Decimal` for financial precision
- `POST /v1/estimate` — single cost estimate
- `POST /v1/estimate/batch` — up to 100 estimates per request with partial success
- `GET /v1/providers` — list all providers and capabilities
- `GET /v1/models` — list models for a provider with optional billable rates
- `GET /v1/versions` — current pricing version
- Model alias resolution (e.g. `gpt-5` → `gpt-5.2`)
- Provider alias resolution (e.g. `grok` → `xai`, `bedrock` → `aws_bedrock`)
- Override ratecard support for custom pricing
- Strict and lenient modes for unsupported dimensions
- JSON Schema validation (Draft 2020-12) for all pricing data
- Lazy-loading provider cache — provider files loaded on first access
- 1MB request body limit middleware
- Structured JSON logging

### Fixed

- Fixed GitHub Actions test failures where `pytest` was missing in CI environments.
- Updated Docker publish metadata tagging to always publish a `latest` image tag alongside semver tags.

[Unreleased]: https://github.com/CrashLoom/LLMPricingRegistry/commits/HEAD
