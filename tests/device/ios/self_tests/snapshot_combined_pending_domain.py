"""Normal Pending/Cancel boundary with its original combined work producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from ios.adapters import snapshot_combined_work as work
from ios.self_tests.snapshot_combined_work_fixture import packet
from ios.self_tests.snapshot_combined_upload_domain import CombinedUploadDomain
from ios.self_tests.snapshot_pending_domain import SnapshotPendingDomain,RUN,BASE,REAL_TIME,REAL_MONOTONIC


class CombinedPendingDomain(SnapshotPendingDomain):
    def __init__(self,case):
        super().__init__(case);self.work_template=packet(BASE)
        self.script_events=deepcopy(self.work_template['source']['workers'][0]['events'])

    def event(self,event,closure,call):
        row=super().event(event,closure,call);row['callerStackId']='c'*32;return row

    # Both declared boundaries use the same closed original work sampler;
    # this function touches only their common Script/timer producer fields.
    work_packet=CombinedUploadDomain.work_packet

    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!=work.ACTION:return super().post(request,timeout)
        self.commands.append(deepcopy(query));self.raws[work.FILE]=json.dumps(self.work_packet(query),indent=1)+'\n'
        self.ctx.files.echo=json.dumps(query).encode();return self.ctx.files

    def owner(self,*,combined=True):
        return self.runtime.pending_owner('primary',RUN,self.client(),combined=combined,
            epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
