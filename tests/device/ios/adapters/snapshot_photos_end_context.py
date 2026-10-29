"""Original Photos-helper scope for Stop/OS quiet and SDK-only retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import stat
from types import SimpleNamespace
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from ios.adapters.installed_code import source as process_source
from ios.adapters.retired_process import IOSRetiredProcess
from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime
from ios.adapters.snapshot_companion_owner import IOSSnapshotCompanionOwner


class SnapshotPhotosEndContext:
    def __init__(self,client,session_store,target,binding,artifact_path,admission_store,lock,run,fixture_url,
            *,epoch_ms,monotonic,snapshot=None,historical=False):
        need(type(historical) is bool and isinstance(session_store,PrivateFeatureState) and isinstance(admission_store,PrivateFeatureState)
            and all(callable(fn) for fn in (epoch_ms,monotonic)));lock.assert_held()
        self.client,self.session_store,self.target,self.binding=client,session_store,deepcopy(target),deepcopy(context(binding))
        self.lock,self.artifact_path,self.run,self.fixture_url,self.historical=lock,Path(artifact_path),run,fixture_url,historical
        self.admission=IOSSnapshotCompanionOwner.archive(admission_store,lock,binding,run,fixture_url,artifact_path);self.admission.result()
        self.source=deepcopy(process_source(self.admission.os_scope['source']));self.session=binding['sessionId'];self.pid=int(binding['processIdentity'])
        need(target.get('platform')=='ios' and target.get('physical') is True and target.get('appId')==self.admission.artifact['bundle']['bundleId']
            and digest(target)==binding['targetFingerprint'] and (historical or callable(getattr(client,'call',None)) and callable(getattr(client,'execute',None))))
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        if snapshot is None:
            need(not historical);state=session_store.read();sdk_pin=self.pin(session_store.path)
            slot=dict(snapshotPhotosSDKSlotVersion=1,path=str(session_store.path),parentPath=str(session_store.path.parent),parentIdentity=self.parent_pin(),
                binding=deepcopy(self.binding),runId=self.run,fixtureUrl=self.fixture_url,admissionOwnerSha256=digest(self.admission.previous),source=deepcopy(self.source),
                sdkStateSha256=digest(state),originalSDKStat=deepcopy(sdk_pin),artifactPath=str(self.artifact_path),artifactSha256=self.binding['artifactSha256'])
            self.snapshot=dict(snapshotPhotosEndSnapshotVersion=2,sdkState=state,sdkPin=sdk_pin,artifactPin=self.pin(self.artifact_path),sdkSlot=slot)
        else:self.snapshot=deepcopy(snapshot)
        self.validate_snapshot()
        self.local(allow_absent=True)
    def validate_snapshot(self):
        exact(self.snapshot,{'snapshotPhotosEndSnapshotVersion','sdkState','sdkPin','artifactPin','sdkSlot'});need(type(self.snapshot['snapshotPhotosEndSnapshotVersion']) is int and self.snapshot['snapshotPhotosEndSnapshotVersion']==2)
        state=self.snapshot['sdkState']
        need(type(state) is dict and state.get('sessionId')==self.session and type(state.get('generation')) is int and state['generation']==self.binding['generation']
            and state.get('targetFingerprint')==self.binding['targetFingerprint'])
        for key in ('sdkPin','artifactPin'):need(type(self.snapshot[key]) is list and len(self.snapshot[key])==8 and all(type(item) is int for item in self.snapshot[key]))
        slot=self.snapshot['sdkSlot'];exact(slot,{'snapshotPhotosSDKSlotVersion','path','parentPath','parentIdentity','binding','runId','fixtureUrl','admissionOwnerSha256','source','sdkStateSha256','originalSDKStat','artifactPath','artifactSha256'})
        need(type(slot['snapshotPhotosSDKSlotVersion']) is int and slot['snapshotPhotosSDKSlotVersion']==1
            and slot['path']==str(self.session_store.path) and slot['parentPath']==str(self.session_store.path.parent)
            and same(slot['binding'],self.binding) and slot['runId']==self.run and slot['fixtureUrl']==self.fixture_url
            and slot['admissionOwnerSha256']==digest(self.admission.previous) and same(slot['source'],self.source)
            and slot['sdkStateSha256']==digest(state) and same(slot['originalSDKStat'],self.snapshot['sdkPin'])
            and slot['artifactPath']==str(self.artifact_path) and slot['artifactSha256']==self.binding['artifactSha256'])
        return True
    def parent_pin(self):
        self.session_store._parent();row=self.session_store.path.parent.lstat();need(stat.S_ISDIR(row.st_mode))
        return [row.st_dev,row.st_ino,row.st_mode,row.st_uid,row.st_gid,row.st_nlink]
    @staticmethod
    def pin(path):return list(IOSSnapshotCompanionRuntime.pin_artifact(SimpleNamespace(artifact_path=Path(path))))
    def local(self,*,allow_absent=False):
        self.validate_snapshot();self.lock.assert_held();self.admission.bound();need(self.snapshot['sdkSlot']['path']==str(self.session_store.path)
            and self.snapshot['sdkSlot']['parentPath']==str(self.session_store.path.parent) and same(self.snapshot['sdkSlot']['parentIdentity'],self.parent_pin())
            and self.pin(self.artifact_path)==self.snapshot['artifactPin']
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
