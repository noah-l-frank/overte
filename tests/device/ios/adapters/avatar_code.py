"""Reviewed candidate module identities, independent of native observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import re

from adapters.native_feature_observation import exact,integer,need
from feature_journeys.contract import json_document
from ios.adapters.avatar_scripts import SUFFIXES

VERSION=1
FILE=Path(__file__).parents[1]/'avatar-code-pins.v1.json'


def validate(value):
    exact(value,{'avatarCodePinsVersion','encoding','sources'})
    need(type(value['avatarCodePinsVersion']) is int and value['avatarCodePinsVersion']==VERSION
        and value['encoding']=='utf-16le-code-units')
    exact(value['sources'],{suffix[1:] for suffix in SUFFIXES})
    for source in value['sources'].values():
        exact(source,{'codeUnits','sha256'})
        need(integer(source['codeUnits'],1,4194304) and type(source['sha256']) is str and re.fullmatch('[a-f0-9]{64}',source['sha256']))
    return {'/'+name:deepcopy(source) for name,source in value['sources'].items()}


def pins():
    raw=FILE.read_bytes();need(len(raw)<=8192)
    return validate(json_document(raw))


def for_worker(value,manager_id,expected,*,required):
    """Select names only; expected identities always come from reviewed pins.

    Default scripts can run combined or as separate managers. A manager need
    not have evaluated another manager's modules. Mandatory actual call-site
    modules cannot be omitted, and every present relevant module is checked.
    """
    from ios.adapters import avatar_scripts
    selected=avatar_scripts.worker(value,manager_id)
    names={next(suffix for suffix in SUFFIXES if row['url'].endswith(suffix)) for row in selected['avatar']['code']}
    need(type(expected) is dict and type(required) is set and required and required<=names<=set(expected))
    subset={name:deepcopy(expected[name]) for name in names}
    avatar_scripts.bound_code(value,manager_id,subset)
    return subset
