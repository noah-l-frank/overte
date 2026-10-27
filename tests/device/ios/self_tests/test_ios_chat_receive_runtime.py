"""Existing installed-peer admission and private scopes; explicit SDK models.

The native producers are declared state machines. The actual admission parser,
receiver, locks, root identities, journals and recovery code execute locally.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_chat_observation import OwnedChatCapture
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.chat_draft_runtime import IOSChatDraftRuntime
from ios.adapters.chat_session_owners import owners_absent
from ios.self_tests.test_ios_peer_admission import PeerAdmissionTests
from self_tests.test_native_chat_observation import Boundary,RUN,SELF,PEER


class CaptureTransport:
    def __init__(self,native,pid):self.native,self.pid=native,pid
    def chat_capture(self,owner,run):
        reader=self.native.reader(ios=True);reader.pid=self.pid
        return OwnedChatCapture(reader,owner,run)


class IOSChatReceiveRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f=PeerAdmissionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.runtime=object.__new__(IOSChatDraftRuntime);self.runtime.adapter=self.f.runtime.adapter
        self.runtime._existing=self.f.runtime._existing
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.paths={};self.artifacts={};self.locks={}
        for role in ('primary','peer'):
            directory=self.root/role;directory.mkdir(mode=0o700);self.paths[role]=directory/'session.json'
            self.artifacts[role]=directory/'artifacts';self.artifacts[role].mkdir(mode=0o700)
            self.locks[role]=ScriptSourceLock(directory/'script-feature-sources.lock');self.enterContext(self.locks[role].held())
        self.runtime.state_path=lambda role:self.paths[role];self.runtime.adapter.state_path=self.runtime.state_path
        self.primary,self.peer=Boundary(),Boundary()
        self.primary.mutate=lambda value:value.update(processId=31)
        def peer_packet(value):value.update(processId=42,instance='e'*32);value['source']['selfSha256']=PEER
        self.peer.mutate=peer_packet
        def peer_check():self.f.fixture.make().continuity();return self.peer.guard()
        self.sources=dict(primary=dict(binding=deepcopy(self.f.primary),check=self.primary.guard,observer=CaptureTransport(self.primary,31)),
            peer=dict(binding=dict(self.f.fixture.scope,processIdentity='42'),check=peer_check,observer=CaptureTransport(self.peer,42)))
        self.runtime._sources=lambda role:self.sources[role]
    def parts(self,**overrides):
        values=dict(primary_root=self.artifacts['primary'],peer_root=self.artifacts['peer'],
            primary_lock=self.locks['primary'],peer_lock=self.locks['peer']);values.update(overrides)
        return self.runtime._chat_receive_components('primary','peer',RUN,**values)
    def commands(self):return deepcopy((self.primary.commands,self.peer.commands))
    def census(self):
        return {str(path.relative_to(self.root)):(path.stat().st_ino,path.read_bytes())
            for path in self.root.rglob('*') if path.is_file()}
    def test_admission_and_scopes_precede_native_cache_creation_on_existing_targets(self):
        parts=self.parts();self.assertEqual(([],[]),self.commands())
        self.assertFalse(owners_absent(self.runtime.adapter,'primary'));self.assertFalse(owners_absent(self.runtime.adapter,'peer'))
        self.assertEqual(self.f.fixture.store.read(),parts['binding']['admission']['installedBefore'])
        self.assertFalse(self.primary.present);self.assertFalse(self.peer.present)
        with self.assertRaises(NativeUIError):parts['receiver'].sample()
        self.assertEqual(([],[]),self.commands())
        parts['primary_capture'].observe();parts['receiver'].sample();self.peer.event(sender=SELF)
        sample=parts['receiver'].sample();self.assertEqual(20000,sample['peer']['capturedEpochMs'])
        self.assertEqual(1,len(sample['peerMessages']));self.assertEqual(2,sample['receiverVersion'])
    def test_reconstruction_uses_same_original_pair_and_no_constructor_chat_queries_or_writes(self):
        parts=self.parts();parts['primary_capture'].observe();parts['receiver'].sample();self.peer.event(sender=SELF)
        parts['receiver'].sample();commands=self.commands();files=self.census()
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No constructor writes')):
            reopened=self.parts()
        self.assertEqual(commands,self.commands());self.assertEqual(files,self.census())
        self.peer.events[0]['localOnly']=True
        with self.assertRaises(NativeUIError):reopened['receiver'].sample()
        self.assertEqual(files,self.census())
    def test_unheld_or_foreign_root_lock_and_changed_admitted_candidate_refuse_before_chat(self):
        self.parts();commands=self.commands();files=self.census()
        for overrides in (dict(primary_lock=ScriptSourceLock(self.locks['primary'].path)),
                          dict(peer_root=self.artifacts['primary'])):
            with self.subTest(overrides=overrides),self.assertRaises(NativeUIError):self.parts(**overrides)
        self.sources['primary']['binding']['artifactSha256']='f'*64
        with self.assertRaises((ValueError,RuntimeError)):self.parts()
        self.assertEqual(commands,self.commands());self.assertEqual(files,self.census())
    def test_peer_replacement_after_construction_blocks_cache_dispatch(self):
        parts=self.parts();self.f.fixture.process['pid']=43
        with self.assertRaises((ValueError,RuntimeError)):parts['primary_capture'].observe()
        self.assertEqual(([],[]),self.commands())
    def test_equal_numeric_pids_on_independent_targets_do_not_replace_candidate_admission(self):
        self.sources['primary']['binding']['processIdentity']='42'
        self.sources['primary']['observer'].pid=42;self.primary.mutate=lambda value:value.update(processId=42)
        parts=self.parts();parts['primary_capture'].observe();sample=parts['receiver'].sample()
        self.assertEqual(42,sample['primary']['processId']);self.assertEqual(42,sample['peer']['processId'])
        self.assertNotEqual(sample['primary']['instance'],sample['peer']['instance'])
    def test_peer_retirement_and_primary_retirement_keep_scope_responsibilities_separate(self):
        parts=self.parts();parts['primary_capture'].observe();parts['receiver'].sample();parts['receiver'].retire()
        self.assertTrue(self.primary.present);self.assertFalse(self.peer.present)
        parts['primary_capture'].retire();self.assertFalse(self.primary.present)
        self.assertFalse(owners_absent(self.runtime.adapter,'primary'));self.assertFalse(owners_absent(self.runtime.adapter,'peer'))
    def test_lost_binding_cas_return_leaves_actual_record_without_cache_creation_or_repeated_write(self):
        write=PrivateFeatureState.write
        def lost(store,value,previous):
            result=write(store,value,previous)
            if store.path.name=='ios-chat-receive-binding.json':raise OSError('Declared lost binding CAS return')
            return result
        with patch.object(PrivateFeatureState,'write',new=lost),self.assertRaises(OSError):self.parts()
        saved=PrivateFeatureState(self.paths['peer'].with_name('ios-chat-receive-binding.json')).read()
        self.assertIsNotNone(saved);self.assertEqual(([],[]),self.commands())
        parts=self.parts();self.assertEqual(saved,parts['binding']);self.assertEqual(([],[]),self.commands())
    def test_foreign_or_absent_primary_capture_journal_cannot_admit_retained_pair(self):
        parts=self.parts();parts['primary_capture'].observe();parts['receiver'].sample();commands=self.commands()
        store=parts['primary_capture'].owner.store;previous=store.read()
        store.write(previous|dict(selfSha256='f'*64),previous)
        with self.assertRaises(NativeUIError):self.parts()
        store.write(previous,store.read());store.discard(previous)
        with self.assertRaises(NativeUIError):self.parts()
        self.assertEqual(commands,self.commands())


if __name__=='__main__':unittest.main()
