from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.engine.calculator import BillingEngine, OverrideRatecard
from app.engine.exceptions import PricingError
from app.pricing.models import Rate
from app.pricing.repository import PricingRepository

ROOT_DIR = Path(__file__).resolve().parents[1]


def make_engine() -> BillingEngine:
    """Create a billing engine bound to the local test registry."""
    repository = PricingRepository(root_dir=ROOT_DIR)
    return BillingEngine(repository=repository, engine_version="0.1.0")


def test_estimate_openai_gpt_41_mini() -> None:
    """Estimate costs for a standard OpenAI model request."""
    engine = make_engine()

    result = engine.estimate(
        provider="openai",
        model="gpt-4.1-mini",
        usage={
            "input_tokens_uncached": 1200,
            "input_tokens_cached": 800,
            "output_tokens": 350,
        },
    )

    assert result.pricing_version == "2026-02-22"
    assert result.total_cost == "0.002240"
    assert len(result.breakdown) == 3


def test_alias_resolution() -> None:
    """Resolve OpenAI model aliases to their canonical model id."""
    engine = make_engine()

    result = engine.estimate(
        provider="openai",
        model="gpt-5",
        usage={"input_tokens_uncached": 1_000_000},
    )

    assert result.model == "gpt-5.2"
    assert result.total_cost == "1.750000"


def test_provider_alias_resolution_for_xai() -> None:
    """Resolve the `grok` provider alias to `xai`."""
    engine = make_engine()

    result = engine.estimate(
        provider="grok",
        model="grok-4",
        usage={"input_tokens_uncached": 1_000_000},
    )

    assert result.total_cost == "3.000000"


def test_provider_alias_resolution_for_aws_bedrock() -> None:
    """Resolve the `bedrock` alias to the AWS Bedrock provider."""
    engine = make_engine()

    result = engine.estimate(
        provider="bedrock",
        model="moonshot/kimi-k2-thinking@us-east-1",
        usage={"input_tokens_uncached": 1_000_000},
    )

    assert result.total_cost == "0.600000"


def test_unsupported_dimension_in_strict_mode() -> None:
    """Raise an error on unsupported dimensions in strict mode."""
    engine = make_engine()

    with pytest.raises(PricingError) as exc_info:
        engine.estimate(
            provider="openai",
            model="gpt-4.1-mini",
            usage={"reasoning_tokens": 10},
            mode="strict",
        )

    assert exc_info.value.code == "UNSUPPORTED_DIMENSION"


def test_unsupported_dimension_in_lenient_mode() -> None:
    """Ignore unsupported dimensions and emit warnings in lenient mode."""
    engine = make_engine()

    result = engine.estimate(
        provider="openai",
        model="gpt-4.1-mini",
        usage={"reasoning_tokens": 10},
        mode="lenient",
    )

    assert result.total_cost == "0.000000"
    assert result.warnings


def test_override_ratecard_bypasses_registry_lookup() -> None:
    """Use override rates without requiring provider/model registry entries."""
    engine = make_engine()

    override = OverrideRatecard(
        currency="USD",
        billable={
            "input_tokens_uncached": Rate(
                kind="per_1m",
                value=Decimal("1.0"),
                raw="1.0",
            ),
            "image_count": Rate(
                kind="per_unit",
                value=Decimal("0.5"),
                raw="0.5",
            ),
        },
    )

    result = engine.estimate(
        provider="unknown-provider",
        model="custom-model",
        usage={"input_tokens_uncached": 1_000_000, "image_count": 3},
        override_ratecard=override,
    )

    assert result.model == "custom-model"
    assert result.total_cost == "2.500000"


def test_pricing_version_not_found() -> None:
    """Reject pricing versions that are not present."""
    engine = make_engine()

    with pytest.raises(PricingError) as exc_info:
        engine.estimate(
            provider="openai",
            model="gpt-4.1-mini",
            usage={"input_tokens_uncached": 1000},
            pricing_version="2025-01-01",
        )

    assert exc_info.value.code == "PRICING_VERSION_NOT_FOUND"
