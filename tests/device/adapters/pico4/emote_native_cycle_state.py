"""Host-only Emote native-cycle namespace; absence never drops orphan intent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState


def cycle_store(adapter, target):
    inputs = adapter._emote_input_store(target)
    return PrivateFeatureState(inputs.path.with_name(inputs.path.stem + '-native-cycle.json'))


def native_cycle_owned(adapter, target):
    """Bounded name-only check before generic teardown, with no product queries.

    A missing root does not authorize discarding prepared files or children.
    Unreadable/oversized directories fail closed. No entry is adopted or removed.
    """
    store = cycle_store(adapter, target); store._parent()
    name = store.path.name
    prefixes = tuple(name + suffix for suffix in ('.pending-', '.frame-', '.child-'))
    with os.scandir(store.path.parent) as entries:
        for index, entry in enumerate(entries):
            need(index < 4096)
            if entry.name == name or entry.name.startswith(prefixes):
                return True
    return False
