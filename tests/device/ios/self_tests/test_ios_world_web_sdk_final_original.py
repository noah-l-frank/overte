"""Actual SDK receipts: an ACK cannot replace the independent absent GET."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_session_end import WorldWebSessionEnd
from ios.self_tests import test_ios_world_web_session_end as fixture


class WorldWebSdkFinalOriginalTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.WorldWebSessionEndTests();self.case.setUp();self.addCleanup(self.case.doCleanups)

    def test_accepted_but_ignored_delete_remains_owned_without_replay(self):
        case=self.case;case.mode='ignored'
        with case.flow.held():
            with self.assertRaises(NativeUIError):case.owner().finish()
            self.assertEqual(1,case.count());self.assertTrue(case.live)
            self.assertIsNotNone(case.sdk_store.read());self.assertIsNotNone(case.actual.store.read())
            for _attempt in range(2):
                with self.assertRaises(NativeUIError):case.owner().finish()
            self.assertEqual(1,case.count())

    def test_complete_archive_reopens_actual_owned_originals_and_rejects_replaced_bytes(self):
        case=self.case
        with case.flow.held():
            owner=case.owner();owner.finish();requests=deepcopy(case.requests)
            decoded=WorldWebSessionEnd.archive(owner.previous,root=case.flow.root,binding=owner.binding,run=owner.run,role=owner.role)
            self.assertEqual(owner.state,decoded);self.assertEqual(requests,case.requests)
            reference=owner.state['original'];path=case.flow.root/('world-web-sdk-'+owner.run+'-'+owner.role+'-os-original-'+reference['sha256']+'.json')
            original=path.read_bytes();self.addCleanup(path.write_bytes,original)
            changed=json.loads(original);changed['commandId']='replaced-original-command';path.write_text(json.dumps(changed))
            # The unchanged reference is a digest of the decoded original;
            # changing a real original value must be rejected, not re-queried.
            with self.assertRaises(NativeUIError):
                WorldWebSessionEnd.archive(owner.previous,root=case.flow.root,binding=owner.binding,run=owner.run,role=owner.role)
            self.assertEqual(requests,case.requests)

    def test_mutating_live_completion_state_cannot_skip_actual_transport_or_originals(self):
        case=self.case
        with case.flow.held():
            owner=case.owner();owner.prepare();owner.state['phase']='complete';owner.state['observed404']=True
            with self.assertRaises(NativeUIError):owner.finish()
            self.assertEqual(0,case.count());self.assertTrue(case.live)


if __name__=='__main__':unittest.main()
