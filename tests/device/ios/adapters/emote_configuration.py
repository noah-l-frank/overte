"""Explicit private Emote image policy and independent prepared target selection.

This validates configuration only. It creates no SDK session, qualifies no
candidate and advertises no whole feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,need
from ios.adapters.graphics_configuration import settings as image_settings

VERSION=1


def selector(value):
    need(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',value));return value


def settings(value,*,role='primary',target=None):
    need(role in ('primary','actor'));peer_key='actorTarget' if role=='primary' else 'primaryTarget'
    exact(value,{'artifactRoot','imagePolicy',peer_key});selector(value[peer_key])
    image_settings({key:value[key] for key in ('artifactRoot','imagePolicy')})
    if target is not None:need(selector(target)!=value[peer_key])
    return deepcopy(value)
