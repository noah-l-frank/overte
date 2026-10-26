"""Closed actual AFC originals from the independently admitted Share archive."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionOwner,IOSSnapshotShareAdmissionRuntime


class IOSSnapshotShareArchiveRuntime(IOSSnapshotShareAdmissionRuntime):
    def __init__(self,*args,admission_store,lock,run,fixture_url,**kwargs):
        super().__init__(*args,**kwargs)
        need(isinstance(admission_store,PrivateFeatureState) and lock.path==self.session_state.path.with_name('script-feature-sources.lock'))
        lock.assert_held();self.archive_admission=IOSSnapshotShareAdmissionOwner.archive(admission_store,lock,self.binding,run,fixture_url,self.artifact_path)
        self.archive_admission.result();need(same(self.archive_admission.os_scope,self.initial));self.check()
    def check(self):
        super().check();self.archive_admission.bound();return True
    def original_path(self,name,limit):
        names={'snapshot-share-chunk.json'}|{'snapshot-share-'+self.archive_admission.run+'/'+kind+'.json' for kind in ('import-original','original-extension')}
        need(type(name) is str and name in names
            and type(limit) is int and 1<=limit<=(720896 if name=='snapshot-share-chunk.json' else 262144))
        self.check();encoded=self.client.execute(self.session,'mobile: pullFile',dict(remotePath='@'+self.target['appId']+':documents/'+name))
        need(type(encoded) is str and len(encoded)<=4*((limit+2)//3));raw=base64.b64decode(encoded,validate=True)
        need(1<=len(raw)<=limit);self.check();return raw
