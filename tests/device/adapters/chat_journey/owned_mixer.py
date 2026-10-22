"""Original private fixture credentials; current mixer facts stay independent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from urllib.parse import urlsplit
import uuid

from adapters.chat_actor_files import stamp
from adapters.chat_journey.mixer_control import FixtureMixerControl
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError


class _OwnedMixerControl(FixtureMixerControl):
    def __init__(self,owner,*,readonly):
        self.owner=owner
        super().__init__(owner.config['messagesMixerControlUrl'],owner.config['controlToken'],owner.guard_callback,
            readonly=readonly,clock_ms=lambda:int(time.time()*1000),monotonic=owner.peer.monotonic)

    def _request(self,command):
        value=super()._request(command)
        need(value['domainId']==self.owner.config['domainId'])
        return value


class OwnedChatMixer:
    """Bind two original control readers to the already-owned actor fixture.

    This object does not start, discover, poll, stop or signal any process. The
    ready file is only original credential/config authority, never readiness.
    """
    def __init__(self,peer,ready_store):
        need(isinstance(peer,OwnedChatPeer) and isinstance(ready_store,PrivateFeatureState)
            and ready_store.path!=peer.config_store.path)
        self.peer,self.store=peer,ready_store
        before=ready_store.path.lstat();self.config=deepcopy(ready_store.read());self.stamp=stamp(before)
        need(stamp(ready_store.path.lstat())==self.stamp)
        exact(self.config,{'schemaVersion','domainUrl','domainHost','domainId','requiredMarkers','expectedEntityCount',
            'bootstrapScriptUrl','peerScriptUrl','peerDisplayName','controlUrl','controlToken',
            'collaborationEditUrl','collaborationStateUrl','messagesMixerControlUrl'})
        need(type(self.config['schemaVersion']) is int and self.config['schemaVersion']==1
            and type(self.config['domainId']) is str and str(uuid.UUID(self.config['domainId']))==self.config['domainId']
            and uuid.UUID(self.config['domainId']).int)
        origin=urlsplit(self.config['messagesMixerControlUrl'])
        need(origin.scheme=='http' and origin.hostname=='127.0.0.1' and origin.port is not None
            and 1<=origin.port<=65535 and not origin.username and not origin.password and not origin.query and not origin.fragment
            and origin.geturl()=='http://127.0.0.1:'+str(origin.port)+'/v1/messages-mixer-state')
        base='http://127.0.0.1:'+str(origin.port)+'/v1/'
        need(self.config['controlUrl']==base+'domain-state' and self.config['collaborationEditUrl']==base+'collaboration-edit'
            and self.config['collaborationStateUrl']==base+'collaboration-state'
            and type(self.config['controlToken']) is str and re.fullmatch('[A-Za-z0-9_-]{40,128}',self.config['controlToken']))
        self.guard_callback=self.guard;self.guard()
        self.controls=tuple(_OwnedMixerControl(self,readonly=readonly) for readonly in (False,True))

    def guard(self):
        try:
            need(stamp(self.store.path.lstat())==self.stamp and self.store.read()==self.config
                and stamp(self.store.path.lstat())==self.stamp and self.peer.guard() is True)
            return True
        except Exception:raise NativeUIError('Original owned Chat mixer configuration is unavailable') from None
