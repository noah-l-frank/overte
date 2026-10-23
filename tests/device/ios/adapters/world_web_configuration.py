"""Closed private Web image/origin configuration and existing peer selection."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from ios.adapters.graphics_configuration import settings as images
from ios.adapters.create_configuration import selector
from ios.adapters.world_web_measurements import origin


def settings(value,*,role='primary',target=None):
    need(role in ('primary','actor'));peer='actorTarget' if role=='primary' else 'primaryTarget'
    exact(value,{'artifactRoot','imagePolicy','origins',peer});selector(value[peer])
    images({key:value[key] for key in ('artifactRoot','imagePolicy')});exact(value['origins'],{'primary','foreign'})
    need(origin(value['origins']['primary'])!=origin(value['origins']['foreign']))
    if target is not None:need(selector(target)!=value[peer])
    return deepcopy(value)
