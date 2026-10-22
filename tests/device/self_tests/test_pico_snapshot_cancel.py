"""Closed bounded Capture/Cancel admission, not a Snapshot feature verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4.snapshot_cancel import PicoSnapshotCancel,command
from adapters.normal_ui import NativeUIError


class SnapshotCancelTests(unittest.TestCase):
    def test_closed_commands_never_accept_requested_capture_or_work_effects(self):
        value=PicoSnapshotCancel.envelope('a'*32,'b'*32,'observe');command(value)
        for field,item in (('expectedCancelled',True),('closedReadWorkRequestId',True),('operation','cancel'),
                ('runId','foreign'),('schemaVersion',True),('request',{'performed':True})):
            broken=deepcopy(value);broken[field]=item
            with self.subTest(field=field),self.assertRaises(NativeUIError):command(broken)
    def test_start_requires_the_actual_original_pico_capture_control_command(self):
        request=dict(schemaVersion=1,commandId=str(uuid.uuid4()),action='activate',controlId='snapshot.capture',
            controlToken=str(uuid.uuid4()),bridgeId=str(uuid.uuid4()),generation=str(uuid.uuid4()),sequence=1,observedElapsedMs=0)
        value=PicoSnapshotCancel.envelope('a'*32,'b'*32,'start',request);command(value)
        for field,item in (('controlId','snapshot.cancel'),('schemaVersion',True),('sequence',True),
                ('observedElapsedMs',-1),('commandId','a'*32),('expectedName','owned')):
            broken=deepcopy(value);broken['request'][field]=item
            with self.subTest(field=field),self.assertRaises(NativeUIError):command(broken)
        value['closedReadWorkRequestId']='c'*32
        with self.assertRaises(NativeUIError):command(value)
    def test_original_completed_script_work_is_selected_only_by_nonce_not_supplied_facts(self):
        value=PicoSnapshotCancel.envelope('a'*32,'b'*32,'retire',closed_read_work_request_id='c'*32);command(value)
        value['closedReadWorkRequestId']={'complete':True,'timers':[]}
        with self.assertRaises(NativeUIError):command(value)


if __name__=='__main__':unittest.main()
