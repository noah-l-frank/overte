"""Private Tablet settings for one genuinely prepared physical SDK.

The binding/native setup are retained originals, never caller-requested target
facts. Live admission independently verifies the existing SDK/native process.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from adapters.native_feature_observation import exact,need,validate as native_original
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.evidence import rectangle
from ios.adapters.world_web_measurements import origin

VERSION=1


def settings(value,*,role='primary',fixture_url=None):
    need(role in ('primary','actor'));exact(value,{'artifactRoot','imagePolicy','physicalBinding','setupNative','origins'})
    need(type(value['artifactRoot']) is str);root=Path(value['artifactRoot']);need(root.is_absolute() and root.resolve()==root and root.is_dir())
    PrivateFeatureState(root/'tabletweb-configuration-check')._parent()
    policy=value['imagePolicy'];exact(policy,{'source','marker','subject'});need(policy['source']=='native-screen')
    for key in ('marker','subject'):rectangle(policy[key],(4096,4096))
    native=value['setupNative'];binding=context(value['physicalBinding'])
    native_original(native,native['requestId'],int(binding['processIdentity']),native['capturedEpochMs'])
    exact(value['origins'],{'primary','foreign'});need(origin(value['origins']['primary'])!=origin(value['origins']['foreign']))
    if fixture_url is not None:
        parsed=urlsplit(fixture_url);actual=urlunsplit((parsed.scheme,parsed.netloc,'','',''))
        need(origin(value['origins']['primary'])==origin(actual))
    return deepcopy(value)
