"""OS-only Archive context over actual repository Node source and fake DVT."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.retired_process import absent
from ios.self_tests.snapshot_share_archive_end_domain import ArchiveEndDomain
from ios.self_tests.snapshot_share_domain import REAL_SLEEP,RUN


class SnapshotShareArchiveEndContextTests(unittest.TestCase):
    def test_actual_first_Archive_PID_remains_the_anchor_after_normal_stop(self):
        domain=ArchiveEndDomain(self)
        with domain.end_context() as context:
            self.assertEqual(85,context.live()['pid']);snapshot=deepcopy(context.snapshot);context.terminate()
            reader=context.process_reader();first=reader.read();self.assertTrue(absent(first));self.assertEqual(85,first['anchor']['pid'])
            next_value=reader.read();self.assertEqual(first['anchor'],next_value['anchor']);self.assertEqual(snapshot,context.snapshot)
        self.assertEqual(1,domain.stop_calls)
        with domain.end_context(snapshot) as context:self.assertTrue(absent(context.process_reader().read()))

    def test_closed_profile_has_real_Node_and_host_quiet_and_replays_original_records(self):
        domain=ArchiveEndDomain(self)
        with domain.end_context() as context:
            context.terminate();path=domain.root/filename('snapshotsharearchive','primary',0)
            owner=IOSProcessRetirement(PrivateFeatureState(path),context.process_reader(),domain.binding,RUN,'primary',0,domain.source_lock,profile='snapshotsharearchive')
            self.assertFalse(owner.advance());REAL_SLEEP(1.6);self.assertFalse(owner.advance());REAL_SLEEP(1.6);self.assertTrue(owner.advance())
            self.assertGreaterEqual(owner.state['windows'][-1]['elapsedMs'],3000);original=deepcopy(owner.previous)
            state=IOSProcessRetirement.archive(original,path=path,binding=domain.binding,source=context.source,bundle=domain.target['appId'],run=RUN,
                role='primary',stage=0,profile='snapshotsharearchive')
            self.assertEqual(owner.state,state);self.assertEqual(original,owner.previous)
        for role,stage in (('actor',0),('primary',1),('actor',1)):
            with self.subTest(role=role,stage=stage),self.assertRaises(NativeUIError):filename('snapshotsharearchive',role,stage)
        self.assertEqual('ios-graphics-actor-1-process-retirement.json',filename('graphics','actor',1))

    def test_new_live_PID_cannot_be_stopped_or_replace_the_original_85_anchor(self):
        domain=ArchiveEndDomain(self)
        with domain.end_context() as context:
            domain.node.call('parent-mode',value='replacement')
            with self.assertRaises(NativeUIError):context.terminate()
            with self.assertRaises(NativeUIError):context.process_reader().read()
        self.assertEqual(0,domain.stop_calls)

    def test_bundle_absence_with_original_PID_still_running_remains_unknown(self):
        domain=ArchiveEndDomain(self)
        with domain.end_context() as context:
            context.terminate();domain.node.call('parent-mode',value='held');reader=context.process_reader()
            packet=reader.read();self.assertFalse(absent(packet));self.assertTrue(all(row['running'] for row in packet['pidChecks']))
            self.assertEqual([0,0],packet['bundlePids'])

    def test_identical_byte_session_or_IPA_replacement_does_not_reanchor_context(self):
        for kind in ('session','artifact'):
            with self.subTest(kind=kind):
                domain=ArchiveEndDomain(self)
                with domain.end_context() as context:
                    path=domain.session.path if kind=='session' else domain.ipa;replacement=path.with_name('replacement')
                    replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
                    with self.assertRaises(NativeUIError):context.guard()
                    with self.assertRaises(NativeUIError):context.terminate()
                self.assertEqual(0,domain.stop_calls)

    def test_unreleased_actual_Node_socket_cannot_qualify_process_absence_or_SDK_release(self):
        domain=ArchiveEndDomain(self)
        with domain.end_context() as context:
            context.terminate();domain.node.call('hold-close')
            with self.assertRaises(NativeUIError):context.process_reader().read()
            info=domain.node.call('info');self.assertTrue(info['cleanupPending']);self.assertFalse(info['available'])
            with self.assertRaises(NativeUIError):domain.node.call('sdk-delete')


if __name__=='__main__':unittest.main()
