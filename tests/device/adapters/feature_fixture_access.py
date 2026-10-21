"""Private adapter-only fixture reads; no runner or independent actor credential."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client

VERSION=1


class AdapterFixtureClient(Client):
    def __init__(self,url,token):
        super().__init__(url,token);self._adapter_admitted=False

    def request(self,path,value=None,method=None,**kwargs):
        need(value is None and method in (None,'GET'))
        if not self._adapter_admitted:
            access=super().request('/adapter-reader',adapter_access=True)
            exact(access,{'fixtureAdapterAccessVersion','role','canMutate','canPublish','peerFactsVisible'})
            need(type(access['fixtureAdapterAccessVersion']) is int and access['fixtureAdapterAccessVersion']==VERSION
                and access['role']=='adapter' and access['canMutate'] is False and access['canPublish'] is False
                and access['peerFactsVisible'] is False)
            self._adapter_admitted=True
        need('adapter_access' not in kwargs)
        return super().request(path,value,method,adapter_access=True,**kwargs)


def client(path,*,configured_url=None):
    value=PrivateFeatureState(Path(path)).read()
    exact(value,{'fixtureAdapterAccessVersion','fixtureUrl','adapterToken'})
    need(type(value['fixtureAdapterAccessVersion']) is int and value['fixtureAdapterAccessVersion']==VERSION
        and type(value['adapterToken']) is str and 32<=len(value['adapterToken'])<=256
        and value['adapterToken'].isascii() and all(33<=ord(c)<=126 for c in value['adapterToken'])
        and (configured_url is None or configured_url==value['fixtureUrl']))
    return AdapterFixtureClient(value['fixtureUrl'],value['adapterToken'])
