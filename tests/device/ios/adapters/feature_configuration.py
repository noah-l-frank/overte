"""Explicit private source-level iOS feature admission; no automatic target setup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.feature_fixture_access import client as fixture_client
from ios.adapters.normal_scripts import configuration as scripts_configuration

VERSION=1
OPERATIONS=frozenset('feature.scripts.'+kind for kind in ('act','observe','cleanup'))


def configuration(path=None):
    path=os.environ.get('OVERTE_IOS_FEATURE_ADAPTER_CONFIG') if path is None else path
    if path is None:return None
    need(isinstance(path,(str,Path)) and bool(str(path)))
    value=PrivateFeatureState(Path(path)).read()
    exact(value,{'iosFeatureAdapterVersion','areas','fixtureConfig'})
    need(type(value['iosFeatureAdapterVersion']) is int and value['iosFeatureAdapterVersion']==VERSION
         and value['areas']==['scripts'] and type(value['fixtureConfig']) is str
         and Path(value['fixtureConfig']).is_absolute())
    return value


def capabilities(target):
    config=configuration()
    if config is None:return []
    need(scripts_configuration(target) is not None)
    return sorted(OPERATIONS)


def reader(config):
    exact(config,{'iosFeatureAdapterVersion','areas','fixtureConfig'})
    return fixture_client(config['fixtureConfig'])
