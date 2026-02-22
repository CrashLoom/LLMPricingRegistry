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
class ModelPricing:
    model: str
    effective_from: str
    billable: dict[str, Rate]
    capabilities: tuple[str, ...]
    metadata: dict[str, Any]


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
