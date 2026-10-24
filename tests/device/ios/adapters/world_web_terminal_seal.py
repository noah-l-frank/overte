"""Bounded private seal projection over separately retained whole originals.

Version 2 avoids embedding the already archived Source/retirement graph again.
It never qualifies a hash as a native fact: verification requires the freshly
decoded complete graph and the original role/window join. Literal v1 remains
readable with its exact embedded measurement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from feature_journeys import terminal

KEY='iosWorldWebTerminalSealOriginalVersion'
VERSION=2


def original(value):
    need(type(value) is dict and type(value.get(KEY)) is int and value[KEY] in (1,2))
    exact(value,{KEY,'samples','seal','measured' if value[KEY]==1 else 'measuredSha256'})
    if value[KEY]==2:
        need(type(value['measuredSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['measuredSha256']))
    return deepcopy(value)


def project(samples,measured,seal):
    """Storage projection only; caller already owns and validates originals."""
    return original({KEY:VERSION,'samples':deepcopy(samples),'measuredSha256':digest(measured),'seal':deepcopy(seal)})


def verify(value,measured,roles):
    """Rejoin the entire actually decoded graph, never a requested effect."""
    value=original(value);seal=value['seal']
    terminal.sealed(seal,seal['description'],value['samples'])
    if value[KEY]==1:need(same(value['measured'],measured))
    else:need(value['measuredSha256']==digest(measured))
    need(seal['liveOriginalSha256']==digest(dict(roles=roles,window=measured)))
    return deepcopy(measured)
