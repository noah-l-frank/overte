"""Existing Archive SDK after first-PID Stop; no foreground/native source read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from ios.adapters.installed_code import source as process_source
from ios.adapters.retired_process import IOSRetiredProcess
from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionOwner


class SnapshotShareArchiveEndContext:
    def __init__(self,client,session_store,target,binding,artifact_path,admission_store,lock,run,fixture_url,
            *,epoch_ms,monotonic,snapshot=None,historical=False):
        need(isinstance(session_store,PrivateFeatureState) and isinstance(admission_store,PrivateFeatureState));lock.assert_held()
        self.client,self.session_store,self.target,self.binding=client,session_store,deepcopy(target),deepcopy(context(binding))
        self.lock,self.artifact_path,self.run,self.fixture_url,self.historical=lock,Path(artifact_path),run,fixture_url,historical
        self.admission=IOSSnapshotShareAdmissionOwner.archive(admission_store,lock,binding,run,fixture_url,artifact_path);self.admission.result()
        self.source=deepcopy(process_source(self.admission.os_scope['source']));self.session=binding['sessionId'];self.pid=int(binding['processIdentity'])
        need(target.get('platform')=='ios' and target.get('physical') is True and target.get('appId')==self.admission.artifact['bundle']['bundleId']
            and digest(target)==binding['targetFingerprint'] and type(historical) is bool
            and (historical or callable(getattr(client,'call',None)) and callable(getattr(client,'execute',None))))
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        if snapshot is None:
            self.snapshot=dict(sdkState=session_store.read(),sdkPin=self.pin(session_store.path),artifactPin=self.pin(self.artifact_path))
        else:self.snapshot=deepcopy(snapshot)
        exact(self.snapshot,{'sdkState','sdkPin','artifactPin'});state=self.snapshot['sdkState']
        need(type(state) is dict and state.get('sessionId')==self.session and type(state.get('generation')) is int and state['generation']==binding['generation']
            and state.get('targetFingerprint')==binding['targetFingerprint'])
        for name in ('sdkPin','artifactPin'):
            pin=self.snapshot[name];need(type(pin) is list and len(pin)==8 and all(type(item) is int for item in pin))
        self.local(allow_absent=True)
    @staticmethod
    def pin(path):return list(IOSSnapshotCompanionRuntime.pin_artifact(SimpleNamespace(artifact_path=Path(path))))
    def local(self,*,allow_absent=False):
        self.lock.assert_held();self.admission.bound();need(self.pin(self.artifact_path)==self.snapshot['artifactPin']
            and digest(self.target)==self.binding['targetFingerprint'])
        state=self.session_store.read()
        if state is None:need(allow_absent)
        else:need(same(state,self.snapshot['sdkState']) and self.pin(self.session_store.path)==self.snapshot['sdkPin'])
        return True
    def sdk(self):
        need(not self.historical);self.local();value=self.client.call('GET','/session/'+self.session)
        need(type(value) is dict and type(value.get('capabilities')) is dict and value['capabilities'].get('appium:bundleId')==self.target['appId'])
        self.local();return value
    def guard(self):
        self.sdk();actual=process_source(self.client.execute(self.session,'mobile: overteProcessSourceInfo',dict(bundleId=self.target['appId'])))
        need(same(actual,self.source));self.local();return True
    def live(self):
        self.guard();value=self.client.execute(self.session,'mobile: overteProcessInfo',dict(bundleId=self.target['appId']))
        exact(value,{'bundleId','pid','foreground'});need(value['bundleId']==self.target['appId'] and type(value['pid']) is int and value['pid']==self.pid
            and type(value['foreground']) is bool);self.guard();return deepcopy(value)
    def terminate(self):
        self.live();return self.client.execute(self.session,'mobile: terminateApp',dict(bundleId=self.target['appId']))
    def process_reader(self):
        need(not self.historical)
        return IOSRetiredProcess(lambda query:self.client.execute(self.session,'mobile: overteRetiredProcessInfo',query),self.guard,
            self.target['appId'],self.pid,self.source,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
