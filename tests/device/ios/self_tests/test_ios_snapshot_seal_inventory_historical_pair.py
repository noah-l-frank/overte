"""Same-call actual Seal/Inventory originals; all current frame guards remain.

Real descriptors/files/Node/normal owner paths; native/UIKit/SDK producers
remain explicit host models. No End/Area25/whole acceptance is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_seal_owner import SnapshotShareAdmissionSealOwner
from ios.adapters.snapshot_share_inventory_owner import SnapshotShareSourceInventoryOwner
from ios.adapters.snapshot_photos_end_read_area import _ACTIVE
from ios.self_tests.snapshot_share_seal_domain import ShareSealDomain,RUN
from ios.self_tests import test_ios_snapshot_share_inventory as inventory_tests


class SnapshotSealInventoryHistoricalPairTests(unittest.TestCase):
    @contextmanager
    def original_entries(self):
        old=sys.getprofile();self.assertTrue(old is None or callable(old));entries=[]
        codes=(SnapshotShareAdmissionSealOwner.original.__code__,SnapshotShareSourceInventoryOwner.original.__code__)
        def actual(frame,event,arg):
            if old is not None:old(frame,event,arg)
            if event=='call' and any(frame.f_code is code for code in codes):entries.append(frame.f_locals['self'])
        sys.setprofile(actual)
        try:yield entries
        finally:sys.setprofile(old)

    @staticmethod
    def count(entries,owner):return sum(value is owner for value in entries)

    def snapshots(self,roots):
        return {str(path):(path.stat().st_dev,path.stat().st_ino,path.stat().st_size,path.stat().st_mtime_ns,
            path.stat().st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
            for root in roots for path in root.rglob('*') if path.is_file()}

    def seal(self):
        d=ShareSealDomain(self)
        with d.seal_owner() as owner:proof=owner.seal()
        return d,proof

    def seal_history(self,d,cls=SnapshotShareAdmissionSealOwner):
        return cls.history(PrivateFeatureState(d.root/'share-admission-seal-owner.json'),d.source_lock,
            d.binding,RUN,d.fixture_url,d.ipa,d.admission_store)

    def inventory(self):
        fixture=inventory_tests.SnapshotShareInventoryTests();self.addCleanup(fixture.doCleanups)
        d=fixture.prepared()
        with d.owner() as share:proof=share.source_inventory_owner().inspect()
        return fixture,d,proof

    def external(self):
        value=tempfile.TemporaryDirectory(prefix='share-pair-original-witness-');self.addCleanup(value.cleanup)
        return Path(value.name)

    def test_actual_seal_history_one_original_live_load_two_and_public_proof_copy_stays_independent(self):
        d,expected=self.seal();before=self.snapshots([d.root]);calls=d.seal_calls,d.close_calls
        with d.source_lock.held(),patch.object(d,'call',side_effect=AssertionError('No live SDK in history')),patch.object(d,'execute',side_effect=AssertionError('No native query in history')):
            with self.original_entries() as entries:reader=self.seal_history(d)
            self.assertEqual(1,self.count(entries,reader));self.assertEqual(expected,reader.proof())
            value=reader.proof();value['outputs'].clear();self.assertEqual(expected,reader.proof())
        self.assertEqual(before,self.snapshots([d.root]));self.assertEqual(calls,(d.seal_calls,d.close_calls))
        with d.seal_owner() as owner:
            with self.original_entries() as entries:loaded=owner.load(owner.previous)
            self.assertEqual(2,self.count(entries,owner));self.assertEqual(owner.state,loaded)

    def test_actual_inventory_subclass_history_one_original_and_live_loader_remains_two(self):
        fixture,d,expected=self.inventory();before=self.snapshots([d.main.ctx.root,d.archive.root]);calls=d.archive.inventory_calls
        with d.main.ctx.lock.held(),d.archive.source_lock.held(),patch.object(d.archive,'execute',side_effect=AssertionError('No live SDK')),patch.object(d.primary,'probe',side_effect=AssertionError('No live primary')):
            with self.original_entries() as entries:reader=fixture.history(d)
            self.assertEqual(1,self.count(entries,reader));self.assertEqual(expected,reader.proof())
            value=reader.proof();value['outputs'].clear();self.assertEqual(expected,reader.proof())
        self.assertEqual(before,self.snapshots([d.main.ctx.root,d.archive.root]));self.assertEqual(calls,d.archive.inventory_calls)
        with d.owner() as share:
            owner=share.source_inventory_owner()
            with self.original_entries() as entries:loaded=owner.load(owner.previous)
            self.assertEqual(2,self.count(entries,owner));self.assertEqual(owner.state,loaded)

    def test_foreign_seal_subclass_keeps_literal_two_original_load_order(self):
        class ForeignSeal(SnapshotShareAdmissionSealOwner):pass
        d,expected=self.seal()
        with d.source_lock.held():
            with self.original_entries() as entries:reader=self.seal_history(d,ForeignSeal)
            self.assertEqual(2,self.count(entries,reader));self.assertEqual(expected,reader.proof())

    def test_actual_seal_original_byte_change_after_first_return_is_refused_by_current_action_frame_read(self):
        d,_expected=self.seal();self.assertIsNone(_ACTIVE.get(),'Do not mask a faulty same-call path with an epoch fallback')
        with d.source_lock.held():
            baseline=self.seal_history(d);action=baseline.action(True);path=action.files.path(action.files.expand(action.state['proof']))
            raw=path.read_bytes();witness=self.external()/'seal-before-corruption.original';witness.write_bytes(raw);witness.chmod(0o600)
            inode=path.stat().st_ino;original=SnapshotShareAdmissionSealOwner.original;changed=[];calls=d.seal_calls,d.close_calls
            def actual(owner):
                result=original(owner)
                if type(owner) is SnapshotShareAdmissionSealOwner and not changed:
                    path.write_bytes(raw[:-1]+(b' ' if raw[-1:]!=b' ' else b'\n'));changed.append(True)
                return result
            with patch.object(SnapshotShareAdmissionSealOwner,'original',actual),self.assertRaises(NativeUIError):self.seal_history(d)
            self.assertEqual([True],changed);self.assertEqual(inode,path.stat().st_ino);self.assertEqual(raw,witness.read_bytes())
            self.assertEqual(calls,(d.seal_calls,d.close_calls))

    def test_actual_inventory_samebytes_new_original_inode_after_first_return_cannot_be_reanchored(self):
        fixture,d,_expected=self.inventory();self.assertIsNone(_ACTIVE.get(),'This exact default path must execute')
        with d.main.ctx.lock.held(),d.archive.source_lock.held():
            baseline=fixture.history(d);action=baseline.action(True);path=action.files.path(action.files.expand(action.state['proof']))
            raw=path.read_bytes();inode=path.stat().st_ino;witness=self.external()/'inventory-original-inode.json'
            original=SnapshotShareSourceInventoryOwner.original;changed=[];calls=d.archive.inventory_calls
            def actual(owner):
                result=original(owner)
                if type(owner) is SnapshotShareSourceInventoryOwner and not changed:
                    path.rename(witness);path.write_bytes(raw);path.chmod(0o600);changed.append(True)
                return result
            with patch.object(SnapshotShareSourceInventoryOwner,'original',actual),self.assertRaises(NativeUIError):fixture.history(d)
            self.assertEqual([True],changed);self.assertEqual(inode,witness.stat().st_ino)
            self.assertNotEqual(inode,path.stat().st_ino);self.assertEqual(raw,witness.read_bytes());self.assertEqual(raw,path.read_bytes())
            self.assertEqual(calls,d.archive.inventory_calls)


if __name__=='__main__':unittest.main()
