"""Explicit paired Avatar SDKs and separate private read/publication authority.

Configuration creates no SDK session, changes no server rights and supplies
no product fact. Authority tokens stay in the live client, not feature state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import re
from adapters.native_feature_observation import exact,need
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from ios.adapters.authentication_origin import origin
from ios.adapters.graphics_configuration import settings as image_settings

VERSION=1


def selector(value):
    need(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',value));return value


def settings(value,*,role,target=None):
    need(role in ('primary','actor'));peer='actorTarget' if role=='primary' else 'primaryTarget'
    fields={'artifactRoot','imagePolicy',peer};exact(value,fields|set(value).intersection({'authorityRead','authorityControlRoot'}))
    if 'authorityControlRoot' in value:
        root=value['authorityControlRoot'];need(role=='primary' and type(root) is str and root and Path(root).is_absolute())
    selector(value[peer]);image_settings({key:value[key] for key in ('artifactRoot','imagePolicy')})
    if target is not None:need(selector(target)!=value[peer])
    need(role=='primary' or 'authorityRead' in value)
    if 'authorityRead' in value:
        authority=value['authorityRead'];exact(authority,{'mode','token'})
        need(authority['mode'] in ('reader','adapter') and type(authority['token']) is str and 32<=len(authority['token'])<=512
            and all(33<=ord(character)<=126 for character in authority['token']))
    return deepcopy(value)


class AvatarAuthorityClient(Client):
    """Read only this run's account scope and this SDK role's credentials."""
    def __init__(self,client,run,role,authority):
        need(isinstance(client,Client) and role in ('primary','actor'));origin(client.url);identifier(run)
        exact(authority,{'mode','token'});need(authority['mode'] in ('reader','adapter')
            and type(authority['token']) is str and 32<=len(authority['token'])<=512
            and all(33<=ord(character)<=126 for character in authority['token']))
        super().__init__(client.url,authority['token'],monotonic=client.monotonic,sleep=client.sleep)
        self.run,self.role,self.mode=run,role,authority['mode']

    def request(self,path,value=None,method=None,**kwargs):
        prefix='/runs/'+self.run+'/avatar/'
        need(path in (prefix+'accounts',prefix+'credentials/'+self.role) and value is None and method in (None,'GET')
            and not kwargs)
        return super().request(path,method='GET',adapter_access=self.mode=='adapter')


def authority_client(client,run,role,configuration):
    """The actor publisher token never substitutes for authority read input."""
    need(isinstance(client,Client) and role in ('primary','actor'));identifier(run);origin(client.url)
    if 'authorityRead' in configuration:return AvatarAuthorityClient(client,run,role,configuration['authorityRead'])
    need(role=='primary');return client
