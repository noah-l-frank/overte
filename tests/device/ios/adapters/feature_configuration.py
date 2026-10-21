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
AREAS=frozenset(('scripts','authentication'))
OPERATIONS=frozenset('feature.'+area+'.'+kind for area in AREAS for kind in ('act','observe','cleanup'))


def configuration(path=None):
    path=os.environ.get('OVERTE_IOS_FEATURE_ADAPTER_CONFIG') if path is None else path
    if path is None:return None
    need(isinstance(path,(str,Path)) and bool(str(path)))
    value=PrivateFeatureState(Path(path)).read()
    exact(value,{'iosFeatureAdapterVersion','areas','fixtureConfig'})
    need(type(value['iosFeatureAdapterVersion']) is int and value['iosFeatureAdapterVersion']==VERSION
         and type(value['areas']) is list and 1<=len(value['areas'])<=len(AREAS)
         and all(type(area) is str and area in AREAS for area in value['areas'])
         and len(set(value['areas']))==len(value['areas']) and type(value['fixtureConfig']) is str
         and Path(value['fixtureConfig']).is_absolute())
    return value


def capabilities(target):
    config=configuration()
    if config is None:return []
    need(scripts_configuration(target) is not None)
    if 'authentication' in config['areas']:
        from ios.adapters.authentication_origin import origin
        value=target.get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')
        need(type(value) is str and origin(value+'/feature-fixture/v1')==value)
    return sorted(operation for operation in OPERATIONS if operation.split('.')[1] in config['areas'])


def reader(config):
    exact(config,{'iosFeatureAdapterVersion','areas','fixtureConfig'})
    return fixture_client(config['fixtureConfig'])
