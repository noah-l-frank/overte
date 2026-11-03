"""Original early pair/config ownership, not process/SDK or whole end proof.

The selected source/binding inputs are declared models. Actual original frames,
closed Files3 metadata and historical reader/lock/file validation execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_files import IOSAssetsFiles,OwnedAssetsFiles
from ios.adapters.assets_end_selection import construct
from ios.adapters.assets_end_graph import selection
from ios.adapters.assets_end_metadata import RecordingAssetsMetadata
from ios.adapters.assets_selected_profile import SelectedAssetsFiles
from ios.adapters.assets_session_owners import inspect_directory
from ios.adapters.installed_code import SDK
from ios.self_tests.assets_picker_fixture import BINDING,RUN,TICKET,URL


class AssetsSelectedEndProfileTests(unittest.TestCase):
    def setUp(self):
        self.roots={};self.locks={};self.native_calls=[]
        for role in ('primary','actor'):
            d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);root=Path(d.name);root.chmod(0o700);self.roots[role]=root
            lock=ScriptSourceLock(root/'script-feature-sources.lock');held=lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None);self.locks[role]=lock
        actor=dict(BINDING,processIdentity='43',targetFingerprint='9'*64,sessionId='actual-peer-boundary')
        source=dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance='c'*32,available=True,cleanupPending=False,sdk=dict(SDK))
        self.context=dict(assetsPairedEndContextVersion=1,runId=RUN,fixtureUrl=URL,initialTicket=TICKET,inputPhaseOriginal=dict(fixturePhaseVersion=1,instance='7'*32,sequence=1,requestId='8'*32,
            runId=RUN,area='assets',capturedEpochMs=1900000000000,active=True,createdEpochMs=1900000000000,retiredEpochMs=None,
            activations=[dict(sequence=1,ticket=TICKET,activatedEpochMs=1900000000000,stimulus=dict(verb='baseline',inputs={}))]),roles={})
        for role,bound in (('primary',BINDING),('actor',actor)):
            self.context['roles'][role]=dict(target=role,artifactRoot=str(self.roots[role]),stateRoot=str(self.roots[role]),
                binding=deepcopy(bound),source=deepcopy(source),bundleId='io.overte.fixture-only')
        self.file_store=PrivateFeatureState(self.roots['primary']/('ios-assets-'+RUN+'-primary-files.json'))
        self.store=PrivateFeatureState(self.roots['primary']/('ios-assets-'+RUN+'-primary-final.json'))
    def archive(self):return construct(self.store,self.context,self.locks,[self.file_store])
    def no_native(self,*args,**kwargs):self.native_calls.append(True);raise AssertionError('Selection cannot send/acquire native facts')
    def files(self,selected):
        native=IOSAssetsFiles(self.no_native,self.no_native,lambda:1900000000000,lambda:True,42,monotonic=lambda:0.,sleep=self.no_native)
        return SelectedAssetsFiles(native,self.file_store,BINDING,RUN,URL,lock=self.locks['primary'],selection=selected)

    def test_selection_is_original_in_same_archive_before_first_files_owner_and_cold_reopen_is_readonly(self):
        selected=self.archive();selected.select();reference=deepcopy(selected.link());owner=self.files(selected);owner.reserve(TICKET)
        self.assertEqual(3,owner.previous['iosAssetsFileOwnerVersion']);self.assertEqual(reference,owner.previous['selectedPair'])
        before={str(p):(p.read_bytes(),p.stat().st_ino) for root in self.roots.values() for p in root.iterdir() if p.is_file()}
        reopened=self.archive();reopened.select();restored=self.files(reopened)
        self.assertEqual(owner.state,restored.state);self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_ino) for root in self.roots.values() for p in root.iterdir() if p.is_file()})
        self.assertEqual([],self.native_calls)

    def test_existing_unselected_assets_owner_blocks_selection_before_header_or_original_birth(self):
        self.file_store.write(dict(actual='unselected old owner'),None);before=self.file_store.read()
        with self.assertRaises(NativeUIError):self.archive().select()
        self.assertEqual(before,self.file_store.read());self.assertIsNone(self.store.read());self.assertFalse(any(self.roots['primary'].glob('assets-end-selection-*')))

    def test_original_same_body_foreign_inode_cannot_reopen_selected_pair_or_files(self):
        selected=self.archive();selected.select();ref=selected.selection_state['reference'];path=selected.selection_frames.path(selected.selection_frames.expand(ref))
        body=path.read_bytes();before=path.stat();path.rename(path.with_name('retained-selection-before-inode-change'));path.write_bytes(body);path.chmod(0o600)
        self.assertNotEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):selected.selected_guard()
        with self.assertRaises(NativeUIError):self.files(self.archive())
        self.assertEqual([],self.native_calls)

    def test_same_inode_selection_body_change_cannot_grant_files_owner(self):
        selected=self.archive();selected.select();ref=selected.selection_state['reference'];path=selected.selection_frames.path(selected.selection_frames.expand(ref));before=path.stat()
        path.write_bytes(path.read_bytes()+b' ');self.assertEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.files(selected)
        self.assertIsNone(self.file_store.read());self.assertEqual([],self.native_calls)

    def test_legacy_file_owner_cannot_be_retroactively_migrated_into_selected_three(self):
        selected=self.archive();selected.select();owner=self.files(selected)
        legacy=OwnedAssetsFiles(owner.native,self.file_store,BINDING,RUN,URL,lock=self.locks['primary']);legacy.reserve(TICKET)
        before=self.file_store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.files(selected)
        self.assertEqual(before,self.file_store.path.read_bytes());self.assertEqual(2,legacy.previous['iosAssetsFileOwnerVersion'])

    def test_historical_files3_requires_independent_selected_authority_and_keeps_input_duty(self):
        selected=self.archive();selected.select();self.files(selected).reserve(TICKET)
        with self.assertRaises(NativeUIError):inspect_directory(self.roots['primary'])
        view=RecordingAssetsMetadata(owned=selected.owned_paths(),selection=selected)
        rows=inspect_directory(self.roots['primary'],metadata=view);view.guard()
        self.assertEqual(['input-files'],rows[0]['responsibilities']);self.assertFalse(rows[0]['clientRetired'])
        self.assertEqual([],self.native_calls)

    def test_foreign_selected_original_reference_cannot_replace_files_link(self):
        selected=self.archive();selected.select();owner=self.files(selected);owner.reserve(TICKET)
        value=deepcopy(owner.previous);value['selectedPair']['contextSha256']='0'*64;self.file_store.write(value,owner.previous)
        with self.assertRaises(NativeUIError):self.files(selected)
        self.assertEqual(value,self.file_store.read());self.assertEqual([],self.native_calls)

    def test_lost_planned_selection_write_stays_owned_and_cold_open_cannot_adopt_it(self):
        selected=self.archive();actual=selected.selection_frames.intent
        def lost(event,wire):
            result=actual(event,wire)
            if wire['phase']=='planned':raise NativeUIError('Declared original selection write interrupted before open')
            return result
        selected.selection_frames.intent=lost
        with self.assertRaises(NativeUIError):selected.select()
        before=self.store.path.read_bytes()
        self.assertEqual('planned',selected.selection_state['pending']['phase'])
        with self.assertRaises(NativeUIError):self.archive().select()
        self.assertEqual(before,self.store.path.read_bytes());self.assertIsNone(self.file_store.read())
        self.assertFalse(any(self.roots['primary'].glob('assets-end-selection-frame-*')))
        self.assertEqual([],self.native_calls)

    def test_lock_named_nested_orphan_is_not_the_actual_selected_held_lock(self):
        from ios.adapters.assets_end_graph import inventory
        nested=self.roots['primary']/'foreign';nested.mkdir(mode=0o700)
        path=nested/'script-feature-sources.lock';path.write_bytes(b'');path.chmod(0o600)
        found=inventory(self.roots.values(),locks=self.locks.values())
        self.assertEqual({path},found)
        self.assertTrue(all(lock.path not in found for lock in self.locks.values()))
        self.assertIsNone(self.store.read());self.assertEqual([],self.native_calls)

    def test_cross_role_nested_root_or_duplicate_selector_is_refused_before_owner_birth(self):
        for fault in ('nested','same-selector'):
            value=deepcopy(self.context)
            if fault=='nested':
                path=self.roots['primary']/'actor-nested';path.mkdir(mode=0o700);value['roles']['actor'].update(artifactRoot=str(path),stateRoot=str(path))
            else:value['roles']['actor']['target']=value['roles']['primary']['target']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):selection(value)
        self.assertIsNone(self.store.read());self.assertEqual([],self.native_calls)


if __name__=='__main__':unittest.main()
