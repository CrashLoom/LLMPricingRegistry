from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_estimate_endpoint() -> None:
    """Return a deterministic estimate for a valid request payload."""
    response = client.post(
        "/v1/estimate",
        json={
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "usage": {
                "input_tokens_uncached": 1200,
                "input_tokens_cached": 800,
                "output_tokens": 350,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pricing_version"] == "2026-02-22"
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["total"]["cost"] == "0.002240"


def test_estimate_endpoint_with_provider_alias() -> None:
    """Support provider aliases on the single estimate endpoint."""
    response = client.post(
        "/v1/estimate",
        json={
            "provider": "grok",
            "model": "grok-4",
            "usage": {
                "input_tokens_uncached": 1_000_000,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "grok"
    assert payload["model"] == "grok-4"
    assert payload["total"]["cost"] == "3.000000"


def test_estimate_endpoint_strict_unsupported_dimension() -> None:
    """Return validation errors for unsupported dimensions in strict mode."""
    response = client.post(
        "/v1/estimate",
        json={
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "usage": {
                "reasoning_tokens": 1200,
            },
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "UNSUPPORTED_DIMENSION"


def test_batch_endpoint_partial_success() -> None:
    """Return mixed success and error entries for batch estimates."""
    response = client.post(
        "/v1/estimate/batch",
        json={
            "items": [
                {
                    "provider": "openai",
                    "model": "gpt-4.1-mini",
                    "usage": {
                        "input_tokens_uncached": 1000,
                    },
                },
                {
                    "provider": "openai",
                    "model": "does-not-exist",
                    "usage": {
                        "input_tokens_uncached": 1000,
                    },
                },
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pricing_version"] == "2026-02-22"
    assert len(payload["results"]) == 1
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["error"]["code"] == "MODEL_NOT_FOUND"


def test_models_endpoint_with_rates() -> None:
    """Include billable rate details when `include_rates=true`."""
    response = client.get(
        "/v1/models", params={"provider": "openai", "include_rates": "true"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["models"]
    assert "billable" in payload["models"][0]


def test_models_endpoint_with_provider_alias() -> None:
    """Support provider aliases on the models listing endpoint."""
    response = client.get("/v1/models", params={"provider": "bedrock"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "bedrock"
    assert any(
        model["model"] == "moonshot/kimi-k2-thinking@us-east-1"
        for model in payload["models"]
    )


def test_versions_endpoint() -> None:
    """Return the active pricing version from metadata."""
    response = client.get("/v1/versions")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"pricing_version": "2026-02-22"}


def test_providers_endpoint_contains_expanded_registry() -> None:
    """List the expected base and extended provider set."""
    response = client.get("/v1/providers")

    assert response.status_code == 200
    payload = response.json()
    providers = {entry["provider"] for entry in payload["providers"]}
    expected_base = {"openai", "anthropic", "google", "deepseek", "openrouter"}
    assert expected_base.issubset(providers)
    assert {"xai", "groq", "kimi", "aws_bedrock"}.issubset(providers)
    assert {"mistral", "together"}.issubset(providers)


def test_estimate_with_override_ratecard() -> None:
    """Apply override pricing ratecards when provided in request."""
    response = client.post(
        "/v1/estimate",
        json={
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "usage": {"input_tokens_uncached": 1_000_000},
            "overrides": {
                "ratecard": {
                    "currency": "USD",
                    "billable": {
                        "input_tokens_uncached": {"per_1m": "1.0"},
                    },
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"]["cost"] == "1.000000"


def test_estimate_empty_usage_rejected() -> None:
    """Reject estimate requests with an empty usage payload."""
    response = client.post(
        "/v1/estimate",
        json={
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "usage": {},
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_models_endpoint_unknown_provider() -> None:
    """Return provider-not-supported for unknown provider names."""
    response = client.get("/v1/models", params={"provider": "nonexistent"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "PROVIDER_NOT_SUPPORTED"


def test_gateway_pricing_mode_warning() -> None:
    """Emit a warning for non-default gateway pricing mode options."""
    response = client.post(
        "/v1/estimate",
        json={
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "usage": {"input_tokens_uncached": 1000},
            "options": {"gateway_pricing_mode": "registry_only"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert any("gateway_pricing_mode" in w for w in payload["warnings"])


def test_internal_error_does_not_leak_details() -> None:
    """Ensure internal errors do not expose sensitive details fields."""
    response = client.get("/v1/models", params={"provider": "nonexistent"})
    if response.status_code == 500:
        payload = response.json()
        assert "reason" not in payload["error"].get("details", {})


def test_body_size_limit() -> None:
    """Reject payloads larger than the configured request body limit."""
    response = client.post(
        "/v1/estimate",
        content=("x" * (1_048_576 + 1)).encode("utf-8"),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "INVALID_REQUEST"
