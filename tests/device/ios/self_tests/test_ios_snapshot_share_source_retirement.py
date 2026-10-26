"""Real named source unlink/quiet; UIKit/native/OS producers are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_source_retirement_owner import SnapshotShareSourceRetirementOwner
from ios.adapters import snapshot_share_source_retirement as source
from ios.self_tests.snapshot_share_source_retirement_domain import SourceRetirementFlow
from ios.self_tests.snapshot_share_domain import RUN,SYSTEM_UI,REAL_MONOTONIC,REAL_SLEEP


class SnapshotShareSourceRetirementTests(unittest.TestCase):
    def prepared(self):
        domain=SourceRetirementFlow(self);domain.activate('share-open','1'*32)
        with domain.owner() as share:share.open('1'*32)
        domain.activate('share-select-owned','2'*32)
        with domain.owner() as share:
            share.select('2'*32);share.cleanup();share.admission_seal_owner().seal();share.source_inventory_owner().inspect()
        return domain
    def history(self,domain):
        share=IOSSnapshotShareOwner.history(PrivateFeatureState(domain.main.ctx.root/'snapshot-share-owner.json'),domain.main.ctx.lock,
            domain.archive.source_lock,domain.main.ctx.binding,domain.archive.binding,RUN,domain.archive.fixture_url,SYSTEM_UI,
            domain.primary.target['appId'],domain.archive.ipa,domain.archive.admission_store)
        return SnapshotShareSourceRetirementOwner.history(PrivateFeatureState(domain.archive.root/'share-source-retirement-owner.json'),share,
            domain.archive.ipa,domain.archive.admission_store)

    def test_exact_seven_unlinks_and_three_native_Node_host_windows_retire_sources_only(self):
        domain=self.prepared();foreign=domain.archive.documents/'unrelated.bytes';foreign.write_bytes(b'Unrelated owned data');foreign.chmod(0o600);began=REAL_MONOTONIC()
        with domain.owner() as share:
            owner=share.source_retirement_owner();proof=owner.cleanup();record,raw=owner.retired()
            self.assertTrue(proof['sourceFilesRetired']);self.assertTrue(proof['archiveProcessRetirementRequired']);self.assertTrue(proof['sourceSDKRetirementRequired'])
            self.assertGreaterEqual(proof['extensionBefore']['hostMilliseconds'],3000);self.assertGreaterEqual(proof['extensionAfter']['nodeMilliseconds'],3000)
            self.assertGreaterEqual(proof['fileQuiet']['nativeMilliseconds'],3000);self.assertGreaterEqual(proof['fileQuiet']['hostMilliseconds'],3000)
            for fault in ('pid','version','inventory','intent','step','closed','name'):
                changed=deepcopy(record)
                if fault=='pid':changed['processId']=True
                elif fault=='version':changed['snapshotShareSourceRetirementVersion']=True
                elif fault=='inventory':changed['inventorySha256']='0'*64
                elif fault=='intent':changed['intent']['sha256']='0'*64
                elif fault=='step':changed['steps'][0]['synchronized']=False
                elif fault=='closed':changed['parentDescriptorClosed']=False
                else:changed['outputs'][0]['name']='unrelated.bytes'
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.qualified(source.original(changed,owner.state['nonce'],owner.inventory))
            self.assertEqual(raw,owner.retired()[1]);self.assertEqual(proof,owner.cleanup())
        self.assertGreaterEqual(REAL_MONOTONIC()-began,6.4);self.assertEqual(list(source.ALL_NAMES),domain.archive.source_unlinks)
        self.assertEqual(1,domain.archive.source_retire_calls);self.assertTrue(all(not (domain.archive.documents/name).exists() for name in source.ALL_NAMES))
        self.assertEqual(b'Unrelated owned data',foreign.read_bytes());self.assertTrue(domain.main.f.f.h.path.exists())
        with domain.main.ctx.lock.held(),domain.archive.source_lock.held():
            reader=self.history(domain);self.assertEqual(proof,reader.proof());self.assertEqual(raw,reader.retired()[1])

    def test_lost_retire_return_retains_original_effect_before_any_new_query_and_never_unlinks_twice(self):
        domain=self.prepared();domain.lost_buttons.add('snapshot.share.archive.source-retire')
        with domain.owner() as share,self.assertRaises(NativeUIError):share.source_retirement_owner().cleanup()
        original=domain.archive.source_retire_text;self.assertEqual(list(source.ALL_NAMES),domain.archive.source_unlinks)
        with domain.owner() as share:self.assertTrue(share.source_retirement_owner().cleanup()['sourceFilesRetired'])
        self.assertEqual(original,domain.archive.source_retire_text);self.assertEqual(1,domain.archive.source_retire_calls)

    def test_partial_actual_unlink_and_unknown_sync_remain_owned_without_any_repeat(self):
        domain=self.prepared();domain.archive.source_sync_unknown_at=1
        for _ in range(2):
            with domain.owner() as share,self.assertRaises(NativeUIError):share.source_retirement_owner().cleanup()
        self.assertEqual([source.NAMES[0]],domain.archive.source_unlinks);self.assertEqual(1,domain.archive.source_retire_calls)
        self.assertFalse((domain.archive.documents/source.NAMES[0]).exists());self.assertTrue((domain.archive.documents/source.INTENT).exists())
        with domain.main.ctx.lock.held(),domain.archive.source_lock.held():
            owner=self.history(domain);self.assertFalse(owner.retired()[0]['complete']);self.assertIsNone(owner.state['result'])

    def test_same_byte_replaced_source_blocks_every_unlink_and_does_not_reanchor(self):
        domain=self.prepared();path=domain.archive.documents/source.NAMES[2];replacement=path.with_name('replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path);fact=(path.stat().st_ino,path.read_bytes())
        for _ in range(2):
            with domain.owner() as share,self.assertRaises(NativeUIError):share.source_retirement_owner().cleanup()
        self.assertEqual([],domain.archive.source_unlinks);self.assertEqual(1,domain.archive.source_retire_calls)
        self.assertEqual(fact,(path.stat().st_ino,path.read_bytes()));self.assertFalse((domain.archive.documents/source.INTENT).exists())

    def test_first_receiver_PID_still_running_blocks_before_any_source_retirement_input(self):
        domain=self.prepared();domain.archive.node.call('mode',value='live')
        with domain.owner() as share,self.assertRaises(NativeUIError):share.source_retirement_owner().cleanup()
        self.assertEqual(0,domain.archive.source_retire_calls);self.assertEqual([],domain.archive.source_unlinks)
        self.assertTrue(all((domain.archive.documents/name).exists() for name in source.NAMES))

    def test_late_lost_inspection_stays_original_then_new_passive_windows_qualify(self):
        domain=self.prepared();domain.lost_buttons.add('snapshot.share.archive.source-retire-inspect')
        with domain.owner() as share,self.assertRaises(NativeUIError):share.source_retirement_owner().cleanup()
        original=domain.archive.source_inspect_text;REAL_SLEEP(5.6)
        with domain.owner() as share,self.assertRaises(NativeUIError):share.source_retirement_owner().cleanup()
        with domain.owner() as share:
            owner=share.source_retirement_owner();row=owner.state['after'][0];self.assertIs(row['qualified'],False)
            frame=deepcopy(owner.observed(row)[1]);raw=owner.action(row,True).original()
            self.assertEqual(original.encode(),raw);self.assertTrue(owner.cleanup()['sourceFilesRetired'])
            self.assertEqual(frame,owner.observed(row)[1]);self.assertEqual(raw,owner.action(row,True).original())
        self.assertEqual(1,domain.archive.source_retire_calls);self.assertEqual(4,domain.archive.ui.clicks.count('snapshot.share.archive.source-retire-inspect'))

    def test_expired_unissued_admission_preserves_original_window_and_acquires_new_samples(self):
        domain=self.prepared()
        with domain.owner() as share:
            owner=share.source_retirement_owner();actual=owner.action
            def stop(row=None,history=False):
                if row is None and not history:raise NativeUIError('Declared stop before the first source retirement UI slot')
                return actual(row,history)
            owner.action=stop
            with self.assertRaises(NativeUIError):owner.cleanup()
            group=deepcopy(owner.state['before'][0]);originals=[deepcopy(owner.queries.query_original(index)) for index in group]
        self.assertEqual(0,domain.archive.source_retire_calls);REAL_SLEEP(3.1)
        with domain.owner() as share:
            owner=share.source_retirement_owner();self.assertTrue(owner.cleanup()['sourceFilesRetired'])
            self.assertEqual(2,len(owner.state['before']));self.assertEqual(group,owner.state['before'][0])
            self.assertEqual(originals,[owner.queries.query_original(index) for index in group])
        self.assertEqual(1,domain.archive.source_retire_calls)


if __name__=='__main__':unittest.main()
