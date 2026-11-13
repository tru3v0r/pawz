"""Versioned controller catalog loading and user-defined model persistence."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CATALOG_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ControllerDefinition:
    id: str
    manufacturer: str
    model: str
    family: str
    known_guids: tuple[str, ...]
    physical_labels: dict[str, str]
    hardware_mapping: dict[str, str]
    svg: str | None
    verified: bool
    provenance: str

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> ControllerDefinition:
        return cls(
            id=raw["id"],
            manufacturer=raw["manufacturer"],
            model=raw["model"],
            family=raw["family"],
            known_guids=tuple(raw["known_guids"]),
            physical_labels=dict(raw["physical_labels"]),
            hardware_mapping=dict(raw["hardware_mapping"]),
            svg=raw["svg"],
            verified=raw["verified"],
            provenance=raw["provenance"],
        )

    def dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "family": self.family,
            "known_guids": list(self.known_guids),
            "physical_labels": self.physical_labels,
            "hardware_mapping": self.hardware_mapping,
            "svg": self.svg,
            "verified": self.verified,
            "provenance": self.provenance,
        }


def _validate_catalog(data: Any, schema: dict[str, Any]) -> dict[str, Any]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors)
        raise ValueError(f"Invalid controller catalog: {details}")
    ids = [model["id"] for model in data["models"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate controller model IDs")
    return data


def load_builtin_catalog() -> tuple[ControllerDefinition, ...]:
    data_dir = files("pawz").joinpath("data", "controllers")
    schema = json.loads(data_dir.joinpath("controller.schema.json").read_text(
        encoding="utf-8"))
    catalog = json.loads(data_dir.joinpath("catalog.json").read_text(encoding="utf-8"))
    _validate_catalog(catalog, schema)
    return tuple(ControllerDefinition.parse(model) for model in catalog["models"])


class ControllerCatalog:
    """Keep immutable packaged models separate from editable user definitions."""

    def __init__(self, custom_catalog_path: Path):
        self._builtins = {model.id: model for model in load_builtin_catalog()}
        self._custom_catalog_path = custom_catalog_path
        self._schema = json.loads(files("pawz").joinpath(
            "data", "controllers", "controller.schema.json").read_text(encoding="utf-8"))
        self._custom = self._load_custom()

    @property
    def definitions(self) -> tuple[ControllerDefinition, ...]:
        return tuple(self._builtins.values()) + tuple(self._custom.values())

    def get(self, model_id: str) -> ControllerDefinition:
        try:
            return self._builtins.get(model_id) or self._custom[model_id]
        except KeyError as exc:
            raise KeyError(f"Unknown controller model: {model_id}") from exc

    def is_builtin(self, model_id: str) -> bool:
        return model_id in self._builtins

    def add_custom(self, definition: ControllerDefinition) -> None:
        if definition.id in self._builtins or definition.id in self._custom:
            raise ValueError(f"Controller model ID already exists: {definition.id}")
        self._validate_definition(definition)
        self._custom[definition.id] = definition
        self._save_custom()

    def replace_custom(self, model_id: str, definition: ControllerDefinition) -> None:
        if model_id in self._builtins:
            raise ValueError("Built-in controller definitions cannot be modified")
        if model_id not in self._custom:
            raise KeyError(f"Unknown custom controller model: {model_id}")
        if definition.id != model_id and (
                definition.id in self._builtins or definition.id in self._custom):
            raise ValueError(f"Controller model ID already exists: {definition.id}")
        self._validate_definition(definition)
        del self._custom[model_id]
        self._custom[definition.id] = definition
        self._save_custom()

    def remove_custom(self, model_id: str) -> None:
        if model_id in self._builtins:
            raise ValueError("Built-in controller definitions cannot be removed")
        try:
            del self._custom[model_id]
        except KeyError as exc:
            raise KeyError(f"Unknown custom controller model: {model_id}") from exc
        self._save_custom()

    def _load_custom(self) -> dict[str, ControllerDefinition]:
        if not self._custom_catalog_path.exists():
            return {}
        data = json.loads(self._custom_catalog_path.read_text(encoding="utf-8"))
        _validate_catalog(data, self._schema)
        custom = {
            model["id"]: ControllerDefinition.parse(model)
            for model in data["models"]
        }
        collisions = self._builtins.keys() & custom.keys()
        if collisions:
            raise ValueError(
                f"Custom catalog redefines built-in model IDs: {sorted(collisions)}")
        return custom

    def _save_custom(self) -> None:
        catalog = {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "models": [model.dump() for model in self._custom.values()],
        }
        _validate_catalog(catalog, self._schema)
        self._custom_catalog_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(catalog, ensure_ascii=False, indent=2)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self._custom_catalog_path.parent,
            prefix=f".{self._custom_catalog_path.name}.",
            suffix=".tmp",
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, self._custom_catalog_path)
        except OSError:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def _validate_definition(self, definition: ControllerDefinition) -> None:
        _validate_catalog({
            "schema_version": CATALOG_SCHEMA_VERSION,
            "models": [definition.dump()],
        }, self._schema)
