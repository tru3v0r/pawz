"""The action catalogue is the single source of truth for actions."""
from unittest.mock import Mock, call

import pytest

from pawz.core.models import ACTIONS, Binding
from pawz.engine import actions
from pawz.ui.windows import ProfileEditor


def test_every_action_has_a_label_and_one_behaviour():
    assert ACTIONS == actions.ACTION_IDS
    assert ProfileEditor.ACTION_LABELS == actions.LABELS
    for action in actions.CATALOGUE:
        assert action.label
        behaviours = [bool(action.mouse), bool(action.keys), action.custom_keys, action.internal]
        assert sum(behaviours) <= 1, action.id
        assert any(behaviours) or action.id == "none"


@pytest.mark.parametrize(("action", "keys", "expected"), [
    ("left_click", "", call.click("left")),
    ("tab_next", "", call.key_combo("ctrl+tab")),
    ("key_combo", "ctrl+c", call.key_combo("ctrl+c")),
])
def test_execute_drives_the_output(action, keys, expected):
    output = Mock()
    actions.execute(action, keys, output)
    assert output.mock_calls == [expected]


def test_none_and_internal_actions_send_nothing_and_unknown_ones_fail():
    output = Mock()
    actions.execute("none", "", output)
    actions.execute("open_settings", "", output)
    assert output.mock_calls == []
    with pytest.raises(ValueError, match="Unknown action"):
        actions.execute("teleport", "", output)


def test_only_catalogue_actions_are_accepted_in_settings():
    with pytest.raises(ValueError):
        Binding.parse({"action": "teleport"})
    assert actions.mouse_button("middle_click") == "middle"
    assert actions.mouse_button("tab_next") is None
