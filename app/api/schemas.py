from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

import pydantic
from pydantic import BaseModel, ConfigDict, Field

from app.constants import (
    MAX_BATCH_SIZE,
    MAX_DIMENSION_QUANTITY,
    SUPPORTED_BILLABLE_DIMENSIONS,
)


class RateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    per_1m: Decimal | None = None
    per_unit: Decimal | None = None

    @pydantic.model_validator(mode="after")
    def validate_rate(self) -> "RateSpec":
        """Ensure exactly one non-negative rate field is provided."""
        has_per_1m = self.per_1m is not None
        has_per_unit = self.per_unit is not None

        if has_per_1m == has_per_unit:
            message = "Exactly one of per_1m or " "per_unit must be provided"
            raise ValueError(message)

        value = self.per_1m if has_per_1m else self.per_unit
        if value is not None and value < 0:
            raise ValueError("Rate values must be >= 0")

        return self


class OverrideRatecard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = "USD"
    billable: dict[str, RateSpec]

    @pydantic.field_validator("billable")
    @classmethod
    def validate_billable_dimensions(
        cls: type["OverrideRatecard"],
        value: dict[str, RateSpec],
    ) -> dict[str, RateSpec]:
        """Validate override dimensions against supported billable keys."""
        if not value:
            message = "Override ratecard billable map must not be empty"
            raise ValueError(message)

        invalid_dimensions = sorted(
            dimension
            for dimension in value
            if dimension not in SUPPORTED_BILLABLE_DIMENSIONS
        )
        if invalid_dimensions:
            raise ValueError(
                (
                    "Unsupported billable dimensions in overrides: "
                    f"{invalid_dimensions}"
                )
            )

        return value


class EstimateOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ratecard: OverrideRatecard | None = None


class EstimateOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pricing_version: str = "latest"
    mode: Literal["strict", "lenient"] = "strict"
    gateway_pricing_mode: Literal[
        "prefer_gateway",
        "prefer_provider",
        "registry_only",
    ] = "prefer_gateway"


class EstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    usage: dict[str, int] = Field(min_length=1)
    options: EstimateOptions = Field(default_factory=EstimateOptions)
    overrides: EstimateOverrides = Field(default_factory=EstimateOverrides)

    @pydantic.field_validator("usage")
    @classmethod
    def validate_usage(
        cls: type["EstimateRequest"],
        value: dict[str, int],
    ) -> dict[str, int]:
        """Validate usage map structure and dimension quantity bounds."""
        for dimension, quantity in value.items():
            if not isinstance(dimension, str) or not dimension:
                raise ValueError("Usage dimensions must be non-empty strings")

            if isinstance(quantity, bool) or not isinstance(quantity, int):
                raise ValueError("Usage quantities must be integers")

            if quantity < 0 or quantity > MAX_DIMENSION_QUANTITY:
                raise ValueError(
                    (
                        f"Usage quantity for '{dimension}' must be between 0 "
                        f"and {MAX_DIMENSION_QUANTITY}"
                    )
                )

        return value


class BatchEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[EstimateRequest] = Field(
        min_length=1,
        max_length=MAX_BATCH_SIZE,
    )


class BreakdownEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    quantity: int
    rate: str
    cost: str


class TotalCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    cost: str


class EstimateMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    computed_at: str
    engine_version: str


class EstimateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pricing_version: str
    provider: str
    model: str
    breakdown: list[BreakdownEntry]
    total: TotalCost
    warnings: list[str]
    meta: EstimateMeta


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any]


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


class BatchErrorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    error: ErrorBody


class BatchEstimateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pricing_version: str
    results: list[EstimateResponse]
    errors: list[BatchErrorItem]


class ProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model_count: int
    capabilities: list[str]


class ProvidersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pricing_version: str
    providers: list[ProviderSummary]


class ModelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    effective_from: str
    capabilities: list[str]
    metadata: dict[str, Any] | None = None
    billable: dict[str, dict[str, str]] | None = None


class ModelsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pricing_version: str
    provider: str
    models: list[ModelSummary]


class VersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pricing_version: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    pricing_version: str
    engine_version: str
