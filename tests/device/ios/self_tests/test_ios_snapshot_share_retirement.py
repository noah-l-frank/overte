"""Connected conditional Share cleanup; native/OS producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import decode
from ios.adapters.snapshot_share_owner import SnapshotSharePending
from ios.adapters import snapshot_share_retirement as source
from ios.self_tests.snapshot_share_domain import SnapshotShareDomain,REAL_MONOTONIC,REAL_SLEEP


class SnapshotShareRetirementTests(unittest.TestCase):
    def completed(self):
        d=SnapshotShareDomain(self);d.activate('share-open','1'*32)
        with d.owner() as owner:owner.open('1'*32)
        d.activate('share-select-owned','2'*32)
        with d.owner() as owner:owner.select('2'*32)
        return d

    def test_original_PID_and_native_file_windows_retire_only_the_two_anchored_runs(self):
        d=self.completed();began=REAL_MONOTONIC()
        with d.owner() as owner:
            proof=owner.cleanup();self.assertTrue(proof['wholeFeatureRequired']);self.assertTrue(proof['sourceJournalRetirementRequired'])
            self.assertGreaterEqual(proof['extensionBefore']['hostMilliseconds'],3000)
            self.assertGreaterEqual(proof['extensionAfter']['nodeMilliseconds'],3000)
            self.assertGreaterEqual(proof['fileQuiet']['nativeMilliseconds'],3000);self.assertGreaterEqual(proof['fileQuiet']['hostMilliseconds'],3000)
            state=owner.state['cleanup'];row=state['after'][-1];actual=decode(owner.archive_source(row['source']).decode('utf-8'))
            args=(row['nonce'],state['retireNonce'],d.archive.imported,owner.archive_source(owner.state['metadata']),
                owner.archive_source(owner.state['imported']),owner.archive_source(state['intent']))
            for fault in ('pid','root','nonce','metadata','steps','boolean-version'):
                changed=deepcopy(actual)
                if fault=='pid':changed['processId']=True
                elif fault=='root':changed['retirement']['groupRootIdentity']='0'*64
                elif fault=='nonce':changed['requestId']='ios-'+'0'*32
                elif fault=='metadata':changed['retirement']['files'][1]['sha256']='0'*64
                elif fault=='steps':changed['retirement']['steps'][-1]['succeeded']=False
                else:changed['snapshotShareRetirementObservationVersion']=True
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.observation(changed,*args,receiver_bundle_id=d.archive.target['appId']+'.receiver')
            changed=deepcopy(actual);changed['archiveRunAbsent']=False
            with self.assertRaises(NativeUIError):source.qualified(changed)
        self.assertGreaterEqual(REAL_MONOTONIC()-began,6.4)
        self.assertFalse(d.archive.group_run.exists());self.assertFalse(d.archive.archive_run.exists());self.assertTrue(d.main.f.f.h.path.exists())
        self.assertEqual(1,d.archive.retire_count);self.assertTrue(d.main_foreground);self.assertFalse(d.archive.foreground)
        with d.owner() as owner:self.assertEqual(proof,owner.cleanup())
        self.assertEqual(1,d.archive.retire_count)

    def test_lost_retire_return_adopts_actual_receipt_without_a_second_delete_input(self):
        d=self.completed();d.lost_buttons.add('snapshot.share.archive.retire')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertFalse(d.archive.group_run.exists())
        with d.owner() as owner:self.assertTrue(owner.cleanup()['hostOriginalRetained'])
        self.assertEqual(1,d.archive.retire_count);self.assertEqual(1,d.archive.ui.clicks.count('snapshot.share.archive.retire'))

    def test_lost_inspection_return_keeps_original_query_and_never_resends_it(self):
        d=self.completed();d.lost_buttons.add('snapshot.share.archive.retire-inspect')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        original=deepcopy(d.archive.retirement)
        with d.owner() as owner:self.assertTrue(owner.cleanup()['hostOriginalRetained'])
        self.assertEqual(original,d.archive.retirement);self.assertEqual(3,d.archive.ui.clicks.count('snapshot.share.archive.retire-inspect'))
        self.assertEqual(1,d.archive.retire_count)

    def test_same_byte_file_replacement_refuses_all_unlinks_and_remains_owned(self):
        d=self.completed();original=d.archive.archive_run/'original.bytes';replacement=original.with_name('replacement')
        replacement.write_bytes(original.read_bytes());replacement.chmod(0o600);replacement.replace(original)
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(SnapshotSharePending):owner.cleanup()
        self.assertEqual(1,d.archive.retire_count);self.assertTrue(original.exists());self.assertTrue(d.archive.group_run.exists())
        self.assertEqual([],d.archive.retirement['steps']);self.assertFalse(d.archive.retirement['complete'])

    def test_partial_native_deletion_never_repeats_or_claims_the_remaining_responsibility(self):
        d=self.completed();d.archive.retirement_fail_after=1
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(SnapshotSharePending):owner.cleanup()
        self.assertEqual(1,d.archive.retire_count);self.assertEqual(1,len(d.archive.retirement['steps']))
        self.assertFalse((d.archive.group_run/'original.bytes').exists());self.assertTrue((d.archive.group_run/'share-original.json').exists())
        self.assertTrue(d.archive.archive_run.exists());self.assertFalse(d.archive.retirement['complete'])

    def test_original_numeric_PID_still_running_blocks_before_any_native_retirement(self):
        d=self.completed();d.archive.node.call('mode',value='live')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertEqual(0,d.archive.retire_count);self.assertTrue(d.archive.group_run.exists());self.assertTrue(d.archive.archive_run.exists())

    def test_late_lost_inspection_keeps_historical_source_without_retiming_or_resending(self):
        d=self.completed();d.lost_buttons.add('snapshot.share.archive.retire-inspect')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        REAL_SLEEP(5.6)
        with d.owner() as owner,self.assertRaises(SnapshotSharePending):owner.cleanup()
        with d.owner() as owner:
            first=owner.state['cleanup']['after'][0];self.assertIs(first['qualified'],False);self.assertIsNotNone(first['source'])
            retained=owner.archive_source(first['source']);ref=deepcopy(owner.state['archiveSources'][first['source']-1])
            self.assertTrue(owner.cleanup()['hostOriginalRetained'])
        with d.owner() as owner:
            self.assertEqual(retained,owner.archive_source(first['source']));self.assertEqual(ref,owner.state['archiveSources'][first['source']-1])
        self.assertEqual(4,d.archive.ui.clicks.count('snapshot.share.archive.retire-inspect'));self.assertEqual(1,d.archive.retire_count)

    def test_expired_before_delete_window_adds_fresh_originals_without_retiming_the_first_group(self):
        d=self.completed()
        with d.owner() as owner:
            actual=owner.acted
            def before_delete(label,*args,**kwargs):
                if label=='archive-retire':raise NativeUIError('Declared stop before any retirement input slot')
                return actual(label,*args,**kwargs)
            with patch.object(owner,'acted',before_delete),self.assertRaises(NativeUIError):owner.cleanup()
            original_group=deepcopy(owner.state['cleanup']['groups'][0]);original_packets=[deepcopy(owner.queries.query_original(index)) for index in original_group]
        self.assertEqual(0,d.archive.retire_count);REAL_SLEEP(3.1)
        with d.owner() as owner:
            owner.cleanup();self.assertEqual(2,len(owner.state['cleanup']['groups']));self.assertEqual(original_group,owner.state['cleanup']['groups'][0])
            self.assertEqual(original_packets,[owner.queries.query_original(index) for index in original_group])
        self.assertEqual(1,d.archive.retire_count)

    def test_unexpected_child_prevents_recursive_or_partial_cleanup_of_the_original_roots(self):
        d=self.completed();foreign=d.archive.group_run/'foreign.bytes';foreign.write_bytes(b'Unowned original');foreign.chmod(0o600)
        with d.owner() as owner,self.assertRaises(SnapshotSharePending):owner.cleanup()
        self.assertEqual(b'Unowned original',foreign.read_bytes());self.assertTrue((d.archive.group_run/'original.bytes').exists())
        self.assertTrue((d.archive.archive_run/'original.bytes').exists());self.assertEqual([],d.archive.retirement['steps'])


if __name__=='__main__':unittest.main()
