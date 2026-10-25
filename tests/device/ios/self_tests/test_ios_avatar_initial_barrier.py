"""Two genuine private initial PNG owners precede ordinary camera work.

Native renderer/application boundaries are modeled producers. The original
PNG/GPU/inode validation, SDK admissions, locks and whole handoff are real.
This qualifies ordering only, not a complete Avatar journey.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_marker_scope import _components
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
from ios.adapters.avatar_peer import session_sha
from ios.self_tests import test_ios_avatar_checkpoint_barrier as sdk_fixture
from ios.self_tests import test_ios_emote_restoration_frames as frames_fixture
from ios.self_tests.test_ios_graphics_measurements import RUN,HOST
from ios.self_tests.test_ios_avatar_renderers import SELF,PEER


class AvatarInitialBarrierTests(unittest.TestCase):
    def setUp(self):
        self.sdk=sdk_fixture.AvatarCheckpointBarrierTests();self.sdk.setUp();self.addCleanup(self.sdk.doCleanups)
        self.owners={};self.frames={};self.native={};self.clock=[10.]
        domain='11111111-1111-4111-8111-111111111111'
        sessions=dict(primary=SELF,actor=PEER)
        for role in ('primary','actor'):
            case=frames_fixture.RawFramesTests();case.setUp();self.addCleanup(case.doCleanups);f=case.fixture;self.native[role]=case
            old=f.scope;scope=object.__new__(IOSAvatarMarkerScope);scope.__dict__.update(old.__dict__)
            scope._marker_components=_components('avatar');scope.binding=deepcopy(self.sdk.bindings[role]);scope.role=role
            scope.fixture_url=self.sdk.client.url+'/runs/'+RUN+'/';scope.lock=self.sdk.owners[role].lock
            scope.bound=scope.lock.assert_held;f.scope=scope
            f.runtime.state_path=lambda _selector,role=role:self.sdk.runtime.state_path(role)
            source=f.runtime._sources
            f.template['worldBefore']['source']['domain']['selfSha256']=session_sha(sessions[role])
            for key in ('renderersBefore','renderersAfter'):
                own=deepcopy(next(row for row in f.template[key]['source']['avatars'] if row['self']))
                own['sessionId']=sessions[role];f.template[key]['source']['avatars']=[own]
            world=f.world
            def avatar_world(run,world=world):
                value=world(run);value['iosAvatarWorldVersion']=value.pop('iosEmoteWorldVersion');value['clockDomain']='native-main-avatar-world';return value
            def bound_source(selector,source=source,world=avatar_world,binding=scope.binding):
                value=source(selector);value['binding']=deepcopy(binding)
                value['observer'].avatar_world=lambda _clock:SimpleNamespace(last=None,read=world)
                return value
            f.runtime._sources=bound_source
            previous=self.sdk.owners[role]
            previous.store.discard(previous.store.read())
            config=dict(artifactRoot=str(f.root),imagePolicy=deepcopy(previous.policy),
                **{('actorTarget' if role=='primary' else 'primaryTarget'):('actor' if role=='primary' else 'primary')})
            if role=='actor':config['authorityRead']=dict(mode='adapter',token='s'*64)
            owner=IOSAvatarFeature(self.sdk.runtime,role,self.sdk.client,RUN,role,config,epoch_ms=lambda:HOST+self.clock[0]*1000,monotonic=lambda:self.clock[0],sleep=lambda _seconds:None)
            scope.lock=owner.lock;scope.bound=owner.lock.assert_held
            refs={s:dict(index=1,sha256='0'*64) for s in ('primary','actor')}
            owner.state=dict(phase='preparing',bindings=deepcopy(self.sdk.bindings),peerAdmission=deepcopy(previous.state['peerAdmission']),phaseInstance=self.sdk.phase,
                initialTicket='b'*32,protected=None,lastCall=None,cleanup=[],snapshots=[],initial=None,initialBarrier=None,preparationClose=None,
                sessions=dict(phase='bound',input=dict(sessions=sessions,domain=domain),sources=deepcopy(refs),peers=deepcopy(refs),
                    authority=dict(sessionBinding=dict(avatarSessionBindingVersion=1,sessions=sessions,domain=domain))))
            with owner.lock.held():
                owner.save()
                frame=IOSAvatarRestorationFrames(f.runtime,'owned',scope,f.root,scope.lock,monotonic=lambda f=f:f.gpu.clock,
                    epoch_ms=lambda f=f:HOST+f.gpu.clock*1000,sleep=lambda duration,f=f:f.gpu.sleep(duration))
                self.frames[role]=frame
            self.owners[role]=owner

    def admit(self,role):
        owner=self.owners[role];frame=self.frames[role]
        with owner.lock.held():
            ref=frame.capture('initial');owner.load();owner.state['initial']=dict(owner=owner.keep(frame.previous),reference=ref);owner.save()
        return ref

    def test_missing_peer_initial_blocks_without_sdk_or_camera_and_retained_pair_is_read_only(self):
        self.admit('primary');primary=self.owners['primary']
        with self.assertRaises(AvatarFeaturePending):primary.wait_peer_initial()
        self.assertIsNone(primary.state['initialBarrier']);self.admit('actor')
        counts={role:sum(len(gpu.commands) for gpu in case.gpus.values()) for role,case in self.native.items()}
        primary.wait_peer_initial();self.owners['actor'].wait_peer_initial()
        self.assertEqual('actor',primary.state['initialBarrier']['subject'])
        self.assertEqual(counts,{role:sum(len(gpu.commands) for gpu in case.gpus.values()) for role,case in self.native.items()})
        primary.wait_peer_initial();self.assertEqual(counts,{role:sum(len(gpu.commands) for gpu in case.gpus.values()) for role,case in self.native.items()})

    def test_peer_initial_cannot_borrow_a_foreign_actual_domain_or_session(self):
        self.admit('primary');self.admit('actor');actor=self.owners['actor'];original=actor.store.read()
        for fault in ('domain','session'):
            with actor.lock.held():
                actor.load();value=actor.state['sessions']
                if fault=='domain':value['input']['domain']='11111111-1111-4111-8111-111111111112'
                else:value['input']['sessions']['actor']='00000000-0000-4000-8000-000000000008'
                value['authority']['sessionBinding']=dict(avatarSessionBindingVersion=1,**deepcopy(value['input']));actor.save()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owners['primary'].wait_peer_initial()
            actor.store.write(original,actor.store.read())


if __name__=='__main__':unittest.main()
