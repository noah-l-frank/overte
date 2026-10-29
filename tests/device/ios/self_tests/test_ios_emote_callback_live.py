"""Actual Callback Scene4 snapshots in the existing durable live journal.

Native/SDK/Qt/GPU remain declared models. No paired State/terminal/OS/SDK end
is claimed by these original-file/recovery tests or the prospective profile.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import canonical
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_callback_live import IOSEmoteCallbackLive
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters import emote_callback_archive as callback_archive
from ios.adapters import emote_rooted_archive as legacy_archive
from ios.self_tests.emote_callback_scene_fixture import CallbackSceneFixture


class CallbackLiveTests(unittest.TestCase):
    def closed(self):
        f=CallbackSceneFixture(self);f.cleanup();return f

    def queries(self,f):
        return dict(native=len(f.domain.history),inputs=deepcopy(f.domain.io.actions),
            files=deepcopy(f.file_boundary.commands),keys=deepcopy(f.key_domain.commands),
            gpu=[deepcopy(q) for slot in f.t.callback_context.worlds.values() for q in slot.commands])

    def files(self,f):
        return {str(p.relative_to(f.root)):(p.stat().st_dev,p.stat().st_ino,p.read_bytes())
            for p in f.root.rglob('*') if p.is_file()}

    def options(self,live):return dict(store=Frozen(live.store.path,live.previous),lock=live.lock,primary_lock=live.primary_lock)

    def test_actual_archive2_live2_retains_held_scene_idempotently_without_live_query_or_original_rewrite(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);before=self.queries(f)
        row=live.append(f.keyed_ref);self.assertEqual(2,live.previous['iosEmoteRootedLiveVersion'])
        frame=live.read_frame(row['reference']);self.assertEqual(2,frame['iosEmoteRootedLiveRecordVersion'])
        self.assertEqual(2,frame['snapshot']['iosEmoteRootedArchiveVersion'])
        self.assertEqual(4,frame['snapshot']['owners']['native']['iosEmoteRetirementVersion'])
        self.assertEqual(4,frame['snapshot']['owners']['keyed']['iosEmoteKeyedRetirementVersion'])
        self.assertTrue(row['measurement']['public']['resources']);self.assertEqual([],row['measurement']['sourcePublic']['resources'])
        self.assertLess(len(canonical(live.previous)),4096)
        files=self.files(f);self.assertEqual(row,live.append(f.keyed_ref));self.assertEqual(1,len(live.state['records']))
        archive=IOSEmoteCallbackLive.archive(live.previous,**self.options(live))
        self.assertEqual([row],archive.selected_many([row['measurement']['public']]))
        self.assertEqual(before,self.queries(f));self.assertEqual(files,self.files(f));self.assertNotIn('end',row['measurement'])

    def test_saved_original_return_loss_recovers_same_inode_once_without_input_or_new_native_read(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);actual=live.originals.intent;lost=[]
        def interrupted(kind,value):
            result=actual(kind,value)
            if value['phase']=='saved' and not lost:lost.append(deepcopy(value));raise OSError('Actual new-profile saved return lost')
            return result
        live.originals.intent=interrupted
        with self.assertRaises(OSError):live.append(f.keyed_ref)
        self.assertEqual(1,len(lost));path=live.originals.path(lost[0]);identity=(path.stat().st_dev,path.stat().st_ino,path.read_bytes())
        before=self.queries(f);rebuilt=IOSEmoteCallbackLive(f.keyed);row=rebuilt.append(f.keyed_ref)
        self.assertIsNone(rebuilt.state['pending']);self.assertEqual(1,len(rebuilt.state['records']))
        self.assertEqual(identity,(path.stat().st_dev,path.stat().st_ino,path.read_bytes()))
        self.assertEqual([row],rebuilt.selected_many([row['measurement']['public']]))
        self.assertEqual(before,self.queries(f))

    def test_real_opened_empty_original_stays_owned_and_cannot_be_adopted_or_replayed(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);actual=live.originals.intent;lost=[]
        def interrupted(kind,value):
            result=actual(kind,value)
            if value['phase']=='opened' and not lost:lost.append(deepcopy(value));raise OSError('Actual opened before bytes loss')
            return result
        live.originals.intent=interrupted
        with self.assertRaises(OSError):live.append(f.keyed_ref)
        self.assertEqual(1,len(lost));path=live.originals.path(lost[0]);self.assertEqual(0,path.stat().st_size)
        saved=live.store.read();before=self.queries(f);rebuilt=IOSEmoteCallbackLive(f.keyed)
        with self.assertRaises(NativeUIError):rebuilt.recover()
        with self.assertRaises(NativeUIError):rebuilt.append(f.keyed_ref)
        self.assertEqual(saved,live.store.read());self.assertEqual(0,path.stat().st_size);self.assertEqual(before,self.queries(f))

    def test_legacy_live1_and_archive1_refuse_actual_new_owner_snapshot_and_live_envelope(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);row=live.append(f.keyed_ref);snapshot=live.read_frame(row['reference'])['snapshot']
        before=self.queries(f);files=self.files(f)
        with self.assertRaises(NativeUIError):IOSEmoteRootedLive(f.keyed)
        with self.assertRaises(NativeUIError):IOSEmoteRootedLive.archive(live.previous,**self.options(live))
        with self.assertRaises(NativeUIError):legacy_archive.reopen(snapshot,lock=f.lock,primary_lock=f.lock)
        old=deepcopy(snapshot);old['iosEmoteRootedArchiveVersion']=1
        with self.assertRaises(NativeUIError):callback_archive.reopen(old,lock=f.lock,primary_lock=f.lock)
        self.assertEqual(before,self.queries(f));self.assertEqual(files,self.files(f))

    def test_same_body_live_original_inode_replacement_cannot_borrow_saved_compact_reference(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);row=live.append(f.keyed_ref)
        path=live.originals.path(live.originals.expand(row['reference']));raw=path.read_bytes();old=(path.stat().st_dev,path.stat().st_ino)
        replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
        self.assertNotEqual(old,(path.stat().st_dev,path.stat().st_ino));self.assertEqual(raw,path.read_bytes());before=self.queries(f)
        with self.assertRaises(NativeUIError):IOSEmoteCallbackLive(f.keyed)
        self.assertEqual(before,self.queries(f))

    def test_scoped_archive_clears_on_error_and_refuses_same_inode_mutation_on_exit(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);row=live.append(f.keyed_ref);before=self.queries(f)
        class Interrupted(Exception):pass
        with self.assertRaises(Interrupted):
            with IOSEmoteCallbackLive.archive_scope(live.previous,**self.options(live)) as archive:
                prepared=archive.prepared;self.assertEqual(row,archive.record(row['reference']));raise Interrupted('Original consumer exit')
        self.assertFalse(prepared.active);self.assertIsNone(archive.prepared)
        with self.assertRaises(NativeUIError):prepared.guard()
        path=live.originals.path(live.originals.expand(row['reference']));raw=path.read_bytes()
        with self.assertRaises(NativeUIError):
            with IOSEmoteCallbackLive.archive_scope(live.previous,**self.options(live)) as archive:
                self.assertEqual(row,archive.record(row['reference']));path.write_bytes(raw)
        self.assertEqual(raw,path.read_bytes());self.assertIsNone(archive.prepared);self.assertEqual(before,self.queries(f))

    def test_current_append_refuses_missing_actual_keyed_member_after_an_earlier_valid_live_cut(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);row=live.append(f.keyed_ref);before=self.queries(f)
        with patch.dict(f.keyed.state,records=[]),self.assertRaises(NativeUIError):live.append(f.keyed_ref)
        self.assertEqual(1,len(live.state['records']));self.assertEqual([row],live.selected_many([row['measurement']['public']]))
        self.assertEqual(before,self.queries(f))

    def test_unknown_live_original_prefix_refuses_before_any_capture_or_archive_adoption(self):
        f=self.closed();live=IOSEmoteCallbackLive(f.keyed);live.append(f.keyed_ref)
        orphan=f.root/('emote-rooted-live-frame-inputs-'+live.run+'-'+live.role+'-0002-'+'f'*64+'.json')
        orphan.write_bytes(b'{}');orphan.chmod(0o600);before=self.queries(f)
        with self.assertRaises(NativeUIError):IOSEmoteCallbackLive(f.keyed)
        self.assertEqual(b'{}',orphan.read_bytes());self.assertEqual(before,self.queries(f))


if __name__=='__main__':unittest.main()
