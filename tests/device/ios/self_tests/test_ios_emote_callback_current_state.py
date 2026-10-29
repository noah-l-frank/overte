"""Actual Scene4 copies joined to current Sample3/Observer4/GPU originals.

Real host files/JS/PNG are used with the declared native source model. No
terminal, Stop, SDK deletion, current physical GPU or whole result is supplied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters import emote_callback_archive as archive
from ios.adapters import emote_callback_current_state as state
from ios.adapters import emote_rooted_gpu as legacy_gpu
from ios.adapters.emote_callback_live import IOSEmoteCallbackLive
from ios.self_tests.emote_callback_scene_fixture import CallbackSceneFixture


class CallbackCurrentStateTests(unittest.TestCase):
    def closed(self):
        f=CallbackSceneFixture(self);f.cleanup();return f

    def snapshot(self,f):return archive.capture(f.keyed,f.keyed_ref)
    def reader(self,f):return state.collect(self.snapshot(f),lock=f.lock,primary_lock=f.lock)
    def changed(self,f,reader,copies):return state.CallbackCurrentState(reader.snapshot,copies,lock=f.lock,primary_lock=f.lock)
    def queries(self,f):
        return dict(native=len(f.domain.history),inputs=deepcopy(f.domain.io.actions),files=deepcopy(f.file_boundary.commands),
            keys=deepcopy(f.key_domain.commands),gpu=[deepcopy(q) for slot in f.t.callback_context.worlds.values() for q in slot.commands])

    def test_actual_current_original_join_keeps_pending_as_of_sample_and_old_gpu_reader_strict(self):
        f=self.closed();before=self.queries(f);parts=state.current(self.snapshot(f),lock=f.lock,primary_lock=f.lock)
        self.assertTrue(parts['currentGpu']);self.assertEqual(before,self.queries(f))
        first=f.first_original['image'];old=unpack(first['owner'])[0]
        self.assertIsNone(old['absence']);self.assertEqual(1,unpack(first['payload'])[0]['retirement']['source']['callbacks'])
        live=IOSEmoteCallbackLive(f.keyed);row=live.append(f.keyed_ref);self.assertTrue(row['measurement']['public']['resources'])
        flow=SimpleNamespace(lock=f.lock,primary_lock=f.lock,store=live.store,root=f.root,role=f.scope.role,
            run=f.scope.run,state=dict(binding=f.scope.binding))
        with self.assertRaises(NativeUIError):legacy_gpu.validate(flow,dict(samples=parts['samples'],restoration=f.frames))
        self.assertEqual(before,self.queries(f));self.assertIsNone(old['absence'])

    def test_projection4_cannot_be_used_as_the_distinct_current_samples3_wal(self):
        f=self.closed();reader=self.reader(f);copies=deepcopy(reader.copies)
        copies[str(f.t.samples.store.path)]=deepcopy(f.original['sampleOwners']);before=self.queries(f)
        with self.assertRaises(NativeUIError):self.changed(f,reader,copies).read()
        self.assertEqual(before,self.queries(f))

    def test_missing_or_foreign_current_gpu_wal_cannot_borrow_typed_historical_drain_absence(self):
        f=self.closed();reader=self.reader(f);request=f.t.samples.state['rows'][0]['requestId']
        path=f.lock.path.with_name('graphics-world-frame-primary-0-'+request[4:]+'.json');before=self.queries(f)
        for fault in ('missing','foreign-inode'):
            copies=deepcopy(reader.copies)
            if fault=='missing':copies[str(path)]=None
            else:copies[str(path)]['file']['inode']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.changed(f,reader,copies).read()
        self.assertEqual(before,self.queries(f))

    def test_unlisted_current_metadata_does_not_fall_back_to_an_existing_current_file(self):
        f=self.closed();reader=self.reader(f);path=str(f.t.observer.store.path);self.assertIsNotNone(PrivateFeatureState(path).read())
        copies=deepcopy(reader.copies);del copies[path];before=self.queries(f)
        with self.assertRaises(NativeUIError):self.changed(f,reader,copies).read()
        self.assertEqual(before,self.queries(f))

    def test_actual_same_body_owner_wal_write_during_collection_refuses_before_live_intent(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);owner=f.t.samples.owner(f.t.samples.state['rows'][0]);target=owner.store.path
        original=PrivateFeatureState.read;changed=[];before=self.queries(f)
        def reading(store):
            value=original(store)
            if store.path==target and not changed:
                raw=target.read_bytes();target.write_bytes(raw);changed.append(raw)
            return value
        with patch.object(PrivateFeatureState,'read',reading),self.assertRaises(NativeUIError):live.append(f.keyed_ref)
        self.assertEqual(1,len(changed));self.assertIsNone(live.state['pending']);self.assertEqual([],live.state['records'])
        self.assertIsNone(live.store.read());self.assertEqual(before,self.queries(f));self.assertEqual(changed[0],target.read_bytes())

    def test_unknown_gpu_owner_prefix_is_not_silently_adopted_as_an_absent_sample(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);orphan=f.lock.path.with_name('graphics-world-frame-primary-0-'+'f'*32+'.json')
        orphan.write_bytes(b'{}');orphan.chmod(0o600);before=self.queries(f)
        with self.assertRaises(NativeUIError):live.append(f.keyed_ref)
        self.assertEqual(b'{}',orphan.read_bytes());self.assertIsNone(live.store.read());self.assertIsNone(live.state['pending'])
        self.assertEqual(before,self.queries(f))

    def test_actual_missing_scope_wal_blocks_live_before_any_new_metadata_or_original_file(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);scope=f.scope.store;scope.discard(scope.read());before=self.queries(f)
        with self.assertRaises(NativeUIError):live.append(f.keyed_ref)
        self.assertIsNone(live.store.read());self.assertEqual([],live.state['records']);self.assertIsNone(live.state['pending'])
        self.assertFalse(any(f.root.glob('emote-rooted-live-frame-inputs-*')));self.assertEqual(before,self.queries(f))

    def test_later_actual_inspect_keeps_same_original_prefix_without_renewing_scene_or_old_sample(self):
        f=self.closed();first=deepcopy(f.first_original);row=f.t.samples.state['rows'][0];owner=f.t.samples.owner(row)
        original=deepcopy(owner.store.read());proof=owner.release_once();later=owner.store.read()
        self.assertGreater(len(unpack(later['transcript'])),len(unpack(original['transcript'])))
        self.assertEqual('inspect',unpack(later['transcript'])[-1]['command']['operation']);self.assertEqual(0,proof['source']['callbacks'])
        before=self.queries(f);parts=state.current(self.snapshot(f),lock=f.lock,primary_lock=f.lock)
        self.assertTrue(parts['currentGpu']);self.assertEqual(before,self.queries(f));self.assertEqual(first,f.first_original)
        self.assertIsNone(unpack(first['image']['owner'])[0]['absence'])


if __name__=='__main__':unittest.main()
