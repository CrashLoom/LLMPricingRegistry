from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

RateKind = Literal["per_1m", "per_unit"]


@dataclass(frozen=True)
class Rate:
    kind: RateKind
    value: Decimal
    raw: str


@dataclass(frozen=True)
class TierCondition:
    # any usage key, or "context_tokens" (= input_uncached + input_cached)
    dimension: str
    # threshold
    gt: int


@dataclass(frozen=True)
class PricingTier:
    condition: TierCondition
    billable: dict[str, Rate]


@dataclass(frozen=True)
class ModelPricing:
    model: str
    effective_from: str
    billable: dict[str, Rate]
    capabilities: tuple[str, ...]
    metadata: dict[str, Any]
    pricing_tiers: tuple[PricingTier, ...]


@dataclass(frozen=True)
class ProviderPricing:
    provider: str
    models: dict[str, ModelPricing]
    source: dict[str, Any]


@dataclass(frozen=True)
class RegistryMeta:
    pricing_version: str
    published_at: str
    currency: str
    schema_version: int
