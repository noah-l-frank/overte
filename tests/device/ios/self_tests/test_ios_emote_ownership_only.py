"""Ownership-only CAS/recovery cannot acquire current native/SDK facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.original_avatar_peer_sources import OriginalAvatarPeerSources
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_sources import IOSEmoteSources,EmotePhaseChanged
from ios.adapters.emote_source_recovery import IOSEmoteSourceRecovery
from ios.self_tests.emote_original_fixtures import Originals
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,frame
from ios.self_tests.test_ios_emote_peer import ACTOR,RUN as PEER_RUN
from ios.self_tests.test_ios_emote_peer_sources import original as peer_original


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.guards=[]
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def guard(self):self.guards.append('existing-process-continuity');return True
    def seed(self,peer=False):
        if not peer:
            fixture=Originals(self.root,self.lock);source=fixture.owner;fixture.append(18800,baseline=True)
            source.state.update(phase='reading',pending=dict(original=None,manifest=None,partial=dict(native=source.frames[-1]['group']['native'])))
        else:
            source=OriginalAvatarPeerSources(PrivateFeatureState(self.root/'ios-emote-actor-peer-sources.json'),self.root,ACTOR,PEER_RUN,None,
                self.lock,self.guard,profile='emote',phase_changed=EmotePhaseChanged,historical=True)
            source.historical=False;source.state['pending']=dict(original=None,manifest=None,partial={})
        source.save();return source
    def owner(self,peer=False,**kwargs):
        if not peer:return IOSEmoteSources(PrivateFeatureState(self.root/'ios-emote-primary-sources.json'),self.root,BINDING,RUN,'primary',
            self.lock,self.guard,None,ownership_only=True,**kwargs)
        return OriginalAvatarPeerSources(PrivateFeatureState(self.root/'ios-emote-actor-peer-sources.json'),self.root,ACTOR,PEER_RUN,None,
            self.lock,self.guard,profile='emote',phase_changed=EmotePhaseChanged,ownership_only=True,**kwargs)
    def test_existing_original_pending_owner_recovers_without_any_reader_or_runtime(self):
        for peer in (False,True):
            with self.subTest(peer=peer):
                source=self.seed(peer);before=deepcopy(source.previous);owner=self.owner(peer)
                recovery=OriginalAvatarPeerRecovery(owner) if peer else IOSEmoteSourceRecovery(owner)
                self.assertTrue(recovery.recover());self.assertIsNone(owner.state['pending']);self.assertEqual(1,len(recovery.state['records']))
                self.assertEqual(before,recovery.record(recovery.state['records'][0])['priorOwner'])
                self.assertEqual(source.frames,owner.frames);self.assertTrue(self.guards)
                self.assertTrue(recovery.recover());self.assertEqual(1,len(recovery.state['records']))
    def test_current_reads_new_originals_and_unjournaled_pending_deletion_are_blocked(self):
        for peer in (False,True):
            source=self.seed(peer);before=source.store.read();owner=self.owner(peer);files=set(self.root.iterdir())
            with self.subTest(peer=peer):
                for operation in (owner.read,lambda:owner.remember('native',{}),lambda:owner.originals.write(len(owner.frames)+1,peer_original() if peer else frame())):
                    with self.assertRaises(NativeUIError):operation()
                self.assertEqual(files,set(self.root.iterdir()));self.assertEqual(before,source.store.read())
                owner.state['pending']=None
                if not peer:owner.state['phase']='ready'
                with self.assertRaises(NativeUIError):owner.save()
                self.assertEqual(before,source.store.read())
    def test_new_metadata_historical_toggle_and_live_reader_attachment_are_not_admitted(self):
        for peer in (False,True):
            with self.subTest(peer=peer),self.assertRaises(NativeUIError):self.owner(peer)
            self.seed(peer)
            with self.subTest(peer=peer),self.assertRaises(NativeUIError):self.owner(peer,historical=True)
            with self.subTest(peer=peer),self.assertRaises(NativeUIError):self.owner(peer,**(dict(runtime=object()) if peer else dict(readers={})))
    def test_even_after_recovery_owner_cannot_mint_a_new_qualified_revision(self):
        for peer in (False,True):
            self.seed(peer);owner=self.owner(peer);recovery=OriginalAvatarPeerRecovery(owner) if peer else IOSEmoteSourceRecovery(owner)
            recovery.recover();before=owner.store.read();owner.state['revision']+=1
            with self.subTest(peer=peer),self.assertRaises(NativeUIError):owner.save()
            self.assertEqual(before,owner.store.read())


if __name__=='__main__':unittest.main()
