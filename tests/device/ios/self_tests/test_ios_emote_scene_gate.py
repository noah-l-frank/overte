"""Real private records/locks/admission; native endpoints explicitly modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import validate as native_packet,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_scene_gate import IOSEmoteSceneGate
from ios.adapters.peer_admission import admit_existing_peer
from ios.self_tests.emote_whole_primary_fixture import WholePrimaryFixture
from ios.self_tests.emote_active_actor_fixture import ACTOR
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from self_tests.test_native_feature_observation import Boundary


class SceneGateTests(unittest.TestCase):
    def setUp(self):
        self.f=WholePrimaryFixture(self);f=self.f
        self.roots=dict(primary=f.target.root,actor=f.installed.store.path.parent);self.bindings=dict(primary=BINDING,actor=ACTOR)
        self.stores={role:PrivateFeatureState(f.runtime.state_path(role).with_name('ios-emote-'+role+'-scene-gate.json')) for role in self.roots}
        self.locks=dict(primary=f.target.lock,actor=ScriptSourceLock(f.runtime.state_path('actor').with_name('script-feature-sources.lock')))
        self.admissions={role:admit_existing_peer(f.runtime,'actor' if role=='primary' else 'primary',self.bindings[role],
            epoch_ms=f.target.scope.epoch_ms,monotonic=f.target.scope.monotonic) for role in self.roots}
        self.sources={role:Boundary() for role in self.roots};self.instance=f.target.phase.previous['instance'];self.ticket=f.target.ticket
        self.gates={}
        for role in self.roots:
            self.gates[role]=IOSEmoteSceneGate(self.stores[role],self.roots[role],self.bindings[role],RUN,role,self.instance,
                self.admissions[role],self.stores['actor' if role=='primary' else 'primary'],self.locks[role],self.locks['primary'],lambda:True,
                check=lambda:None,monotonic=f.target.scope.monotonic,validate_original=self.proof,validate_ack=self.ack)
        fixture=f.target.f.fixture;fixture.held.__exit__(None,None,None);fixture.held=nullcontext()
    def proof(self,value,**kwargs):
        need(set(value)=={'packet'});p=value['packet'];native_packet(p,p['requestId'],int(kwargs['binding']['processIdentity']),p['capturedEpochMs'])
        return dict(nativeEndpoint=deepcopy(p),binding=deepcopy(kwargs['binding']),stage=kwargs['stage'])
    def ack(self,value,**kwargs):return self.proof(value,**dict(kwargs,stage='ack'))['nativeEndpoint']
    def endpoint(self,role):
        source=self.sources[role];source.send(dict(commandId='ios-'+format(source.sequence+1,'032x')));p=deepcopy(source.sample)
        p['processId']=int(self.bindings[role]['processIdentity']);p['animation'].update(overrideActive=False);p['animation'].pop('clip',None)
        return dict(packet=p)
    def write(self,role,stage):
        with self.locks[role].held():return self.gates[role].retain('own',stage,self.ticket,self.endpoint(role))
    def read(self,role,stage):
        gate=self.gates[role];candidate=gate.candidate(stage,self.ticket)
        if candidate is not None:
            with self.locks[role].held():
                try:return gate.qualified(stage,self.ticket)['peer']
                except NativeUIError:pass
                return gate.admit(stage,self.ticket,candidate,self.endpoint(role))
    def test_both_initials_before_camera_and_both_endpoints_before_any_cleanup_fence(self):
        p,a=self.gates['primary'],self.gates['actor'];self.write('primary','initial')
        self.assertIsNone(self.read('primary','initial'))
        with self.locks['primary'].held(),self.assertRaises(NativeUIError):p.ready('initial',self.ticket)
        self.write('actor','initial');self.read('actor','initial');self.read('primary','initial')
        for role in self.roots:
            with self.locks[role].held():self.assertTrue(self.gates[role].ready('initial',self.ticket))
        self.write('actor','scene-retired');self.assertIsNone(self.read('actor','scene-retired'))
        with self.locks['actor'].held(),self.assertRaises(NativeUIError):a.ready('scene-retired',self.ticket)
        self.write('primary','scene-retired');self.read('primary','scene-retired');self.read('actor','scene-retired')
        for role in self.roots:
            with self.locks[role].held():self.assertTrue(self.gates[role].ready('scene-retired',self.ticket))
    def test_candidate_wait_refuses_either_actual_source_lock_and_foreign_process(self):
        self.write('actor','initial');p=self.gates['primary']
        for role in self.roots:
            with self.locks[role].held(),self.assertRaises(NativeUIError):
                (p if role=='primary' else self.gates['actor']).candidate('initial',self.ticket)
        value=self.stores['actor'].read();changed=deepcopy(value);changed['binding']['processIdentity']='43';self.stores['actor'].write(changed,value)
        with self.assertRaises(NativeUIError):p.candidate('initial',self.ticket)
    def test_lost_host_original_return_adopts_exact_ready_without_new_endpoint(self):
        gate=self.gates['primary'];write=gate.files.write
        def lost(*args):result=write(*args);raise OSError('Lost original carrier return')
        original=self.endpoint('primary')
        with self.locks['primary'].held():
            with patch.object(gate.files,'write',lost),self.assertRaises(OSError):gate.retain('own','initial',self.ticket,original)
            before=self.sources['primary'].sequence;self.assertTrue(gate.resolve());self.assertEqual(before,self.sources['primary'].sequence)
            self.assertEqual(1,len(gate.state['own']));gate.decode(gate.store.read())
    def test_peer_snapshot_growth_keeps_same_initial_reference_and_archive_never_reads_new_peer_state(self):
        for role in self.roots:self.write(role,'initial')
        first=self.read('primary','initial');self.read('actor','initial');again=self.read('primary','initial');self.assertEqual(first,again)
        gate=self.gates['primary']
        with self.locks['primary'].held():
            saved=gate.store.read();archived=IOSEmoteSceneGate.archive(saved,store=gate.store,root=gate.root,binding=gate.binding,run=RUN,
                role='primary',instance=self.instance,admission=gate.admission,peer_store=gate.peer_store,
                lock=gate.lock,primary_lock=gate.primary_lock,validate_original=self.proof,validate_ack=self.ack)
            archived.qualified('initial',self.ticket)
            with self.assertRaises(NativeUIError):archived.retain('own','initial',self.ticket,self.endpoint('primary'))
        with self.assertRaises(NativeUIError):archived.candidate('initial',self.ticket)

    def test_second_actual_peer_stage_replays_root_identity_without_json_encoding_path_objects(self):
        for stage in ('initial','scene-retired'):
            for role in self.roots:self.write(role,stage)
            for role in self.roots:self.read(role,stage)
        for role in self.roots:
            gate=self.gates[role]
            with self.locks[role].held():
                self.assertEqual(2,len(gate.decode(gate.store.read())['peer']))
                gate.ready('scene-retired',self.ticket)
