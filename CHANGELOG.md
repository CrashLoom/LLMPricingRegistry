# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1](https://github.com/CrashLoom/LLMPricingRegistry/compare/v0.1.0...v0.1.1) (2026-02-22)


### Bug Fixes

* ensure correct release please workflow ([#3](https://github.com/CrashLoom/LLMPricingRegistry/issues/3)) ([73898d3](https://github.com/CrashLoom/LLMPricingRegistry/commit/73898d3714b6205a898ba6fc4cc8e86dadab3957))

## 0.1.0 (2026-02-22)

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

### Bug Fixes

* ensure ci working properly ([#1](https://github.com/CrashLoom/LLMPricingRegistry/issues/1)) ([3a37139](https://github.com/CrashLoom/LLMPricingRegistry/commit/3a37139701a2cdf72948206a4c6ea3a22cf7f8ab))
