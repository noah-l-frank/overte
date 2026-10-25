"""Read-only existing process scopes across an owned Photos app handoff.

These guards may observe background OS continuity. They never make a background
native/UI read, mutate a driver bundle, create a session or launch a process.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from ios.adapters.installed_code import InstalledCodeBinding,source as process_source
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.snapshot_companion_owner import IOSSnapshotCompanionOwner
from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime
from ios.adapters.tablet_web_admission import installed_forward


class PhotosClientContext:
    def __init__(self,runtime,selector,binding):
        need(isinstance(runtime,IOSScriptRuntime));self.runtime,self.selector,self.binding=runtime,selector,deepcopy(context(binding))
        self.client,self.session,self.session_state,self.target,self.scope=runtime._existing(selector)
        need(same(dict(self.scope,processIdentity=binding['processIdentity']),binding))
        self.gate=runtime.adapter._binding(selector,self.client,self.session,self.session_state,self.target)
        need(isinstance(self.gate,InstalledCodeBinding));self.installed=deepcopy(self.gate.record())
        need(self.installed is not None and self.installed['phase']=='bound' and self.installed['process']['pid']==int(binding['processIdentity']))
        self.os_source=deepcopy(process_source(self.gate.process_source()));self.probe()

    def probe(self,foreground=None):
        need(foreground is None or type(foreground) is bool)
        client,session,state,target,scope=self.runtime._existing(self.selector)
        need(session==self.session and same(state,self.session_state) and same(target,self.target) and same(scope,self.scope))
        # Canonical explicit background permission is confined to this OS-only
        # context. Existing source['check'] guards are never replaced or called.
        actual=self.gate.continuity(allow_background=True);record=deepcopy(self.gate.record());installed_forward(self.installed,record)
        original=deepcopy(process_source(self.gate.process_source()));need(same(original,self.os_source)
            and actual['pid']==int(self.binding['processIdentity']) and (foreground is None or actual['foreground']==foreground))
        return dict(binding=deepcopy(self.binding),process=actual,source=original,installed=record)

    def foreground_sources(self):
        self.probe(True);source=self.runtime._sources(self.selector);need(same(source['binding'],self.binding));self.probe(True);return source

    def activate(self):
        self.probe(False);return self.client.execute(self.session,'mobile: activateApp',dict(bundleId=self.target['appId']))


class PhotosCompanionContext:
    def __init__(self,client,session_store,target,binding,artifact_path,admission_store,lock,run,fixture_url,*,epoch_ms,monotonic,sleep):
        need(isinstance(session_store,PrivateFeatureState) and isinstance(admission_store,PrivateFeatureState));lock.assert_held()
        self.client,self.session_store,self.target,self.binding,self.artifact_path=client,session_store,deepcopy(target),deepcopy(context(binding)),Path(artifact_path)
        self.admission=IOSSnapshotCompanionOwner.archive(admission_store,lock,binding,run,fixture_url,artifact_path)
        self.admission.result();self.artifact=self.admission.artifact;self.os_scope=deepcopy(self.admission.os_scope)
        need(target.get('platform')=='ios' and target.get('physical') is True and target.get('appId')==self.artifact['bundle']['bundleId']
            and digest(target)==binding['targetFingerprint'])
        self.session=binding['sessionId'];self.session_state=session_store.read();need(type(self.session_state) is dict
            and self.session_state.get('sessionId')==self.session and self.session_state.get('generation')==binding['generation']
            and self.session_state.get('targetFingerprint')==binding['targetFingerprint'])
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        # Reuse the pure no-follow stat pin helper, not the foreground runtime's
        # constructor or probe with a relaxed flag.
        self.artifact_pin=IOSSnapshotCompanionRuntime.pin_artifact(self);self.probe()

    def probe(self,foreground=None):
        need(foreground is None or type(foreground) is bool)
        need(self.session_store.read()==self.session_state and IOSSnapshotCompanionRuntime.pin_artifact(self)==self.artifact_pin)
        query=dict(bundleId=self.target['appId']);before=deepcopy(process_source(self.client.execute(self.session,'mobile: overteProcessSourceInfo',query)))
        actual=self.client.execute(self.session,'mobile: overteProcessInfo',query);after=deepcopy(process_source(self.client.execute(self.session,'mobile: overteProcessSourceInfo',query)))
        need(type(actual) is dict and set(actual)=={'bundleId','pid','foreground'} and actual['bundleId']==self.target['appId']
            and type(actual['pid']) is int and actual['pid']==int(self.binding['processIdentity']) and type(actual['foreground']) is bool
            and (foreground is None or actual['foreground']==foreground) and same(before,after) and same(after,self.os_scope['source'])
            and self.session_store.read()==self.session_state and IOSSnapshotCompanionRuntime.pin_artifact(self)==self.artifact_pin)
        return dict(binding=deepcopy(self.binding),process=deepcopy(actual),source=after)

    def foreground_runtime(self):
        self.probe(True)
        scope={key:value for key,value in self.binding.items() if key!='processIdentity'}
        runtime=IOSSnapshotCompanionRuntime(self.client,self.session_store,self.target,scope,self.artifact_path,
            lambda:self.probe(True) is not None,epoch_ms=self.epoch_ms,monotonic=self.monotonic,sleep=self.sleep)
        need(same(runtime.binding,self.binding) and same(runtime.initial,self.os_scope));return runtime

    def activate(self):
        self.probe(False);return self.client.execute(self.session,'mobile: activateApp',dict(bundleId=self.target['appId']))


def same_device(primary,companion):
    """Independently attest both retained SDKs against one private selector.

    Only its digest leaves this helper. The actual device selector and raw
    deviceInfo values must never enter public receipts or log output.
    """
    need(isinstance(primary,PhotosClientContext) and isinstance(companion,PhotosCompanionContext))
    first=primary.target.get('capabilities',{}).get('appium:udid');second=companion.target.get('capabilities',{}).get('appium:udid')
    need(type(first) is str and 8<=len(first)<=128 and all(32<ord(char)<127 for char in first) and first==second)
    primary.runtime.adapter.attest_physical_target(primary.client,primary.session,primary.target)
    primary.runtime.adapter.attest_physical_target(companion.client,companion.session,companion.target)
    primary.probe();companion.probe();return hashlib.sha256(first.encode()).hexdigest()
