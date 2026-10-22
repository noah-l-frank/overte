"""Explicit private source-level iOS feature admission; no automatic target setup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.feature_fixture_access import client as fixture_client
from ios.adapters.normal_scripts import configuration as scripts_configuration

VERSION=4
READS=(1,2,3,4)
AREAS=frozenset(('scripts','authentication','graphics','create','emotes'))
COMPLETE_AREAS=frozenset(('scripts','authentication','graphics','create','emotes'))
OPERATIONS=frozenset('feature.'+area+'.'+kind for area in AREAS for kind in ('act','observe','cleanup'))


def configuration(path=None):
    path=os.environ.get('OVERTE_IOS_FEATURE_ADAPTER_CONFIG') if path is None else path
    if path is None:return None
    need(isinstance(path,(str,Path)) and bool(str(path)))
    value=PrivateFeatureState(Path(path)).read()
    validate(value)
    return value


def validate(value):
    need(type(value) is dict and type(value.get('iosFeatureAdapterVersion')) is int and value['iosFeatureAdapterVersion'] in READS)
    version=value['iosFeatureAdapterVersion']
    exact(value,{'iosFeatureAdapterVersion','areas','fixtureConfig'}|({'graphics'} if version>=2 else set())|({'create'} if version>=3 else set())|({'emotes'} if version>=4 else set()))
    allowed=AREAS if version>=4 else AREAS-{'emotes'} if version==3 else AREAS-{'create','emotes'} if version==2 else AREAS-{'graphics','create','emotes'}
    need(type(value['iosFeatureAdapterVersion']) is int
         and type(value['areas']) is list and 1<=len(value['areas'])<=len(AREAS)
         and all(type(area) is str and area in allowed for area in value['areas'])
         and len(set(value['areas']))==len(value['areas']) and type(value['fixtureConfig']) is str
         and Path(value['fixtureConfig']).is_absolute())
    if version>=2:
        if 'graphics' in value['areas']:
            from ios.adapters.graphics_configuration import settings
            settings(value['graphics'])
        else:need(value['graphics'] is None)
    if version>=3:
        if 'create' in value['areas']:
            from ios.adapters.create_configuration import settings
            settings(value['create'])
        else:need(value['create'] is None)
    if version>=4:
        if 'emotes' in value['areas']:
            from ios.adapters.emote_configuration import settings
            settings(value['emotes'])
        else:need(value['emotes'] is None)
    return value


def capabilities(target):
    config=configuration()
    if config is None:return []
    need(set(config['areas'])<=COMPLETE_AREAS)
    need(scripts_configuration(target) is not None)
    if 'authentication' in config['areas']:
        from ios.adapters.authentication_origin import origin
        value=target.get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')
        need(type(value) is str and origin(value+'/feature-fixture/v1')==value)
    return sorted(operation for operation in OPERATIONS if operation.split('.')[1] in config['areas'])


def reader(config):
    validate(config)
    return fixture_client(config['fixtureConfig'])
