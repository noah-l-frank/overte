"""Retained original receiver/renderer reads and host-file recovery seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_avatar_peer_sources import OriginalAvatarPeerSources
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_sources import EmotePhaseChanged
from ios.self_tests.test_ios_emote_peer_sources import original
from ios.self_tests.test_ios_emote_peer import ACTOR,RUN


class PeerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.source=self.owner();self.source.historical=False;self.source.save()
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def owner(self,profile='emote',role='actor'):
        return OriginalAvatarPeerSources(PrivateFeatureState(self.root/('ios-'+profile+'-'+role+'-peer-sources.json')),
            self.root,ACTOR,RUN,None,self.lock,lambda:True,profile=profile,phase_changed=EmotePhaseChanged,role=role,historical=True)
    def pending(self,partial=None):
        self.source.state['pending']=dict(original=None,manifest=None,partial=partial or {});self.source.save()
    def append(self,frame):
        self.pending();count=len(self.source.frames);item=self.source.originals.write(count+1,frame)
        refs=self.source.originals.append(self.source.state['manifests'],item);self.source.frames.append(deepcopy(frame))
        self.source.state.update(revision=count+1,manifests=refs,pending=None);self.source.save()
    def test_all_returned_prefixes_are_retained_and_historical_recovery_uses_no_SDK(self):
        before=original();self.append(before);peer=before['peer']
        self.pending(dict(phaseBefore=before['phaseBefore'],phaseAfter=before['phaseAfter'],world=peer['world'],receive=peer['receive'],
            renderers=peer['renderers'],nativeStart=dict(nativeBefore=peer['clockJoin']['nativeBefore']),clockJoin=peer['clockJoin']))
        recovery=OriginalAvatarPeerRecovery(self.source);recovery.recover();self.assertIsNone(self.source.state['pending'])
        self.append(original(True));self.assertTrue(recovery.follow(self.source.frames[-1]))
        def forbidden():raise AssertionError('historical SDK guard')
        self.source.guard=self.source.originals.guard=forbidden
        archive=OriginalAvatarPeerRecovery.archive(recovery.store.read(),self.source)
        self.assertTrue(archive.follow(self.source.frames[-1],historical=True))
        retained=archive.attempt(archive.record(archive.state['records'][0]));self.assertEqual(peer['receive'],retained['pending']['partial']['receive'])
    def test_actual_original_receive_and_renderer_prefix_mutations_never_become_new_ownership(self):
        for profile,key in (('emote','receive'),('avatar','renderers')):
            if profile!='emote':self.source=self.owner(profile);self.source.historical=False;self.source.save()
            before=original();partial=deepcopy(before['peer'][key]);partial['instance']='0'*32
            self.pending({key:partial});recovery=OriginalAvatarPeerRecovery(self.source);recovery.recover()
            later=original(True)
            if profile=='avatar':later['phaseBefore']['area']=later['phaseAfter']['area']='avatar-people'
            self.append(later);self.assertTrue(self.source.validate_frame(later))
            # This later completed original is independently valid. Only its
            # contradiction of an actually returned abandoned source birth
            # must make continuation fail, rather than an invalid frame hash.
            with self.subTest(key=key),self.assertRaises(NativeUIError):recovery.follow(later)
    def test_opened_empty_original_keeps_inode_and_bytes_after_abandonment(self):
        self.pending();intent=self.source.originals.intent
        def interrupted(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='opened':raise OSError('Synthetic lost host write')
        with patch.object(self.source.originals,'intent',side_effect=interrupted),self.assertRaises(OSError):self.source.originals.write(1,original())
        path=next(self.root.glob('emote-peer-frame-*.json'));identity=(path.stat().st_dev,path.stat().st_ino)
        recovery=OriginalAvatarPeerRecovery(self.source);recovery.recover();record=recovery.record(recovery.state['records'][0])
        self.assertEqual(0,record['partialFile']['bytes']);self.assertEqual(identity,(path.stat().st_dev,path.stat().st_ino))
        self.assertTrue(path.exists());self.assertIsNone(self.source.state['pending'])
    def test_foreign_hardlink_and_changed_recovery_record_remain_blocking(self):
        self.pending();intent=self.source.originals.intent
        def interrupted(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='opened':raise OSError('Synthetic interrupted write')
        with patch.object(self.source.originals,'intent',side_effect=interrupted),self.assertRaises(OSError):self.source.originals.write(1,original())
        path=next(self.root.glob('emote-peer-frame-*.json'));link=self.root/'foreign-link';os.link(path,link)
        with self.assertRaises(NativeUIError):OriginalAvatarPeerRecovery(self.source).recover()
        self.assertIsNotNone(self.source.state['pending']);link.unlink();recovery=OriginalAvatarPeerRecovery(self.source);recovery.recover()
        next(self.root.glob('emote-peer-abandoned-*.json')).write_bytes(b'{}')
        with self.assertRaises(NativeUIError):OriginalAvatarPeerRecovery(self.source)
    def test_lost_return_after_actual_source_CAS_adopts_without_new_native_work(self):
        self.pending();recovery=OriginalAvatarPeerRecovery(self.source);save=recovery.save;count=[0]
        def lost():
            count[0]+=1
            if count[0]==3:raise OSError('Synthetic lost recovery return')
            return save()
        with patch.object(recovery,'save',side_effect=lost),self.assertRaises(OSError):recovery.recover()
        self.assertIsNone(self.source.state['pending']);rebuilt=OriginalAvatarPeerRecovery(self.source);self.assertTrue(rebuilt.recover())
        self.assertEqual(1,len(rebuilt.state['records']));self.assertIsNone(rebuilt.state['pending'])
    def test_avatar_primary_and_actor_are_distinct_configured_owners_without_DTO_renaming(self):
        for role in ('primary','actor'):
            self.source=self.owner('avatar',role);self.source.historical=False;self.source.save()
            before=original();before['phaseBefore']['area']=before['phaseAfter']['area']='avatar-people'
            self.pending(dict(receive=before['peer']['receive']));recovery=OriginalAvatarPeerRecovery(self.source);recovery.recover()
            self.assertEqual('avatar',recovery.store.read()['profile']);self.assertEqual(role,recovery.store.read()['role'])
            retained=recovery.attempt(recovery.record(recovery.state['records'][0]))
            self.assertEqual(before['peer']['receive'],retained['pending']['partial']['receive'])


if __name__=='__main__':unittest.main()
