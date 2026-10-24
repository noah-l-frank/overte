"""Actual component originals and private file-loss recovery; no native build."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import canonical,unpack
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.self_tests.test_ios_emote_rooted_retirement import RootedRetirementCompositionTests


class RootedLiveTests(unittest.TestCase):
    def setUp(self):
        self.f=RootedRetirementCompositionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_actual_cut_is_compact_idempotent_purely_replayable_and_original_tampering_fails(self):
        owner=self.f.keyed;live=IOSEmoteRootedLive(owner);domain=self.f.f.domain
        history=len(domain.history);actions=list(domain.io.actions)
        row=live.append(self.f.keyed_ref);public=row['measurement']['public']
        self.assertTrue(public['resources']);self.assertEqual(1,len(live.state['records']))
        self.assertEqual({'index','sha256','bytes','device','inode'},set(live.state['records'][0]))
        self.assertLess(len(canonical(live.previous)),4096)
        self.assertEqual(row,live.append(self.f.keyed_ref));self.assertEqual(1,len(live.state['records']))
        self.assertEqual([row],live.selected_many([public]))
        actual_files={p:(p.stat().st_ino,p.read_bytes()) for p in owner.root.rglob('*') if p.is_file()}
        def forbidden(*_args,**_kwargs):self.fail('Historical live cut queried live ownership')
        owner.guard=forbidden
        archive=IOSEmoteRootedLive.archive(live.previous,store=Frozen(live.store.path,live.previous),lock=owner.lock,primary_lock=owner.primary_lock)
        self.assertEqual([row],archive.selected_many([public]));self.assertEqual(history,len(domain.history));self.assertEqual(actions,domain.io.actions)
        self.assertEqual(actual_files,{p:(p.stat().st_ino,p.read_bytes()) for p in owner.root.rglob('*') if p.is_file()})
        for fault in ('boolean','future','role','binding','fixture','instance','policy'):
            value=deepcopy(live.previous)
            if fault=='boolean':value['iosEmoteRootedLiveVersion']=True
            elif fault=='future':value['iosEmoteRootedLiveVersion']=2
            elif fault=='role':value['role']='actor'
            elif fault=='binding':value['binding']['processIdentity']='52'
            elif fault=='fixture':value['fixtureUrl']+='foreign/'
            elif fault=='instance':value['phaseInstance']='9'*32
            else:value['imagePolicy']['source']='foreign'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                IOSEmoteRootedLive.archive(value,store=Frozen(live.store.path,value),lock=owner.lock,primary_lock=owner.primary_lock)
        wrong=deepcopy(public);wrong['sequence']+=1
        with self.assertRaises(NativeUIError):archive.selected_many([wrong])
        with self.assertRaises(NativeUIError):archive.append(self.f.keyed_ref)
        # A current metadata prefix cannot forget an unowned next original.
        orphan=owner.root/('emote-rooted-live-frame-inputs-'+live.run+'-'+live.role+'-0002-'+'f'*64+'.json')
        with orphan.open('xb') as stream:stream.write(b'{}')
        orphan.chmod(0o600)
        try:
            with self.assertRaises(NativeUIError):IOSEmoteRootedLive(owner)
        finally:orphan.unlink()
        path=live.originals.path(live.originals.expand(row['reference']));raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaises(NativeUIError):archive.selected_many([public])

    def test_lost_saved_return_adopts_same_inode_and_planned_unknown_birth_stays_pending(self):
        owner=self.f.keyed;live=IOSEmoteRootedLive(owner);intent=live.intent;lost=[]
        def interrupted(kind,value):
            result=intent(kind,value)
            if value['phase']=='saved' and not lost:lost.append(True);raise OSError('Actual private saved return lost')
            return result
        live.originals.intent=interrupted
        with self.assertRaises(OSError):live.append(self.f.keyed_ref)
        pending=deepcopy(live.state['pending']);self.assertEqual('saved',pending['original']['phase'])
        path=live.originals.path(pending['original']);before=(path.stat().st_dev,path.stat().st_ino,path.read_bytes())
        domain=self.f.f.domain;history=len(domain.history);actions=list(domain.io.actions)
        resumed=IOSEmoteRootedLive(owner);row=resumed.append(self.f.keyed_ref)
        self.assertIsNone(resumed.state['pending']);self.assertEqual(1,len(resumed.state['records']))
        self.assertEqual(before,(path.stat().st_dev,path.stat().st_ino,path.read_bytes()))
        self.assertEqual([row],resumed.selected_many([row['measurement']['public']]))
        self.assertEqual(history,len(domain.history));self.assertEqual(actions,domain.io.actions)
        # The same genuinely saved original can demonstrate a metadata loss
        # before observed file birth. No decoder may guess its actual inode.
        state=dict(records=[],pending=deepcopy(pending));state['pending']['original'].update(phase='planned',file=None)
        value=resumed.envelope(state);resumed.store.write(value,resumed.previous)
        blocked=IOSEmoteRootedLive(owner)
        with self.assertRaises(NativeUIError):blocked.append(self.f.keyed_ref)
        self.assertEqual(value,blocked.store.read());self.assertEqual(before,(path.stat().st_dev,path.stat().st_ino,path.read_bytes()))
        self.assertEqual(history,len(domain.history));self.assertEqual(actions,domain.io.actions)

    def test_lost_completed_metadata_return_requires_reconstruction_and_keeps_one_original(self):
        owner=self.f.keyed;live=IOSEmoteRootedLive(owner);write=PrivateFeatureState.write;lost=[]
        def interrupted(store,value,previous):
            write(store,value,previous)
            if store.path==live.store.path:
                state=unpack(value['payload'])[0]
                if state['records'] and state['pending'] is None and not lost:
                    lost.append(True);raise OSError('Actual completed metadata commit return lost')
        with patch.object(PrivateFeatureState,'write',interrupted),self.assertRaises(OSError):live.append(self.f.keyed_ref)
        self.assertTrue(live.failed)
        with self.assertRaises(NativeUIError):live.append(self.f.keyed_ref)
        pattern='emote-rooted-live-frame-inputs-'+live.run+'-'+live.role+'-*.json'
        before={p:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in live.root.glob(pattern)}
        self.assertEqual(1,len(before));domain=self.f.f.domain;history=len(domain.history);actions=list(domain.io.actions)
        resumed=IOSEmoteRootedLive(owner);row=resumed.append(self.f.keyed_ref)
        self.assertEqual(1,len(resumed.state['records']));self.assertIsNone(resumed.state['pending'])
        self.assertEqual([row],resumed.selected_many([row['measurement']['public']]))
        self.assertEqual(before,{p:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in live.root.glob(pattern)})
        self.assertEqual(history,len(domain.history));self.assertEqual(actions,domain.io.actions)

    def test_scoped_archive_reuses_only_its_qualified_graph_and_clears_it_on_return_or_error(self):
        owner=self.f.keyed;live=IOSEmoteRootedLive(owner);row=live.append(self.f.keyed_ref)
        options=dict(store=Frozen(live.store.path,live.previous),lock=owner.lock,primary_lock=owner.primary_lock)
        with IOSEmoteRootedLive.archive_scope(live.previous,**options) as archive:
            prepared=archive.prepared;self.assertTrue(prepared.active)
            self.assertEqual(row,archive.record(row['reference']))
            self.assertEqual([row],archive.selected_many([row['measurement']['public']]))
        self.assertIsNone(archive.prepared);self.assertFalse(prepared.active)
        with self.assertRaises(NativeUIError):prepared.guard()
        class Interrupted(Exception):pass
        with self.assertRaises(Interrupted):
            with IOSEmoteRootedLive.archive_scope(live.previous,**options) as archive:
                prepared=archive.prepared;raise Interrupted('Read-only consumer interrupted')
        self.assertIsNone(archive.prepared);self.assertFalse(prepared.active)

    def test_scoped_archive_refuses_same_inode_original_rewrite_before_return(self):
        owner=self.f.keyed;live=IOSEmoteRootedLive(owner);row=live.append(self.f.keyed_ref)
        path=live.originals.path(live.originals.expand(row['reference']));raw=path.read_bytes()
        with self.assertRaises(NativeUIError):
            with IOSEmoteRootedLive.archive_scope(live.previous,store=Frozen(live.store.path,live.previous),
                    lock=owner.lock,primary_lock=owner.primary_lock) as archive:
                self.assertEqual(row,archive.record(row['reference']));path.write_bytes(raw)
        self.assertEqual(raw,path.read_bytes());self.assertIsNone(archive.prepared)


if __name__=='__main__':unittest.main()
