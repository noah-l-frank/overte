"""Connected original pending/cancel owners; Qt/native producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner,SnapshotPendingCapturePending
from ios.self_tests.snapshot_pending_domain import SnapshotPendingDomain,RUN


class SnapshotPendingOwnerTests(unittest.TestCase):
    def lost(self,control):
        d=SnapshotPendingDomain(self);d.lost_controls.add(control)
        with d.owner() as owner,self.assertRaises(OSError):owner.cancel('f'*32)
        with d.owner() as owner:self.assertTrue(owner.cancel('f'*32)['wholeFeatureRequired'])
        self.assertEqual((1,1),(d.capture_count,d.cancel_count));return d

    def test_normal_pending_cancel_joins_actual_timer_death_and_restores_original_settings(self):
        d=SnapshotPendingDomain(self)
        with d.owner() as owner:
            result=owner.cancel('f'*32);self.assertGreaterEqual(result['nativeQuietMilliseconds'],3000);self.assertGreaterEqual(result['hostQuietMilliseconds'],3000)
            self.assertTrue(result['wholeFeatureRequired']);self.assertTrue(result['originalJournalRetirementRequired']);fixture_url=owner.phase.fixture_url
        self.assertEqual((1,1,0,''),(d.capture_count,d.cancel_count,d.mode_index,d.f.input_native.name));self.assertFalse(d.popup)
        self.assertTrue(all(weak() is None and row['destroyedEpochMs'] is not None for weak,row in d.timer_records));self.assertFalse(d.f.f.h.path.exists())
        edits=[row for row in d.f.input_native.requests if row['operation']=='edit']
        with d.owner() as owner:self.assertEqual(result,owner.cancel('f'*32))
        self.assertEqual(len(edits),len([row for row in d.f.input_native.requests if row['operation']=='edit']))
        d.good=False
        with d.ctx.lock.held():
            history=IOSSnapshotPendingOwner.archive(PrivateFeatureState(d.ctx.root/'pending-snapshot-owner.json'),d.ctx.lock,d.ctx.binding,RUN,fixture_url)
            self.assertEqual(result,history.result())
            original=history.previous
            for fault in ('tail-birth','tail-sequence','restoration-pid'):
                bad=deepcopy(original);state=unpack(bad['payload'])[0]
                if fault=='tail-birth':state['nativeTail']['instance']='f'*32
                elif fault=='tail-sequence':state['nativeTail']['sequence']+=1
                else:state['restoration']['ui']['processId']=43
                bad['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):history.decode(bad)
            self.assertEqual(original,history.store.read())

    def test_lost_capture_return_uses_original_reception_without_second_pending_capture(self):self.lost('snapshot.capture')
    def test_lost_cancel_return_uses_original_reception_without_second_cancel(self):self.lost('snapshot.cancel')
    def test_lost_animated_choice_return_recovers_when_the_actual_popup_is_already_closed(self):self.lost('snapshot.mode.animated')
    def test_lost_still_restoration_choice_return_never_reopens_or_resends_the_choice(self):self.lost('snapshot.mode.still')

    def test_retained_real_timer_objects_block_until_weak_death_without_repeating_cancel(self):
        d=SnapshotPendingDomain(self);d.hold_timers=True
        with d.owner() as owner,self.assertRaises(SnapshotPendingCapturePending):owner.cancel('f'*32)
        self.assertEqual((1,1),(d.capture_count,d.cancel_count));self.assertTrue(d.held);self.assertTrue(all(row['destroyedEpochMs'] is None for _weak,row in d.timer_records))
        d.held.clear()
        with d.owner() as owner:self.assertTrue(owner.cancel('f'*32)['originalSettingsRestored'])
        self.assertEqual((1,1),(d.capture_count,d.cancel_count));self.assertTrue(all(weak() is None for weak,_row in d.timer_records))

    def test_acknowledged_ignored_choice_cannot_produce_a_pending_capture_or_repeat_the_input(self):
        d=SnapshotPendingDomain(self);d.ignored_controls.add('snapshot.mode.animated')
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(NativeUIError):owner.cancel('f'*32)
        self.assertEqual((0,0),(d.capture_count,d.cancel_count));self.assertEqual(4,len([row for row in d.f.input_native.requests if row['operation']=='edit']))

    def test_acknowledged_ignored_cancel_cannot_claim_timer_or_file_quiet_and_never_repeats(self):
        d=SnapshotPendingDomain(self);d.ignored_controls.add('snapshot.cancel')
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(SnapshotPendingCapturePending):owner.cancel('f'*32)
        self.assertEqual((1,0),(d.capture_count,d.cancel_count));self.assertTrue(d.capturing)
        edits=[row for row in d.f.input_native.requests if row['operation']=='edit'];self.assertEqual(1,sum(row['input']['fieldToken']==d.tokens['snapshot.cancel'] for row in edits))

    def test_saved_pending_original_before_parent_CAS_keeps_its_original_inode_and_does_not_requery(self):
        d=SnapshotPendingDomain(self)
        with d.owner() as owner:
            actual=owner.save
            def before_parent():
                if any(row['label']=='actual-pending' and row['sha256'] is not None for row in owner.state['slots']):raise OSError('Declared lost parent CAS after saved actual pending original')
                actual()
            with patch.object(owner,'save',before_parent),self.assertRaises(OSError):owner.cancel('f'*32)
            slot=next(row for row in owner.state['slots'] if row['label']=='actual-pending');child=owner.child(slot,True);original=deepcopy(child.historical());reference=deepcopy(child.state['storage'])
            path=child.files().path(reference);identity=(path.stat().st_dev,path.stat().st_ino,path.read_bytes());nonce=child.state['query']['commandId']
        with d.owner() as owner:
            owner.cancel('f'*32);self.assertEqual(original,owner.history('work',slot['index']).historical())
        self.assertEqual(identity,(path.stat().st_dev,path.stat().st_ino,path.read_bytes()));self.assertEqual(1,sum(command['commandId']==nonce for command in d.commands))
        self.assertEqual((1,1),(d.capture_count,d.cancel_count))


if __name__=='__main__':unittest.main()
