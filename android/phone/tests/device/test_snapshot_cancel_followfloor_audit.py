"""Independent complete-current continuity over an actual closed Qt DTO.

The original Qt helper/gateway/QML run in an isolated host component build.
Subsequent transport acquisitions and later native capture rows are explicit
synthetic seams; all historical recipe/caller/work originals remain unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
import subprocess
import unittest

import test_snapshot_native_controls as native
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_cancel import PhoneSnapshotCancel,validate


class SnapshotCancelFollowfloorAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):native.SnapshotNativeControlsTests.setUpClass.__func__(cls)

    def original(self):
        raw=subprocess.check_output([str(self.executable),str(self.stage),'fast-closed','--testScript'],text=True,timeout=15,
            env=os.environ|{'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','XDG_CONFIG_HOME':str(self.stage/'audit-config')})
        return json.loads(next(line[7:] for line in raw.splitlines() if line.startswith('CLOSED:')))

    def test_independent_follow_current_floor_rejects_loss_of_later_original_native_history(self):
        original=self.original();epoch=original['capturedEpochMs'];current=deepcopy(original['source']['current'])
        path=current['native']['storageRoot']+'/after-cancel.png'
        history=current['native']['history'];self.assertEqual([],history['events'])
        for kind,phase,target in (('capture-begin','',''),('capture-status','complete',path)):
            history['events'].append(dict(sequence=len(history['events'])+1,kind=kind,id='independent_later_capture',phase=phase,path=target,
                error='',capturedEpochMs=current['capturedEpochMs'],elapsedMs=0))
        history['sequence']=len(history['events']);requests=[];sequence=[0];row=[current]
        def send(request):
            requests.append(deepcopy(request));sequence[0]+=1
            packet=deepcopy(original);packet.update(requestId=request['commandId'],sequence=sequence[0],requestedEpochMs=epoch,capturedEpochMs=epoch)
            packet['source']['current']=deepcopy(row[0]);packet['source']['current']['capturedEpochMs']=epoch
            packet['source']['observedEpochMs']=epoch
            # Only this explicitly synthetic new acquisition envelope advances.
            # Historical before/pending/cancelled/retirement/caller/work events
            # retain every original native timestamp and byte unchanged.
            out[0]=json.dumps(packet)
        out=[''];reader=PhoneSnapshotCancel(send,lambda:out[0],lambda:epoch,lambda:True,original['processId'])
        job=original['source']['job'];run=original['runId'];nonce=current['scriptWork']['requestId']
        result=reader.request(run,job,'observe',closed_read_work_request_id=nonce)
        self.assertEqual(history,result['source']['current']['native']['history'])
        self.assertEqual(original['source']['cancelled'],result['source']['cancelled'])
        # This is still a valid single envelope and still includes the entire
        # retired recipe prefix. Only the previously acquired current floor
        # reveals that the later original capture has disappeared.
        row[0]=deepcopy(original['source']['current'])
        with self.assertRaises(NativeUIError):reader.request(run,job,'observe',closed_read_work_request_id=nonce)
        self.assertEqual(['observe','observe'],[request['operation'] for request in requests])

    def test_independent_closed_current_work_and_full_history_are_not_replaced_by_retirement_ack(self):
        original=self.original();request=dict(schemaVersion=1,commandId=original['requestId'],action='phone-snapshot-cancel',
            runId=original['runId'],jobId=original['source']['job'],operation='retire',request={},
            closedReadWorkRequestId=original['source']['current']['scriptWork']['requestId'])
        validate(original,request,original['processId'],original['capturedEpochMs'])
        for frame in ('current','retirement'):
            for stream in ('history','scriptHistory'):
                changed=deepcopy(original);changed['source'][frame]['native'][stream]['instance']='0'*32
                with self.subTest(frame=frame,stream=stream),self.assertRaises((ValueError,RuntimeError)):
                    validate(changed,request,original['processId'],original['capturedEpochMs'])


if __name__=='__main__':unittest.main()
