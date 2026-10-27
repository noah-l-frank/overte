"""Closed combined pending cancellation and immutable normal-input recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner,SnapshotPendingCapturePending
from ios.self_tests.snapshot_combined_pending_domain import CombinedPendingDomain,RUN


class SnapshotCombinedPendingTests(unittest.TestCase):
    def test_unknown_combined_original_prefix_blocks_initial_owner_without_dispatch(self):
        d=CombinedPendingDomain(self);commands=deepcopy(d.commands)
        for prefix in ('pending-combined-work-','snapshot-combined-pending-parts-'):
            path=d.ctx.root/(prefix+'orphan.json');path.write_bytes(b'foreign original');path.chmod(0o600)
            before=(path.stat().st_ino,path.read_bytes())
            with self.subTest(prefix=prefix),self.assertRaises(NativeUIError),d.owner():pass
            self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));self.assertEqual(commands,d.commands);path.unlink()
        with d.owner() as owner:self.assertIsNone(owner.previous)
        self.assertEqual((0,0),(d.capture_count,d.cancel_count))

    def test_normal_pending_cancel_restores_settings_and_replays_original_combined_archive(self):
        d=CombinedPendingDomain(self)
        with d.owner() as owner:
            result=owner.cancel('f'*32);self.assertEqual(2,result['iosSnapshotPendingResultVersion'])
            self.assertEqual('combined',result['workProfile']);self.assertEqual(2,result['cancellation']['iosSnapshotOwnedPendingCancellationVersion'])
            self.assertGreaterEqual(result['nativeQuietMilliseconds'],3000);self.assertGreaterEqual(result['hostQuietMilliseconds'],3000)
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.phase.fixture_url
        self.assertEqual((1,1,0,''),(d.capture_count,d.cancel_count,d.mode_index,d.f.input_native.name));self.assertFalse(d.popup)
        self.assertFalse(d.f.f.h.path.exists());commands=deepcopy(d.commands)
        with d.owner() as owner:self.assertEqual(result,owner.cancel('f'*32))
        with lock.held():
            archived=IOSSnapshotPendingOwner.archive(store,lock,binding,RUN,url,combined=True);self.assertEqual(result,archived.result())
            with self.assertRaises(NativeUIError):IOSSnapshotPendingOwner.archive(store,lock,binding,RUN,url)
        self.assertEqual(commands,d.commands);self.assertTrue(all(weak() is None and row['destroyedEpochMs'] is not None for weak,row in d.timer_records))

    def test_lost_normal_cancel_return_reopens_original_reception_without_second_cancel(self):
        d=CombinedPendingDomain(self);d.lost_controls.add('snapshot.cancel')
        with d.owner() as owner,self.assertRaises(OSError):owner.cancel('f'*32)
        with d.owner() as owner:self.assertEqual(2,owner.cancel('f'*32)['iosSnapshotPendingResultVersion'])
        self.assertEqual((1,1),(d.capture_count,d.cancel_count))

    def test_retained_actual_timer_objects_stay_responsible_until_original_weak_death(self):
        d=CombinedPendingDomain(self);d.hold_timers=True
        with d.owner() as owner,self.assertRaises(SnapshotPendingCapturePending):owner.cancel('f'*32)
        self.assertTrue(d.held);self.assertTrue(all(row['destroyedEpochMs'] is None for _weak,row in d.timer_records))
        d.held.clear()
        with d.owner() as owner:self.assertTrue(owner.cancel('f'*32)['originalSettingsRestored'])
        self.assertEqual((1,1),(d.capture_count,d.cancel_count))

    def test_acknowledged_ignored_cancel_cannot_claim_quiet_or_repeat_normal_cancel(self):
        d=CombinedPendingDomain(self);d.ignored_controls.add('snapshot.cancel')
        for _attempt in range(2):
            with d.owner() as owner,self.assertRaises(SnapshotPendingCapturePending):owner.cancel('f'*32)
        self.assertEqual((1,0),(d.capture_count,d.cancel_count));self.assertTrue(d.capturing)
        self.assertEqual(1,sum(query['operation']=='edit' and query['input']['fieldToken']==d.tokens['snapshot.cancel'] for query in d.f.input_native.requests))

    def test_saved_actual_pending_before_parent_cas_keeps_original_files_and_query_once(self):
        d=CombinedPendingDomain(self)
        with d.owner() as owner:
            save=owner.save
            def lost():
                if any(slot['label']=='actual-pending' and slot['sha256'] is not None for slot in owner.state['slots']):raise OSError('Declared loss after original combined pending child before parent CAS')
                return save()
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(OSError):owner.cancel('f'*32)
            slot=next(slot for slot in owner.state['slots'] if slot['label']=='actual-pending');child=owner.child(slot,True)
            original=deepcopy(child.historical());nonce=child.state['query']['commandId']
            pins={path.name:(path.stat().st_dev,path.stat().st_ino,path.read_bytes()) for path in d.ctx.root.iterdir()
                if path.name.startswith(('pending-combined-work-','snapshot-combined-pending-parts-'))}
        self.assertTrue(pins)
        with d.owner() as owner:owner.cancel('f'*32);self.assertEqual(original,owner.history('work',slot['index']).historical())
        self.assertEqual(pins,{name:((d.ctx.root/name).stat().st_dev,(d.ctx.root/name).stat().st_ino,(d.ctx.root/name).read_bytes()) for name in pins})
        self.assertEqual(1,sum(query['commandId']==nonce for query in d.commands));self.assertEqual((1,1),(d.capture_count,d.cancel_count))


if __name__=='__main__':unittest.main()
