from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Query, Request

from app.api.schemas import (
    BatchErrorItem,
    BatchEstimateRequest,
    BatchEstimateResponse,
    BreakdownEntry,
    ErrorBody,
    EstimateMeta,
    EstimateRequest,
    EstimateResponse,
    HealthResponse,
    ModelsResponse,
    ModelSummary,
    ProvidersResponse,
    ProviderSummary,
    TotalCost,
    VersionResponse,
)
from app.engine import BillingEngine, OverrideRatecard, PricingError
from app.engine.calculator import EstimateResult
from app.pricing.models import Rate
from app.pricing.repository import PricingRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1")


def _get_repository(request: Request) -> PricingRepository:
    return request.app.state.repository


def _get_engine(request: Request) -> BillingEngine:
    return request.app.state.engine


def _to_decimal_string(value: Decimal) -> str:
    return format(value, "f")


def _to_override_ratecard(payload: EstimateRequest) -> OverrideRatecard | None:
    if payload.overrides.ratecard is None:
        return None

    billable: dict[str, Rate] = {}
    for dimension, spec in payload.overrides.ratecard.billable.items():
        if spec.per_1m is not None:
            raw_value = _to_decimal_string(spec.per_1m)
            billable[dimension] = Rate(
                kind="per_1m",
                value=spec.per_1m,
                raw=raw_value,
            )
        elif spec.per_unit is not None:
            raw_value = _to_decimal_string(spec.per_unit)
            billable[dimension] = Rate(
                kind="per_unit", value=spec.per_unit, raw=raw_value
            )
        else:
            raise ValueError(
                f"RateSpec for '{dimension}' has neither per_1m nor per_unit"
            )

    return OverrideRatecard(
        currency=payload.overrides.ratecard.currency, billable=billable
    )


_GATEWAY_MODE_WARNING = (
    "gateway_pricing_mode is not yet implemented; "
    "all requests use registry pricing regardless of this setting"
)


def _check_gateway_mode(options_mode: str) -> str | None:
    if options_mode != "prefer_gateway":
        return _GATEWAY_MODE_WARNING
    return None


def _estimate_response_from_result(
    result: EstimateResult,
    extra_warnings: list[str] | None = None,
) -> EstimateResponse:
    warnings = list(result.warnings)
    if extra_warnings:
        warnings.extend(extra_warnings)

    return EstimateResponse(
        pricing_version=result.pricing_version,
        provider=result.provider,
        model=result.model,
        breakdown=[
            BreakdownEntry(
                dimension=item.dimension,
                quantity=item.quantity,
                rate=item.rate,
                cost=item.cost,
            )
            for item in result.breakdown
        ],
        total=TotalCost(currency=result.currency, cost=result.total_cost),
        warnings=warnings,
        meta=EstimateMeta(
            computed_at=result.computed_at,
            engine_version=result.engine_version,
        ),
    )


@router.post("/estimate", response_model=EstimateResponse)
def estimate(payload: EstimateRequest, request: Request) -> EstimateResponse:
    """Estimate a single request cost using registry or override pricing."""
    engine = _get_engine(request)
    logger.info(
        "estimate_requested",
        extra={
            "event": "estimate_requested",
            "provider": payload.provider,
            "model": payload.model,
        },
    )

    result = engine.estimate(
        provider=payload.provider,
        model=payload.model,
        usage=payload.usage,
        mode=payload.options.mode,
        pricing_version=payload.options.pricing_version,
        override_ratecard=_to_override_ratecard(payload),
    )

    gw_warning = _check_gateway_mode(payload.options.gateway_pricing_mode)
    extra = [gw_warning] if gw_warning else None
    return _estimate_response_from_result(result, extra_warnings=extra)


@router.post("/estimate/batch", response_model=BatchEstimateResponse)
def estimate_batch(
    payload: BatchEstimateRequest, request: Request
) -> BatchEstimateResponse:
    """Estimate costs for a batch and return partial successes."""
    repository = _get_repository(request)
    engine = _get_engine(request)

    results: list[EstimateResponse] = []
    errors: list[BatchErrorItem] = []

    for index, item in enumerate(payload.items):
        try:
            result = engine.estimate(
                provider=item.provider,
                model=item.model,
                usage=item.usage,
                mode=item.options.mode,
                pricing_version=item.options.pricing_version,
                override_ratecard=_to_override_ratecard(item),
            )
        except PricingError as exc:
            errors.append(
                BatchErrorItem(
                    index=index,
                    error=ErrorBody(
                        code=exc.code, message=exc.message, details=exc.details
                    ),
                )
            )
            continue

        gw_warning = _check_gateway_mode(item.options.gateway_pricing_mode)
        extra = [gw_warning] if gw_warning else None
        results.append(
            _estimate_response_from_result(
                result,
                extra_warnings=extra,
            )
        )

    return BatchEstimateResponse(
        pricing_version=repository.pricing_version,
        results=results,
        errors=errors,
    )


@router.get("/providers", response_model=ProvidersResponse)
def list_providers(request: Request) -> ProvidersResponse:
    """List available providers with model counts and capabilities."""
    repository = _get_repository(request)

    providers: list[ProviderSummary] = []
    for provider_name in repository.list_providers():
        provider = repository.get_provider(provider_name)
        if provider is None:
            continue

        capabilities = sorted(
            {
                capability
                for model in provider.models.values()
                for capability in model.capabilities
            }
        )
        providers.append(
            ProviderSummary(
                provider=provider.provider,
                model_count=len(provider.models),
                capabilities=capabilities,
            )
        )

    return ProvidersResponse(
        pricing_version=repository.pricing_version, providers=providers
    )


@router.get("/models", response_model=ModelsResponse)
def list_models(
    request: Request,
    provider: str = Query(..., min_length=1),
    include_rates: bool = Query(False),
) -> ModelsResponse:
    """List models for a provider with optional billable rate details."""
    repository = _get_repository(request)
    provider_data = repository.get_provider(provider)
    if provider_data is None:
        raise PricingError(
            "PROVIDER_NOT_SUPPORTED",
            "Provider not supported",
            details={"provider": provider},
        )

    models: list[ModelSummary] = []
    for model in repository.list_models(provider):
        models.append(
            ModelSummary(
                model=model.model,
                effective_from=model.effective_from,
                capabilities=list(model.capabilities),
                metadata=model.metadata or None,
                billable=(
                    repository.serialize_billable(model.billable)
                    if include_rates
                    else None
                ),
            )
        )

    return ModelsResponse(
        pricing_version=repository.pricing_version,
        provider=provider,
        models=models,
    )


@router.get("/versions", response_model=VersionResponse)
def get_versions(request: Request) -> VersionResponse:
    """Return the active pricing version for this deployment."""
    repository = _get_repository(request)
    return VersionResponse(pricing_version=repository.pricing_version)


@router.get("/healthz", response_model=HealthResponse, include_in_schema=False)
def healthz(request: Request) -> HealthResponse:
    """Liveness/readiness probe — returns 200 when the app is ready."""
    repository = _get_repository(request)
    engine = _get_engine(request)
    return HealthResponse(
        status="ok",
        pricing_version=repository.pricing_version,
        engine_version=engine.engine_version,
    )
