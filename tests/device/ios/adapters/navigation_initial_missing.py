"""Historical initial-process error owner, never a new lookup or OK input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace

from adapters.native_feature_observation import need
from ios.adapters.navigation_missing_actions import NavigationMissingActions
from ios.adapters.navigation_scene_admission import validate as admission_original


def original(value,initial,fixture_url):
    initial=admission_original(initial)
    if value is None:return None
    need(type(value) is dict)
    checker=object.__new__(NavigationMissingActions);checker.binding=initial['binding'];checker.run=initial['runId']
    checker.version=value.get('iosNavigationMissingActionsVersion')
    checker.admission=SimpleNamespace(archive=lambda:deepcopy(initial),fixture=SimpleNamespace(fixture_url=fixture_url,
        inputs=initial['providerInputs'],instance=initial['providerInstance']))
    state=checker.decode(value)
    # A failed/unknown OK is retained. Only the original independent cleared
    # source cut can discharge the dialog/listener's lifetime responsibility.
    need(state['proof'] is not None and state['cleared'] is not None)
    return deepcopy(state)
