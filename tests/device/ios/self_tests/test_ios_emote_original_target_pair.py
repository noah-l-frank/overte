"""Real Feature2/3 files preserve explicit original selector custody.

Bindings/owner phase are declared codec inputs only; these cases supply no
native, scene, process/SDK end fact and execute no live source transport.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from ios.self_tests.emote_active_actor_fixture import ACTOR


class OriginalTargetPairTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name);self.root.chmod(0o700)
        for name in ('primary-sdk','actor-sdk','primary-art','actor-art','foreign-sdk','foreign-art'):(self.root/name).mkdir(mode=0o700)
        self.paths=dict(primary=self.root/'primary-sdk'/'session.json',actor=self.root/'actor-sdk'/'session.json')
        def state_path(selector):self.assertIn(selector,self.paths);return self.paths[selector]
        def forbidden(*_args,**_kwargs):self.fail('No native/SDK/candidate producer is allowed in codec cases')
        self.runtime=IOSEmoteRuntime(SimpleNamespace(state_path=state_path,_candidate_guard=forbidden,_binding=forbidden))
        self.pair=dict(primaryTarget='primary',actorTarget='actor',primaryArtifactRoot=str(self.root/'primary-art'),actorArtifactRoot=str(self.root/'actor-art'))
        self.policy=dict(source='world-render-target',marker=[0,0,64,32],subject=[0,40,100,100])
        self.state=dict(phase='preparing',binding=deepcopy(ACTOR),primaryBinding=deepcopy(BINDING),actorAdmission=None,
            phaseInstance='c'*32,initialTicket='d'*32,lastCall=None,inputBarrier=None,cleanup=[],retirement=None)
    def owner(self,*,pair=True):
        return IOSEmoteRootedFeature(self.runtime,'actor',Client('http://127.0.0.1:9/feature-fixture/v1','a'*64),RUN,'actor',
            Path(self.pair['actorArtifactRoot']),self.policy,primary_selector='primary',target_pair=self.pair if pair else None)
    def born(self,*,pair=True):
        flow=self.owner(pair=pair)
        with flow.held():flow.state=deepcopy(self.state);flow.save()
        return flow
    def test_profile_three_persists_actual_selected_directories_and_bindings_before_any_live_source(self):
        flow=self.born();value=flow.store.read();self.assertEqual(3,value['iosEmoteFeatureVersion'])
        self.assertEqual(str(self.root/'primary-sdk'),value['targetPair']['primaryStateRoot'])
        self.assertEqual(str(self.root/'actor-sdk'),value['targetPair']['actorStateRoot'])
        self.assertEqual(BINDING,value['targetPair']['primaryBinding']);self.assertEqual(ACTOR,value['targetPair']['actorBinding'])
        raw=flow.store.path.read_bytes();inode=flow.store.path.stat().st_ino
        reopened=self.owner()
        with reopened.held():reopened.load();self.assertEqual(flow.state,reopened.state)
        self.assertEqual(raw,flow.store.path.read_bytes());self.assertEqual(inode,flow.store.path.stat().st_ino)
    def test_literal_profile_two_keeps_no_pair_and_is_not_silently_upgraded(self):
        flow=self.born(pair=False);value=flow.store.read();self.assertEqual(2,value['iosEmoteFeatureVersion']);self.assertNotIn('targetPair',value)
        raw=flow.store.path.read_bytes();inode=flow.store.path.stat().st_ino
        older=self.owner(pair=False)
        with older.held():older.load();self.assertEqual(value,older.previous)
        newer=self.owner()
        with self.assertRaises(NativeUIError),newer.held():newer.load()
        self.assertEqual(raw,flow.store.path.read_bytes());self.assertEqual(inode,flow.store.path.stat().st_ino)
    def test_missing_profile_or_foreign_original_binding_cannot_adopt_feature_three(self):
        flow=self.born();raw=flow.store.path.read_bytes();inode=flow.store.path.stat().st_ino
        legacy=self.owner(pair=False)
        with self.assertRaises(NativeUIError),legacy.held():legacy.load()
        self.assertEqual(raw,flow.store.path.read_bytes());self.assertEqual(inode,flow.store.path.stat().st_ino)
        value=flow.store.read();changed=deepcopy(value);changed['targetPair']['actorBinding']['processIdentity']='999'
        flow.store.write(changed,value);new=self.owner()
        with self.assertRaises(NativeUIError),new.held():new.load()
    def test_actual_selector_directory_rebinding_and_late_pair_drift_refuse_original_rewrite(self):
        flow=self.born();raw=flow.store.path.read_bytes();inode=flow.store.path.stat().st_ino
        self.paths['actor']=self.root/'foreign-sdk'/'session.json'
        # Keep the ORIGINAL store and held SDK descriptor. A new owner would
        # read an empty foreign path and legitimately return state=None.
        with self.assertRaises(NativeUIError),flow.held():flow.load()
        self.paths['actor']=self.root/'actor-sdk'/'session.json'
        flow.configured_pair['actorArtifactRoot']=str(self.root/'foreign-art')
        with self.assertRaises(NativeUIError),flow.held():flow.save()
        self.assertEqual(raw,flow.store.path.read_bytes());self.assertEqual(inode,flow.store.path.stat().st_ino)

    def test_cross_role_artifact_ancestor_roots_refuse_both_directions_before_birth(self):
        original=deepcopy(self.pair)
        for outer,inner in (('primary','actor'),('actor','primary')):
            nested=self.root/(outer+'-art')/'nested-other-art';nested.mkdir(mode=0o700)
            self.pair=deepcopy(original);self.pair[inner+'ArtifactRoot']=str(nested)
            with self.subTest(outer=outer),self.assertRaises(NativeUIError):self.owner()
        self.pair=original
        self.assertFalse(any(self.root.rglob('ios-emote-*-feature.json')))

    def test_artifact_and_other_role_sdk_ancestor_roots_refuse_both_directions(self):
        original=deepcopy(self.pair);paths=dict(self.paths)
        for artifact_role,state_role,artifact_contains in (
                ('primary','actor',True),('primary','actor',False),
                ('actor','primary',True),('actor','primary',False)):
            self.pair=deepcopy(original);self.paths.clear();self.paths.update(paths)
            if artifact_contains:
                nested=Path(self.pair[artifact_role+'ArtifactRoot'])/('nested-'+state_role+'-sdk');nested.mkdir(mode=0o700)
                self.paths[state_role]=nested/'session.json'
            else:
                nested=self.paths[state_role].parent/('nested-'+artifact_role+'-art');nested.mkdir(mode=0o700)
                self.pair[artifact_role+'ArtifactRoot']=str(nested)
            with self.subTest(artifact=artifact_role,state=state_role,artifactContains=artifact_contains):
                flow=self.owner()
                with self.assertRaises(NativeUIError),flow.held():flow.state=deepcopy(self.state);flow.save()
                self.assertFalse(flow.store.path.exists())
        self.pair=original;self.paths.clear();self.paths.update(paths)
        self.assertFalse(any(self.root.rglob('ios-emote-*-feature.json')))
