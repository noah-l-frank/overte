"""Separate actor SDK and independently queried actual primary host SDK.

The world Web is local to the primary. The actor retains its own scene, avatar,
Qt and native process inventories while reading original primary VM/WK/DOM
receipts through independent typed reader instances. No normalized facts cross.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.self_tests.world_web_sources_fixture import SDK


class ActorSDK(SDK):
    @property
    def time(self):return self.primary.time
    @time.setter
    def time(self,value):self.primary.time=value
    def __init__(self,whole):
        self.primary=whole.sdk;primary=self.primary;current=primary.time
        super().__init__();primary.time=current
        self.use_snapshot=getattr(primary,'use_snapshot',False)
        self.use_whole_snapshot=getattr(primary,'use_whole_snapshot',False)
        self.pid=52;self.run=primary.run;self.base_epoch=primary.base_epoch;self.fixture_url=primary.fixture_url;self.role='actor'
        self.binding=dict(primary.binding,processIdentity=str(self.pid),sessionId='independent-actor-session',targetFingerprint=hashlib.sha256(b'independent-actor-target').hexdigest())
        self.world=deepcopy(whole.domain.world_template);self.world['processId']=self.pid;self.world['source']['scriptOriginal']['processId']=self.pid
        self.world['source']['domain']['selfSha256']='7'*64;self.browser=primary.browser
    def clock_packet(self,value):super().clock_packet(value);value['instance']='9'*32
    def phase(self,path,**kwargs):return self.primary.phase(path,**kwargs)
    def host_epoch(self):return self.primary.host_epoch()


class IndependentActor:
    def __init__(self,whole):
        self.whole=whole;self.sdk=ActorSDK(whole);self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.peer=self.sdk.owner(PrivateFeatureState(self.root/'ios-world-web-actor-sources.json'),self.lock)
        primary=whole.sdk;old=getattr(primary,'role',None);primary.role='actor-primary'
        try:self.primary=primary.owner(PrivateFeatureState(whole.scope.root/'ios-world-web-actor-primary-sources.json'),whole.scope.lock)
        finally:
            if old is None:del primary.role
            else:primary.role=old
    def close(self):self.held.__exit__(None,None,None);self.temp.cleanup()
