"""Explicit private source-level iOS feature admission; no automatic target setup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.feature_fixture_access import client as fixture_client
from ios.adapters.normal_scripts import configuration as scripts_configuration

VERSION=6
READS=(1,2,3,4,5,6)
WHOLE_SETTINGS={'world-navigation':('worldNavigation','navigation_configuration'),
    'avatar-people':('avatarPeople','avatar_configuration'),
    'world-web':('worldWeb','world_web_configuration'),
    'tablet-web':('tabletWeb','tablet_web_configuration')}
LEGACY_AREAS=frozenset(('scripts','authentication','graphics','create','emotes'))
AREAS=LEGACY_AREAS|frozenset(WHOLE_SETTINGS)
# Emotes retains its readable v4 configuration and operation implementation.
# Real cached marker resources still need the two-stage native/process finalizer
# before this area can again advertise a complete operation triple.
COMPLETE_AREAS=frozenset(('scripts','authentication','graphics','create','world-navigation'))
OPERATIONS=frozenset('feature.'+area+'.'+kind for area in AREAS for kind in ('act','observe','cleanup'))|frozenset(
    'feature.'+area+'.terminal' for area in set(WHOLE_SETTINGS)|{'emotes'})


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
    exact(value,{'iosFeatureAdapterVersion','areas','fixtureConfig'}|({'graphics'} if version>=2 else set())|({'create'} if version>=3 else set())|({'emotes'} if version>=4 else set())
        |({field for field,_module in WHOLE_SETTINGS.values()} if version>=5 else set())
        |({'emoteCoordinatorVersion'} if version>=6 else set()))
    allowed=AREAS if version>=5 else LEGACY_AREAS if version==4 else LEGACY_AREAS-{'emotes'} if version==3 else LEGACY_AREAS-{'create','emotes'} if version==2 else LEGACY_AREAS-{'graphics','create','emotes'}
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
    if version>=6:
        if 'emotes' in value['areas']:
            need(type(value['emoteCoordinatorVersion']) is int and value['emoteCoordinatorVersion']==2)
        else:need(value['emoteCoordinatorVersion'] is None)
    if version>=5:
        from importlib import import_module
        for area,(field,module) in WHOLE_SETTINGS.items():
            if area in value['areas']:
                validate_settings=import_module('ios.adapters.'+module).settings
                if area=='avatar-people':validate_settings(value[field],role='primary')
                else:validate_settings(value[field])
            else:need(value[field] is None)
    return value


def capabilities(target):
    config=configuration()
    if config is None:return []
    need(set(config['areas'])<=COMPLETE_AREAS)
    # Reading an old configuration does not upgrade its coordinator or admit
    # rooted terminal ownership. Complete admission remains closed above.
    if 'emotes' in config['areas']:
        need(config['iosFeatureAdapterVersion']>=6 and config['emoteCoordinatorVersion']==2)
    need(scripts_configuration(target) is not None)
    if 'authentication' in config['areas']:
        from ios.adapters.authentication_origin import origin
        value=target.get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')
        need(type(value) is str and origin(value+'/feature-fixture/v1')==value)
    return sorted(operation for operation in OPERATIONS if operation.split('.')[1] in config['areas'])


def reader(config):
    validate(config)
    return fixture_client(config['fixtureConfig'])
