"""Existing separately bound Photos companion SDK; no launch or session create."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import stat
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.installed_code import source as process_source
from ios.adapters.snapshot_companion_artifact import artifact


class IOSSnapshotCompanionRuntime:
    def __init__(self,client,session_state,target,scope,artifact_path,guard,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(session_state,PrivateFeatureState) and type(target) is dict and target.get('platform')=='ios' and target.get('physical') is True
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic,sleep)) and callable(getattr(client,'call',None)) and callable(getattr(client,'execute',None)))
        self.client,self.session_state,self.target,self.guard=client,session_state,deepcopy(target),guard
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        need(type(scope) is dict and set(scope)=={'sourceRevision','artifactSha256','sessionId','generation','targetFingerprint'})
        context(dict(scope,processIdentity='1'));need(digest(target)==scope['targetFingerprint'])
        self.scope=deepcopy(scope);self.artifact_path=Path(artifact_path);self.artifact_pin=self.pin_artifact()
        self.artifact=artifact(self.artifact_path,scope['artifactSha256']);need(self.pin_artifact()==self.artifact_pin)
        need(target.get('appId')==self.artifact['bundle']['bundleId']);self.session=scope['sessionId'];self.original_session=session_state.read()
        need(type(self.original_session) is dict and self.original_session.get('sessionId')==self.session
            and self.original_session.get('generation')==scope['generation'] and self.original_session.get('targetFingerprint')==scope['targetFingerprint'])
        self.client.call('GET','/session/'+self.session);self.initial=self.probe()
        self.binding=context(dict(scope,processIdentity=str(self.initial['process']['pid'])))

    def pin_artifact(self):
        """Actual no-follow original identity; no repeated archive hashing."""
        before=self.artifact_path.lstat()
        descriptor=os.open(self.artifact_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as original:
            opened=os.fstat(original.fileno());named=self.artifact_path.lstat()
            def identity(value):
                need(stat.S_ISREG(value.st_mode) and value.st_nlink==1)
                return (value.st_dev,value.st_ino,value.st_mode,value.st_nlink,value.st_uid,value.st_size,value.st_mtime_ns,value.st_ctime_ns)
            pin=identity(before);need(pin==identity(opened)==identity(named));return pin

    def probe(self):
        need(self.guard() is not False and self.pin_artifact()==self.artifact_pin
            and self.session_state.read()==self.original_session and digest(self.target)==self.scope['targetFingerprint'])
        query=dict(bundleId=self.target['appId'])
        before=deepcopy(process_source(self.client.execute(self.session,'mobile: overteProcessSourceInfo',query)))
        actual=self.client.execute(self.session,'mobile: overteProcessInfo',query)
        need(type(actual) is dict and set(actual)=={'bundleId','pid','foreground'} and actual['bundleId']==self.target['appId']
            and type(actual['pid']) is int and 0<actual['pid']<=2147483647 and actual['foreground'] is True)
        after=deepcopy(process_source(self.client.execute(self.session,'mobile: overteProcessSourceInfo',query)))
        need(before==after and self.guard() is not False and self.pin_artifact()==self.artifact_pin and self.session_state.read()==self.original_session)
        value=dict(process=deepcopy(actual),source=after)
        if hasattr(self,'initial'):need(value==self.initial)
        return value

    def check(self):self.probe();return True

    def original(self,action):
        need(action in ('identity','clock'));self.check()
        remote='@'+self.target['appId']+':documents/snapshot-companion-'+action+'.json'
        encoded=self.client.execute(self.session,'mobile: pullFile',dict(remotePath=remote))
        need(type(encoded) is str and len(encoded)<=349528);raw=base64.b64decode(encoded,validate=True);need(1<=len(raw)<=262144)
        self.check();return raw

    @contextmanager
    def owner(self,run,client):
        from ios.adapters.snapshot_companion_owner import IOSSnapshotCompanionOwner
        lock=ScriptSourceLock(self.session_state.path.with_name('script-feature-sources.lock'));failure=None
        with lock.held():
            try:
                self.check();owner=IOSSnapshotCompanionOwner(self,lock,run,
                    PhaseFixtureReader(client,run,'snapshots',epoch_ms=self.epoch_ms,monotonic=self.monotonic))
                yield owner;self.check()
            except BaseException as original:failure=original
        if failure is not None:raise failure
