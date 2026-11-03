"""Pure host ownership of original Pico remote Avatar observation files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState


def source_store(adapter, target, run, *, area='avatar-people'):
    need(area in ('avatar-people','emotes'))
    parent = adapter._avatar_parent_store(target, run)
    prefix='avatar-remote-owner-' if area=='avatar-people' else 'emote-remote-owner-'
    return PrivateFeatureState(parent.path.with_name(parent.path.name.replace('avatar-parent-owner-', prefix, 1)))


def retained(adapter, target):
    if adapter.pico_configuration is None: return False
    # Reuse the actual target-derived key; no candidate/native reader is called.
    return any(namespace_owned(store,store.path.name.removesuffix('0'*32 + '.json'))
        for store in (source_store(adapter,target,'0'*32,area=area) for area in ('avatar-people','emotes')))


def namespace_owned(store, prefix):
    store._parent()
    with os.scandir(store.path.parent) as entries:
        for index, entry in enumerate(entries):
            need(index < 4096)
            if entry.name.startswith(prefix): return True
    return False
