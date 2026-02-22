from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.pricing import models as pricing_models


class PricingRepository:
    def __init__(self, root_dir: Path | None = None) -> None:
        """Initialize repository paths, validators, and lazy caches."""
        self._root_dir = root_dir or Path(__file__).resolve().parents[2]
        self._pricing_dir = self._root_dir / "pricing"
        self._schema_dir = self._root_dir / "schema"

        self._provider_validator = Draft202012Validator(
            self._read_json(self._schema_dir / "pricing_provider.schema.json")
        )
        meta_schema = self._schema_dir / "pricing_registry_meta.schema.json"
        meta_schema_payload = self._read_json(meta_schema)
        self._meta_validator = Draft202012Validator(meta_schema_payload)

        self._meta = self._load_meta()
        self._provider_files = self._discover_providers()
        self._provider_cache: dict[str, pricing_models.ProviderPricing] = {}
        self._model_aliases: dict[str, dict[str, str]] | None = None
        self._provider_aliases: dict[str, str] | None = None

    @property
    def pricing_version(self) -> str:
        """Return the active pricing version from registry metadata."""
        return self._meta.pricing_version

    @property
    def currency(self) -> str:
        """Return the registry currency code."""
        return self._meta.currency

    @property
    def meta(self) -> pricing_models.RegistryMeta:
        """Return parsed registry metadata."""
        return self._meta

    def list_providers(self) -> list[str]:
        """List provider slugs discovered in the registry."""
        return sorted(self._provider_files)

    def get_provider(
        self,
        provider: str,
    ) -> pricing_models.ProviderPricing | None:
        """Get provider pricing data by canonical or alias provider name."""
        canonical_provider = self.resolve_provider(provider)

        if canonical_provider in self._provider_cache:
            return self._provider_cache[canonical_provider]

        path = self._provider_files.get(canonical_provider)
        if path is None:
            return None

        loaded = self._load_provider(path)
        self._provider_cache[canonical_provider] = loaded
        return loaded

    def resolve_provider(self, provider: str) -> str:
        """Resolve provider alias chains to a canonical provider key."""
        aliases = self._get_provider_aliases()
        origin = provider
        resolved = provider
        visited: set[str] = set()

        while True:
            if resolved in visited:
                return origin
            visited.add(resolved)

            next_provider = aliases.get(resolved)
            if next_provider is None:
                return resolved

            resolved = next_provider

    def resolve_model(self, provider: str, model: str) -> str:
        """Resolve a model alias within a provider namespace."""
        aliases = self._get_model_aliases()
        canonical_provider = self.resolve_provider(provider)
        provider_aliases = aliases.get(canonical_provider, {})
        return provider_aliases.get(model, model)

    def get_model(
        self,
        provider: str,
        model: str,
    ) -> pricing_models.ModelPricing | None:
        """Get model pricing by provider/model, including alias resolution."""
        provider_data = self.get_provider(provider)
        if not provider_data:
            return None
        resolved = self.resolve_model(provider, model)
        return provider_data.models.get(resolved)

    def list_models(self, provider: str) -> list[pricing_models.ModelPricing]:
        """List all models for a provider sorted by model id."""
        provider_data = self.get_provider(provider)
        if not provider_data:
            return []
        models: list[pricing_models.ModelPricing] = []
        for key in sorted(provider_data.models):
            models.append(provider_data.models[key])
        return models

    @staticmethod
    def serialize_billable(
        billable: dict[str, pricing_models.Rate],
    ) -> dict[str, dict[str, str]]:
        """Serialize rate objects to raw strings for API responses."""
        serialized: dict[str, dict[str, str]] = {}
        for dimension in sorted(billable):
            rate = billable[dimension]
            serialized[dimension] = {rate.kind: rate.raw}
        return serialized

    # ------------------------------------------------------------------
    # Internal loading
    # ------------------------------------------------------------------

    def _load_meta(self) -> pricing_models.RegistryMeta:
        raw_meta = self._read_json(self._pricing_dir / "registry_meta.json")
        self._validate_schema(
            self._meta_validator,
            raw_meta,
            "registry_meta.json",
        )
        return pricing_models.RegistryMeta(
            pricing_version=raw_meta["pricing_version"],
            published_at=raw_meta["published_at"],
            currency=raw_meta["currency"],
            schema_version=raw_meta["schema_version"],
        )

    def _discover_providers(self) -> dict[str, Path]:
        """Scan provider directory for JSON files without reading them."""
        providers_dir = self._pricing_dir / "providers"
        result: dict[str, Path] = {}
        for path in sorted(providers_dir.glob("*.json")):
            result[path.stem] = path
        return result

    def _load_provider(
        self,
        provider_path: Path,
    ) -> pricing_models.ProviderPricing:
        raw = self._read_json(provider_path)
        self._validate_schema(
            self._provider_validator,
            raw,
            provider_path.name,
        )

        models = self._parse_models(raw["models"], provider_path.name)
        return pricing_models.ProviderPricing(
            provider=raw["provider"],
            models=models,
            source=raw.get("source", {}),
        )

    def _parse_models(
        self,
        raw_models: list[dict[str, Any]],
        filename: str,
    ) -> dict[str, pricing_models.ModelPricing]:
        models: dict[str, pricing_models.ModelPricing] = {}
        for raw_model in raw_models:
            billable = self._parse_billable(raw_model["billable"])
            entry = pricing_models.ModelPricing(
                model=raw_model["model"],
                effective_from=raw_model["effective_from"],
                billable=billable,
                capabilities=tuple(raw_model.get("capabilities", [])),
                metadata=raw_model.get("metadata", {}),
            )
            if entry.model in models:
                message = f"Duplicate model '{entry.model}' in {filename}"
                raise ValueError(message)
            models[entry.model] = entry
        return models

    @staticmethod
    def _parse_billable(
        raw_billable: dict[str, Any],
    ) -> dict[str, pricing_models.Rate]:
        billable: dict[str, pricing_models.Rate] = {}
        for dimension, raw_rate in raw_billable.items():
            if "per_1m" in raw_rate:
                kind, raw_value = "per_1m", str(raw_rate["per_1m"])
            else:
                kind, raw_value = "per_unit", str(raw_rate["per_unit"])
            billable[dimension] = pricing_models.Rate(
                kind=kind, value=Decimal(raw_value), raw=raw_value
            )
        return billable

    def _get_model_aliases(self) -> dict[str, dict[str, str]]:
        if self._model_aliases is None:
            self._model_aliases = self._load_model_aliases()
        return self._model_aliases

    def _load_model_aliases(self) -> dict[str, dict[str, str]]:
        aliases: dict[str, dict[str, str]] = {}
        aliases_dir = self._pricing_dir / "aliases"

        for alias_path in sorted(aliases_dir.glob("*.json")):
            raw = self._read_json(alias_path)
            provider = raw.get("provider")
            mapping = raw.get("aliases", {})

            if isinstance(provider, str) and isinstance(mapping, dict):
                provider_aliases: dict[str, str] = {}
                for alias, canonical in mapping.items():
                    provider_aliases[str(alias)] = str(canonical)
                aliases[provider] = provider_aliases

        return aliases

    def _get_provider_aliases(self) -> dict[str, str]:
        if self._provider_aliases is None:
            self._provider_aliases = self._load_provider_aliases()
        return self._provider_aliases

    def _load_provider_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        aliases_dir = self._pricing_dir / "aliases"

        for alias_path in sorted(aliases_dir.glob("*.json")):
            raw = self._read_json(alias_path)
            mapping = raw.get("provider_aliases", {})
            if not isinstance(mapping, dict):
                continue

            for alias, canonical in mapping.items():
                aliases[str(alias)] = str(canonical)

        return aliases

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _validate_schema(
        validator: Draft202012Validator,
        payload: dict[str, Any],
        filename: str,
    ) -> None:
        errors = sorted(
            validator.iter_errors(payload),
            key=lambda err: list(err.path),
        )
        if not errors:
            return

        first_error = errors[0]
        path = ".".join(str(part) for part in first_error.path)
        path_suffix = f" at '{path}'" if path else ""
        raise ValueError(
            (
                "Schema validation failed for "
                f"{filename}{path_suffix}: {first_error.message}"
            )
        )
