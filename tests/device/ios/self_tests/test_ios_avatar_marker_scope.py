"""Avatar marker-only normal input/quiet owners; native/rendering are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import hashlib
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.normal_script_manager import NormalScriptManager
from adapters.token_script_ui import TokenScriptUI
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.original_marker_scope import OriginalMarkerScope
from adapters.original_marker_recovery import OriginalMarkerRecovery
from adapters.script_feature.history import pack
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_marker_files import OwnedAvatarMarkerFiles
from ios.adapters.avatar_marker_recovery import IOSAvatarMarkerRecovery
from ios.adapters.avatar_originals import IOSAvatarOriginals
from ios.self_tests import test_ios_emote_marker_scope as old_fixture
from ios.self_tests.emote_marker_domain_fixture import RunningDomain


class AvatarDomain(RunningDomain):
    def __init__(self,scope):
        super().__init__(scope)
        # These are synthetic producer schema boundaries, never rewritten live
        # originals. The staged Avatar marker code still executes in actual Node.
        self.world_template['iosAvatarWorldVersion']=self.world_template.pop('iosEmoteWorldVersion')
        self.world_template['clockDomain']='native-main-avatar-world'
        self.identity='00000000-0000-4000-8000-000000000001'
        self.world_template['source']['domain']['selfSha256']=hashlib.sha256(uuid.UUID(self.identity).bytes).hexdigest()
    def world(self,run):
        value=super().world(run)
        value['source']['bodies']=dict(avatarBodyCollectionVersion=1,instance='e'*32,sequence=value['sequence'],
            capturedEpochMs=value['clockAfter']['epochMs'],complete=True,avatars=[dict(sessionId=self.identity,self=True,replicated=False,
                position=[0,0,4],orientation=[0,0,0,1],velocity=[0,0,0])])
        return value
    def widgets(self):
        p=super().widgets();p['avatarControlsVersion']=1
        p['avatarGeneration']=p.pop('emoteGeneration');p['avatarSourceSequence']=p.pop('emoteSourceSequence')
        del p['emoteControlsVersion'];del p['emoteInventory'];return p
    def manager(self):
        s=self.scope;ui=TokenScriptUI(self.io,monotonic=lambda:self.time,sleep=self.io.sleep)
        picker=TokenScriptFilePicker(self.io,self.files.root.as_uri(),monotonic=lambda:self.time,sleep=self.io.sleep)
        return NormalScriptManager(ui,self.io.observe,PrivateFeatureState(s.store.path.with_name('ios-avatar-'+s.role+'-marker-script.json')),
            s.binding,source_kind='script-file-bundle',file_owner=s.files,file_picker=picker,monotonic=lambda:self.time,sleep=self.io.sleep)


class AvatarMarkerScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=old_fixture.MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.scope=self.owner();self.domain=AvatarDomain(self.scope)
    def owner(self):
        # The old fixture supplies only neutral binding/lock/journal scaffolding.
        s=self.fixture.owner();s.__class__=IOSAvatarMarkerScope
        s.store=PrivateFeatureState(s.root/'ios-avatar-primary-marker.json')
        s.files=OwnedAvatarMarkerFiles(None,PrivateFeatureState(s.root/'ios-avatar-primary-marker-files.json'),s.binding)
        s.originals=IOSAvatarOriginals(s.root,s.binding,s.run,s.role,s.guard,s.storage_intent,kind='inputs')
        s.previous=s.store.read()
        if s.previous is not None:s.state=s.decode(s.previous)
        return s
    def test_actual_avatar_marker_code_newly_observed_UUID_view_and_three_second_cleanup_retire_once(self):
        owned=self.scope.prepare();self.assertIn('avatar-marker-v1',self.domain.vm['added'][0]['properties']['userData'])
        self.assertEqual(owned['marker']['id'],self.domain.vm['added'][0]['id'])
        self.domain.paint();self.scope.admit_rendered();snapshot=self.scope.snapshot()
        retained=IOSAvatarMarkerScope.archive(snapshot,root=self.scope.root,binding=self.scope.binding,run=self.scope.run,
            role=self.scope.role,lock=self.scope.lock,require_ready=True)
        self.assertEqual(owned['marker']['sourceUrl'],retained.bind_image_world(self.scope.frames[-1]['world'])['url'])
        self.assertEqual({'performed':True},self.scope.cleanup());self.assertFalse(self.domain.files.root.exists())
        first=self.scope.frames[self.scope.state['quiet'][0]-1];last=self.scope.frames[-1]
        self.assertGreaterEqual(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic'],3)
        self.assertGreaterEqual(last['world']['clockBefore']['monotonicMs']-first['world']['clockAfter']['monotonicMs'],3000)
        actions=list(self.domain.io.actions);self.scope.cleanup();self.assertEqual(actions,self.domain.io.actions)
        self.assertEqual(self.scope.frames,self.owner().frames)
    def test_image_marker_context_allows_actual_scale_and_missing_mesh_but_requires_actual_root_continuity(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered()
        self.domain.world_template['source']['avatar'].update(modelScale=1.5,feetPosition=[0,2,4],boundsReady=False,bounds=None)
        actual=self.scope.capture('actual-missing-avatar');self.scope.bind_image_world(actual['world'])
        for fault in ('missing','moved'):
            wrong=deepcopy(actual['world'])
            if fault=='missing':del wrong['source']['bodies']
            else:wrong['source']['bodies']['avatars'][0]['position'][0]+=.1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.scope.bind_image_world(wrong)

    def test_lost_normal_stop_reconstructs_and_never_resends(self):
        self.scope.prepare();self.domain.paint();self.scope.admit_rendered();activate=self.domain.io.activate
        def lost(identifier,**kwargs):
            activate(identifier,**kwargs)
            if identifier=='scripts.stop.0':raise NativeUIError('synthetic lost stop')
        with patch.object(self.domain.io,'activate',side_effect=lost),self.assertRaises(NativeUIError):self.scope.cleanup()
        rebuilt=self.owner();self.domain.attach(rebuilt);self.assertEqual({'performed':True},rebuilt.cleanup())
        self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))
    def test_lost_passive_read_keeps_avatar_namespaced_original_prefix_without_resend(self):
        self.domain.web_failure=True
        with self.assertRaises(OSError):self.scope.capture('abandoned-avatar-read')
        old=deepcopy(self.scope.state['pending']['partial']['world']);self.domain.web_failure=False
        actual=self.scope.capture('new-avatar-read');recovery=IOSAvatarMarkerRecovery(self.scope)
        self.assertEqual(1,len(recovery.state['records']));r=recovery.record(recovery.state['records'][0])
        self.assertEqual(old,recovery.prior(r['priorOwner'])['pending']['partial']['world'])
        self.assertEqual(1,r['iosAvatarMarkerAbandonedReadVersion']);self.assertNotEqual(old['requestId'],actual['world']['requestId'])
        self.assertTrue((self.scope.root/('avatar-marker-read-abandoned-'+self.scope.run+'-primary-1.json')).exists())
    def test_actual_worker_that_ended_before_stop_retires_with_terminal_originals(self):
        self.scope.prepare();self.domain.stop();self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertEqual('finished-execution',self.scope.state['cleanupMode']);self.assertNotIn('scripts.stop.0',self.domain.io.actions)
        self.assertEqual(1,self.scope.state['admission']['iosAvatarPartialMarkerVersion'])
    def test_avatar_scope_rejects_emote_envelope_and_profile_instead_of_relabelling(self):
        original=self.fixture.owner();original.save()
        with self.assertRaises(NativeUIError):self.scope.decode(original.snapshot())
        with self.assertRaises(NativeUIError):IOSAvatarMarkerRecovery(original)
        with self.assertRaises(NativeUIError):OriginalMarkerScope.archive(original.snapshot(),root=self.scope.root,
            binding=self.scope.binding,run=self.scope.run,role=self.scope.role,lock=self.scope.lock)


class GenericEmoteScope(OriginalMarkerScope):PROFILE='emote'


class OriginalMarkerCompatibilityTests(unittest.TestCase):
    def test_explicit_frozen_emote_v1_envelope_reads_unchanged_without_writer_or_live_SDK(self):
        f=old_fixture.MarkerScopeTests();f.setUp();self.addCleanup(f.tearDown)
        original=f.owner()
        # Literal original v1 shape; neither new facade nor generic owner writes
        # this legacy fixture. No original frame/inode is invented for zero reads.
        state=dict(phase='new',revision=0,manifests=[],pending=None,baseline=None,admission=None,admissionFrame=None,
            loadBarrier=None,stopBarrier=None,webAdmission=None,directory=None,fileOwnership=None,operations=[],
            leases=dict(tablet=False,address=False,menu=False),quiet=[],cleanupMode='full')
        value=dict(iosEmoteMarkerScopeVersion=1,runId=original.run,role='primary',binding=original.binding,
            artifactRoot=str(original.root),fixtureUrl=original.fixture_url,ticket=original.ticket,payload=pack([state]))
        scope=GenericEmoteScope.archive(value,root=original.root,binding=original.binding,run=original.run,role='primary',lock=original.lock)
        self.assertEqual(value,scope.envelope(scope.state));self.assertEqual('emote',scope.components.profile)
    def test_original_emote_ready_source_and_actual_files_are_accepted_without_rewrite(self):
        f=old_fixture.MarkerScopeTests();f.setUp();self.addCleanup(f.tearDown)
        old=f.owner();domain=RunningDomain(old);old.prepare();domain.paint();old.admit_rendered();value=old.snapshot()
        actual_files={p.name:(p.stat().st_ino,p.read_bytes()) for p in old.root.glob('emote-inputs-*') if p.is_file()}
        archive=GenericEmoteScope.archive(value,root=old.root,binding=old.binding,run=old.run,role=old.role,lock=old.lock,require_ready=True)
        self.assertEqual(old.frames,archive.frames);self.assertEqual(value,archive.envelope(archive.state))
        self.assertEqual(actual_files,{p.name:(p.stat().st_ino,p.read_bytes()) for p in old.root.glob('emote-inputs-*') if p.is_file()})


if __name__=='__main__':unittest.main()
