"""Closed Share archive admission over actual selected/installed app forests."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_companion_artifact import share_artifact
from ios.adapters.snapshot_companion_owner import IOSSnapshotCompanionOwner
from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime
from ios.adapters import snapshot_share_admission_source as source


class IOSSnapshotShareAdmissionOwner(IOSSnapshotCompanionOwner):
    _namespace='ios-snapshot-share-code'
    _schema='iosSnapshotShareCode'
    _owner_key='iosSnapshotShareCodeOwnerVersion'
    _frame_key='snapshotShareCompanionFrameVersion'
    _control_prefix='snapshot.share.companion'
    _source=source
    _artifact_reader=staticmethod(share_artifact)
    _artifact_role='share-archive'
    def result(self):
        result=super().result()
        return dict(result,embeddedExtension=deepcopy(self.artifact['extension']),embeddedExtensionCodeVerified=True)


class IOSSnapshotShareAdmissionRuntime(IOSSnapshotCompanionRuntime):
    _artifact_reader=staticmethod(share_artifact)
    def original(self,action):
        need(action in ('identity','clock'));self.check()
        remote='@'+self.target['appId']+':documents/snapshot-share-companion-'+action+'.json'
        encoded=self.client.execute(self.session,'mobile: pullFile',dict(remotePath=remote))
        need(type(encoded) is str and len(encoded)<=349528);raw=base64.b64decode(encoded,validate=True);need(1<=len(raw)<=262144)
        self.check();return raw
    def original_path(self,_name,_limit):need(False)
    @contextmanager
    def owner(self,run,client):
        lock=ScriptSourceLock(self.session_state.path.with_name('script-feature-sources.lock'));failure=None
        with lock.held():
            try:
                self.check();owner=IOSSnapshotShareAdmissionOwner(self,lock,run,
                    PhaseFixtureReader(client,run,'snapshots',epoch_ms=self.epoch_ms,monotonic=self.monotonic))
                yield owner;self.check()
            except BaseException as original:failure=original
        if failure is not None:raise failure
