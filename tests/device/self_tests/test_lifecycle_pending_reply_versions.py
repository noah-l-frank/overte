"""Original Pending reply admission and unchanged existing V1 continuation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_pending as pending
from adapters.pico4.lifecycle_back import frame
from adapters.script_journey.history import unpack
from self_tests import test_pico_lifecycle_pending as original
from self_tests.test_pending_commit_owner import Boundary,RUN


class LifecyclePendingReplyVersionTests(unittest.TestCase):
    def test_v2_reply_original_survives_cold_decode_without_a_new_source_query(self):
        fixture=original.LifecyclePendingTests();self.addCleanup(fixture.doCleanups);fixture.setUp()
        fixture.owner.back();fixture.owner.open_scripts();fixture.owner.mutate('focus')
        before=fixture.owner.store.path.read_bytes();calls=deepcopy(fixture.boundary.commands)
        reply=deepcopy(fixture.owner.state['replies'][0])
        cold=fixture.make()
        self.assertEqual(2,cold.version);self.assertEqual(reply,cold.state['replies'][0])
        self.assertEqual(before,cold.store.path.read_bytes());self.assertEqual(calls,fixture.boundary.commands)
        self.assertEqual('focus',cold.reply_packet(reply,cold.state['mutations'][0])['operation'])

    def test_original_v1_owner_continues_cold_with_v2_code_without_reply_or_writer_migration(self):
        fixture=original.LifecyclePendingTests()
        self.addCleanup(fixture.doCleanups)
        with patch.object(pending,'VERSION',1):fixture.setUp()
        first=fixture.owner.store.path.read_bytes()
        self.assertEqual(1,fixture.owner.version)
        self.assertNotIn('replies',fixture.owner.state)
        fixture.owner=fixture.make()
        self.assertEqual(first,fixture.owner.store.path.read_bytes())
        result=pending.run_pending(fixture.owner)
        self.assertEqual(1,fixture.owner.version)
        self.assertEqual('quiet',fixture.owner.state['phase'])
        self.assertFalse(result['completeLifecycle'])
        self.assertNotIn('replies',fixture.owner.state)
        self.assertNotIn('replies',unpack(fixture.owner.store.read()['payload'])[0])
        self.assertEqual(['focus','type','hold','attempt','release'],
            [row['operation'] for row in fixture.boundary.commands if row['operation']!='observe'])

    def test_full_reply_original_request_time_and_strict_types_are_required_without_source_calls(self):
        boundary=Boundary();reader=boundary.owner();reader.read(RUN);reader.operate(RUN,'focus')
        owner=object.__new__(pending.PicoLifecyclePending);owner.run=RUN;owner.pid=123
        started,requested,completed,epoch=reader.last_received
        request=deepcopy(reader.last_request)
        row=dict(request=request,original=frame(reader.last_raw),exchangeTiming=dict(
            startedHost=started,requestedEpochMs=requested,completedHost=completed,completedEpochMs=epoch))
        self.assertEqual(reader.last,owner.reply_packet(row,request))
        calls=len(boundary.commands)
        faults=(lambda value:value['request'].update(intentSequence=True),
            lambda value:value['exchangeTiming'].update(startedHost=False),
            lambda value:value['exchangeTiming'].update(completedEpochMs=epoch+2000),
            lambda value:value['exchangeTiming'].update(completedHost=completed+2),
            lambda value:value['original'].update(raw=value['original']['raw']+' '),
            lambda value:value['request'].update(commandId='c'*32))
        for fault in faults:
            changed=deepcopy(row);fault(changed)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.reply_packet(changed,request)
        self.assertEqual(calls,len(boundary.commands))
        # Inspection copies never replace the literal native reply retained by
        # the already completed exchange.
        row['original']['raw']='{}';self.assertEqual(reader.last,json.loads(reader.last_raw))


if __name__=='__main__':unittest.main()
