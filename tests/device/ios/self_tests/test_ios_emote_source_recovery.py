"""Interrupted passive native reads and partial host files; no device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_source_recovery import IOSEmoteSourceRecovery
from ios.self_tests.emote_original_fixtures import Originals
from ios.self_tests.test_ios_emote_sources import frame,phase


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.fixture=Originals(self.root,self.lock);self.source=self.fixture.owner
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def pending(self,partial=None):
        self.source.state.update(phase='reading',pending=dict(original=None,manifest=None,partial=partial or {}));self.source.save()
    def test_partial_original_is_retained_and_new_distinct_read_must_extend_native_prefix(self):
        packet=self.fixture.model.native(18800,baseline=True);self.pending(dict(native=packet,phaseBefore=phase(1,90000)))
        recovery=IOSEmoteSourceRecovery(self.source);self.assertTrue(recovery.recover())
        self.assertEqual([],self.source.frames);self.assertEqual('ready',self.source.state['phase'])
        self.fixture.append(18800,baseline=True,phase_offset=2);current=self.source.frames[-1];self.assertTrue(recovery.follow(current))
        altered=deepcopy(current)
        for native in (altered['clockJoin']['nativeBefore'],altered['group']['native'],altered['clockJoin']['nativeAfter']):
            native['animation']['joints'][0][4]+=.1
            native['animation']['history']['frames'][0]['joints'][0]['pose'][4]+=.1
        altered['clockJoin']['originalsSha256']=digest(dict(altered['group'],widgets=altered['widgets'],world=altered['world']))
        self.assertTrue(self.source.validate_frame(altered))
        with self.assertRaises(NativeUIError):recovery.follow(altered)
        retained=self.source.decode(recovery.record(recovery.state['records'][0])['priorOwner'])[0]
        self.assertEqual(packet,retained['pending']['partial']['native'])
    def test_partial_opened_file_inode_and_empty_bytes_remain_owned_without_deletion(self):
        self.pending();original=self.source.originals.intent
        def interrupted(kind,value):
            original(kind,value)
            if kind=='original' and value['phase']=='opened':raise OSError('Synthetic interrupted host frame write')
        with patch.object(self.source.originals,'intent',side_effect=interrupted),self.assertRaises(OSError):self.source.originals.write(1,frame())
        path=next(self.root.glob('emote-frame-*.json'));identity=(path.stat().st_dev,path.stat().st_ino)
        recovery=IOSEmoteSourceRecovery(self.source);recovery.recover();row=recovery.record(recovery.state['records'][0])
        self.assertEqual(0,row['partialFile']['bytes']);self.assertEqual(identity,(path.stat().st_dev,path.stat().st_ino))
        self.assertEqual('ready',self.source.state['phase']);self.assertEqual([],self.source.frames)
        self.assertTrue(IOSEmoteSourceRecovery(self.source).recover());self.assertTrue(path.exists())
    def test_returned_script_roots_widgets_world_and_phase_are_replayed_without_sdk_in_archive(self):
        self.fixture.append(18800,baseline=True);before=self.source.frames[-1]
        self.pending(dict(nativeStart=dict(nativeBefore=before['clockJoin']['nativeBefore']),native=before['group']['native'],
            nativeEnd=dict(nativeAfter=before['clockJoin']['nativeAfter']),script=before['group']['script'],
            rootsBefore=before['group']['rootsBefore'],rootsAfter=before['group']['rootsAfter'],widgets=before['widgets'],
            world=before['world'],phaseAfter=before['phaseAfter']))
        recovery=IOSEmoteSourceRecovery(self.source);recovery.recover();self.fixture.append(20000,active=True)
        self.assertTrue(recovery.follow(self.source.frames[-1]));value=deepcopy(recovery.store.read())
        def forbidden():raise AssertionError('Historical recovery must not call the live SDK guard')
        self.source.guard=self.source.originals.guard=forbidden
        archived=IOSEmoteSourceRecovery.archive(value,self.source)
        self.assertTrue(archived.follow(self.source.frames[-1],historical=True))
    def test_foreign_hardlink_or_changed_partial_inode_blocks_recovery(self):
        self.pending();intent=self.source.originals.intent
        def interrupted(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='opened':raise OSError('Synthetic host write interruption')
        with patch.object(self.source.originals,'intent',side_effect=interrupted),self.assertRaises(OSError):self.source.originals.write(1,frame())
        path=next(self.root.glob('emote-frame-*.json'));os.link(path,self.root/'foreign-link')
        with self.assertRaises(NativeUIError):IOSEmoteSourceRecovery(self.source).recover()
        self.assertEqual('reading',self.source.state['phase']);self.assertEqual(2,path.stat().st_nlink)
    def test_lost_recovery_return_after_actual_source_cas_adopts_without_native_reads(self):
        self.pending();recovery=IOSEmoteSourceRecovery(self.source);save=recovery.save;calls=[]
        def lost():
            calls.append(1)
            if len(calls)==3:raise OSError('Synthetic lost recovery metadata return')
            return save()
        with patch.object(recovery,'save',side_effect=lost),self.assertRaises(OSError):recovery.recover()
        self.assertEqual('ready',self.source.state['phase']);rebuilt=IOSEmoteSourceRecovery(self.source)
        self.assertTrue(rebuilt.recover());self.assertEqual(1,len(rebuilt.state['records']));self.assertIsNone(rebuilt.state['pending'])
    def test_tampered_abandoned_owner_cannot_restore_or_publish_an_old_original(self):
        self.pending();recovery=IOSEmoteSourceRecovery(self.source);recovery.recover()
        path=next(self.root.glob('emote-source-abandoned-*.json'));path.write_bytes(b'{}')
        with self.assertRaises(NativeUIError):IOSEmoteSourceRecovery(self.source)


if __name__=='__main__':unittest.main()
