from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.constants import MAX_DIMENSION_QUANTITY, SUPPORTED_BILLABLE_DIMENSIONS
from app.engine.exceptions import PricingError
from app.pricing.models import Rate
from app.pricing.repository import PricingRepository

COST_QUANTIZER = Decimal("0.000001")
ONE_MILLION = Decimal("1000000")


@dataclass(frozen=True)
class OverrideRatecard:
    currency: str
    billable: dict[str, Rate]


@dataclass(frozen=True)
class BreakdownItem:
    dimension: str
    quantity: int
    rate: str
    cost: str


@dataclass(frozen=True)
class EstimateResult:
    pricing_version: str
    provider: str
    model: str
    breakdown: list[BreakdownItem]
    currency: str
    total_cost: str
    warnings: list[str]
    computed_at: str
    engine_version: str


class BillingEngine:
    def __init__(
        self,
        repository: PricingRepository,
        engine_version: str,
    ) -> None:
        """Build a deterministic billing engine."""
        self._repository = repository
        self._engine_version = engine_version

    @property
    def engine_version(self) -> str:
        """Return the billing engine version string."""
        return self._engine_version

    def estimate(
        self,
        *,
        provider: str,
        model: str,
        usage: dict[str, int],
        mode: str = "strict",
        pricing_version: str = "latest",
        currency: str = "USD",
        override_ratecard: OverrideRatecard | None = None,
    ) -> EstimateResult:
        """Estimate cost for a provider/model usage payload."""
        self._validate_pricing_version(pricing_version)
        self._validate_currency(currency)
        self._validate_mode(mode)
        self._validate_usage(usage)

        resolved_model, rate_map, tier_warning = self._resolve_rate_map(
            provider=provider,
            model=model,
            usage=usage,
            override_ratecard=override_ratecard,
        )

        total_raw = Decimal("0")
        warnings: list[str] = []
        if tier_warning:
            warnings.append(tier_warning)
        breakdown: list[BreakdownItem] = []

        for dimension in sorted(usage):
            quantity = usage[dimension]
            if quantity == 0:
                continue

            if dimension not in SUPPORTED_BILLABLE_DIMENSIONS:
                self._handle_unsupported_dimension(
                    mode=mode,
                    provider=provider,
                    model=resolved_model,
                    dimension=dimension,
                    warnings=warnings,
                )
                continue

            rate = rate_map.get(dimension)
            if rate is None:
                self._handle_unsupported_dimension(
                    mode=mode,
                    provider=provider,
                    model=resolved_model,
                    dimension=dimension,
                    warnings=warnings,
                )
                continue

            cost_raw = self._compute_cost(quantity=quantity, rate=rate)
            total_raw += cost_raw
            breakdown.append(
                BreakdownItem(
                    dimension=dimension,
                    quantity=quantity,
                    rate=rate.raw,
                    cost=self._to_fixed_6(cost_raw),
                )
            )

        total_cost = self._to_fixed_6(total_raw)

        return EstimateResult(
            pricing_version=self._repository.pricing_version,
            provider=provider,
            model=resolved_model,
            breakdown=breakdown,
            currency=self._repository.currency,
            total_cost=total_cost,
            warnings=warnings,
            computed_at=datetime.now(UTC).isoformat(),
            engine_version=self._engine_version,
        )

    def _resolve_rate_map(
        self,
        *,
        provider: str,
        model: str,
        usage: dict[str, int],
        override_ratecard: OverrideRatecard | None,
    ) -> tuple[str, dict[str, Rate], str | None]:
        if override_ratecard is not None:
            if override_ratecard.currency != self._repository.currency:
                raise PricingError(
                    "INVALID_REQUEST",
                    f"Override currency must be {self._repository.currency}",
                    details={"currency": override_ratecard.currency},
                )
            return model, override_ratecard.billable, None

        provider_data = self._repository.get_provider(provider)
        if provider_data is None:
            raise PricingError(
                "PROVIDER_NOT_SUPPORTED",
                "Provider not supported",
                details={"provider": provider},
            )

        resolved_model = self._repository.resolve_model(provider, model)
        model_data = provider_data.models.get(resolved_model)
        if model_data is None:
            raise PricingError(
                "MODEL_NOT_FOUND",
                "Model not found",
                details={"provider": provider, "model": model},
            )

        rate_map = model_data.billable
        tier_warning: str | None = None

        if model_data.pricing_tiers:
            for tier in sorted(
                model_data.pricing_tiers,
                key=lambda t: t.condition.gt,
                reverse=True,
            ):
                value = self._resolve_dimension(
                    tier.condition.dimension, usage
                )
                if value > tier.condition.gt:
                    rate_map = tier.billable
                    tier_warning = (
                        f"Pricing tier applied: {tier.condition.dimension} "
                        f"{value} > {tier.condition.gt}."
                    )
                    break

        return resolved_model, rate_map, tier_warning

    @staticmethod
    def _resolve_dimension(dimension: str, usage: dict[str, int]) -> int:
        if dimension == "context_tokens":
            return usage.get("input_tokens_uncached", 0) + usage.get(
                "input_tokens_cached", 0
            )
        return usage.get(dimension, 0)

    @staticmethod
    def _compute_cost(*, quantity: int, rate: Rate) -> Decimal:
        quantity_decimal = Decimal(quantity)
        if rate.kind == "per_1m":
            return (quantity_decimal / ONE_MILLION) * rate.value
        return quantity_decimal * rate.value

    @staticmethod
    def _to_fixed_6(value: Decimal) -> str:
        quantized = value.quantize(COST_QUANTIZER, rounding=ROUND_HALF_UP)
        return format(quantized, "f")

    @staticmethod
    def _validate_mode(mode: str) -> None:
        if mode not in {"strict", "lenient"}:
            raise PricingError(
                "INVALID_REQUEST",
                "Mode must be strict or lenient",
                details={"mode": mode},
            )

    def _validate_pricing_version(self, pricing_version: str) -> None:
        if pricing_version in {"latest", self._repository.pricing_version}:
            return
        raise PricingError(
            "PRICING_VERSION_NOT_FOUND",
            "Pricing version not found",
            details={"pricing_version": pricing_version},
        )

    def _validate_currency(self, currency: str) -> None:
        if currency == self._repository.currency:
            return
        raise PricingError(
            "INVALID_REQUEST",
            f"Currency must be {self._repository.currency}",
            details={"currency": currency},
        )

    @staticmethod
    def _validate_usage(usage: dict[str, int]) -> None:
        for dimension, quantity in usage.items():
            if not isinstance(dimension, str) or not dimension:
                raise PricingError(
                    "INVALID_REQUEST",
                    "Usage dimensions must be non-empty strings",
                    details={"dimension": dimension},
                )

            if isinstance(quantity, bool) or not isinstance(quantity, int):
                raise PricingError(
                    "INVALID_REQUEST",
                    "Usage quantities must be integers",
                    details={"dimension": dimension, "quantity": quantity},
                )

            if quantity < 0 or quantity > MAX_DIMENSION_QUANTITY:
                raise PricingError(
                    "INVALID_REQUEST",
                    "Usage quantity out of range",
                    details={
                        "dimension": dimension,
                        "min": 0,
                        "max": MAX_DIMENSION_QUANTITY,
                        "quantity": quantity,
                    },
                )

    @staticmethod
    def _handle_unsupported_dimension(
        *,
        mode: str,
        provider: str,
        model: str,
        dimension: str,
        warnings: list[str],
    ) -> None:
        if mode == "strict":
            raise PricingError(
                "UNSUPPORTED_DIMENSION",
                "Unsupported dimension",
                details={
                    "provider": provider,
                    "model": model,
                    "dimension": dimension,
                },
            )

        warnings.append(
            (
                f"Ignored unsupported dimension '{dimension}' for provider "
                f"'{provider}' model '{model}'"
            )
        )
