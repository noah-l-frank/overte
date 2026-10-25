"""Actual private handoff/installed-code files; checkpoint producer is modeled.

The handoff is scheduling metadata only. These tests establish no Avatar fact,
scene cleanup or complete feature result from a peer's stored checkpoint.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from feature_journeys.witness import Client
from ios.adapters import avatar_operation_clock
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.peer_admission import admit_existing_peer
from ios.self_tests import test_ios_installed_code as installed


class AvatarCheckpointBarrierTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.epoch=100000.;self.mono=10.;self.run='a'*32;self.ticket='c'*32;self.phase='d'*32;self.installed={};self.bindings={}
        for role in ('primary','actor'):
            directory=self.root/role;directory.mkdir(mode=0o700)
            f=installed.InstalledCodeTests();f.setUp();self.addCleanup(f.doCleanups)
            f.scope=dict(f.scope,sessionId='sdk-'+role,targetFingerprint=('b' if role=='primary' else 'c')*64)
            f.binding=f.make();f.active();self.installed[role]=f;self.bindings[role]=dict(f.scope,processIdentity='42')
        fixture=self
        class Runtime(IOSAvatarRuntime):
            def state_path(_self,selector):return fixture.root/selector/'session.json'
            def _sources(_self,_selector):raise AssertionError('A private checkpoint barrier must never query either SDK')
            def _existing(_self,selector):
                scope=fixture.installed[selector].scope
                return None,scope['sessionId'],dict(sessionId=scope['sessionId']),{},deepcopy(scope)
        adapter=SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda selector,*_args:self.installed[selector].make())
        self.runtime=Runtime(adapter);self.client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
        self.client.request=lambda *_args,**_kwargs:(_ for _ in ()).throw(AssertionError('A private checkpoint barrier uses no HTTP'))
        self.owners={}
        for role in ('primary','actor'):
            other='actor' if role=='primary' else 'primary';config=dict(artifactRoot=str(self.root/role),imagePolicy=dict(source='world-render-target',marker=[0,0,32,32],subject=[64,64,96,96]),
                **{('actorTarget' if role=='primary' else 'primaryTarget'):other})
            if role=='actor':config['authorityRead']=dict(mode='adapter',token='s'*64)
            owner=IOSAvatarFeature(self.runtime,role,self.client,self.run,role,config,epoch_ms=lambda:self.epoch,monotonic=lambda:self.mono)
            admission=admit_existing_peer(self.runtime,other,self.bindings[role],epoch_ms=lambda:self.epoch,monotonic=lambda:self.mono)
            original=OriginalFrameStore(self.root/role,self.bindings[role],self.run,role,lambda:True,lambda *_:None,
                namespace='avatar-observation',schema_prefix='avatarObservation')
            record=dict(iosAvatarObservationRecordVersion=1,index=1,ticket=self.ticket,status='observed',partial={},components={},
                facts=dict(phaseInstance=self.phase,ticket=self.ticket),abandonment=None)
            ref=dict(index=1,ticket=self.ticket,status='observed',original=original.write(1,record))
            owner.state=dict(phase='cleaning',bindings=deepcopy(self.bindings),peerAdmission=admission,phaseInstance=self.phase,initialTicket='b'*32,
                protected=None,sessions=None,lastCall=None,snapshots=[],initial=None,initialBarrier=None,preparationClose=None,cleanup=[dict(kind='admission',ticket=self.ticket,
                    baseline=dict(index=1,sha256='0'*64),source=dict(index=1,sha256='0'*64),operationClock=avatar_operation_clock.begin(self.epoch,self.mono)),
                    dict(kind='checkpoint',reference=ref,published=role=='actor',publisher=None)])
            with owner.lock.held():
                if role=='actor':owner.state['cleanup'][-1]['publisher']=owner.keep(dict(syntheticCheckpointPublisher=True))
                owner.save()
            self.owners[role]=owner

    def test_both_roles_retain_exact_admitted_peer_checkpoint_without_sdk_or_http_and_reopen_it(self):
        actor=self.owners['actor'];primary=self.owners['primary'];value=actor.wait_peer_checkpoint()
        self.assertEqual('primary',value['subject']);self.assertEqual(self.ticket,value['reference']['ticket'])
        self.assertEqual(value,actor.wait_peer_checkpoint())
        reverse=primary.wait_peer_checkpoint();self.assertEqual('actor',reverse['subject'])
        self.assertEqual(value,actor.state['cleanup'][-1]);self.assertEqual(reverse,primary.state['cleanup'][-1])
        # Later peer metadata cannot rewrite the actually retained handoff.
        with primary.lock.held():primary.load();primary.state['lastCall']=None;primary.save()
        self.assertEqual(value,actor.wait_peer_checkpoint())

    def test_changed_pair_phase_ticket_or_actual_original_file_refuses_handoff(self):
        primary=self.owners['primary'];original=deepcopy(primary.store.read())
        for fault in ('binding','phase','ticket','hash'):
            with self.subTest(fault=fault),primary.lock.held():
                primary.load()
                if fault=='binding':primary.state['bindings']['primary']['sessionId']='replacement-sdk'
                elif fault=='phase':primary.state['phaseInstance']='e'*32
                elif fault=='ticket':primary.state['cleanup'][0]['ticket']='f'*32
                else:primary.state['cleanup'][1]['reference']['original']['sha256']='f'*64
                primary.save()
            with self.assertRaises((ValueError,RuntimeError)):self.owners['actor'].wait_peer_checkpoint()
            primary.store.write(original,primary.store.read())

    def test_original_whole_deadline_expiry_cannot_obtain_or_renew_a_peer_handoff(self):
        actor=self.owners['actor'];before=deepcopy(actor.store.read());self.epoch+=26000;self.mono+=26
        with self.assertRaises(NativeUIError):actor.wait_peer_checkpoint()
        self.assertEqual(before,actor.store.read())


if __name__=='__main__':unittest.main()
