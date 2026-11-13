import json

import pytest

from pawz.core.controller_catalog import (
    ControllerCatalog,
    ControllerDefinition,
    load_builtin_catalog,
)


def make_definition(model_id="custom.test-controller"):
    return ControllerDefinition(
        id=model_id,
        manufacturer="Example",
        model="Test Controller",
        family="generic",
        known_guids=(),
        physical_labels={},
        hardware_mapping={},
        svg=None,
        verified=False,
        provenance="Created by a test.",
    )


def test_builtin_catalog_is_schema_validated_and_does_not_claim_hardware_support():
    definitions = load_builtin_catalog()

    assert len(definitions) >= 19
    assert all(not model.verified and not model.known_guids for model in definitions)
    assert definitions[0].id == "generic.sdl-gamecontroller"
    assert definitions[0].known_guids == ()
    assert definitions[0].verified is False


def test_custom_catalog_round_trips_and_protects_builtin_definitions(tmp_path):
    path = tmp_path / "controllers" / "catalog.json"
    catalog = ControllerCatalog(path)
    definition = make_definition()

    catalog.add_custom(definition)

    reloaded = ControllerCatalog(path)
    assert reloaded.get(definition.id) == definition
    with pytest.raises(ValueError, match="cannot be modified"):
        reloaded.replace_custom(
            "generic.sdl-gamecontroller", make_definition("generic.sdl-gamecontroller"))
    with pytest.raises(ValueError, match="cannot be removed"):
        reloaded.remove_custom("generic.sdl-gamecontroller")


def test_custom_catalog_rejects_schema_invalid_and_builtin_collision(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "models": [{"id": "generic.sdl-gamecontroller"}],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid controller catalog"):
        ControllerCatalog(path)

    path.write_text(json.dumps({
        "schema_version": 1,
        "models": [make_definition("generic.sdl-gamecontroller").dump()],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="redefines built-in"):
        ControllerCatalog(path)
