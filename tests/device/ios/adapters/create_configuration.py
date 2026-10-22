"""Explicit private Create image/rez configuration and existing peer selection."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,need
from ios.adapters.graphics_configuration import settings as images
from ios.adapters.create_rez_client import configuration as rez


def selector(value):
    need(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',value));return value


def settings(value,*,role='primary',target=None):
    need(role in ('primary','actor'));peer='actorTarget' if role=='primary' else 'primaryTarget'
    exact(value,{'artifactRoot','imagePolicy',peer}|({'rezAuthority'} if role=='primary' else set()))
    selector(value[peer]);images({key:value[key] for key in ('artifactRoot','imagePolicy')})
    if target is not None:need(selector(target)!=value[peer])
    if role=='primary':rez(value['rezAuthority'])
    return deepcopy(value)
