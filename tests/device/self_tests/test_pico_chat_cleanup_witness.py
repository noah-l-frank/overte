"""Actual Pico cleanup wrapper/common sources on explicit adapter/parent seams.

Pico construction/native factories are separately tested against an actual
owned stdin worker. Here its adapter/parent identity is projected onto the
compiled-source fixture; no product target or complete 25-step claim follows.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_composition import PicoChatWitness
from adapters.pico4.chat_cleanup_witness import PicoChatCleanupWitness
from adapters.chat_journey.observation import ChatObservationOwner
from self_tests import test_chat_cleanup_witness as seams


class PicoChatCleanupWitnessTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatCleanupWitnessTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.sample=self.h.observers['actor'].samples;source=self.h.original.source
        self.parent=PrivateFeatureState(self.h.root/'projected-pico-parent.json')
        self.value=dict(picoChatCompositionVersion=6,runId=source.run,binding=deepcopy(self.sample.binding),
            peerBinding=deepcopy(self.sample.peer_binding),fixtureUrl=source.fixture_url,phase='caches-retired',
            completedSteps=26,peerOriginBasis='native-configured-metadata-only')
        self.parent.write(self.value,None);self.target='synthetic-pico-target';self.calls=[]
        def samples(*args,**kwargs):self.calls.append(('samples',args,kwargs));return self.sample
        def observation(*args,**kwargs):
            self.calls.append(('observation',args,kwargs))
            return ChatObservationOwner(args[1],args[2],self.h.h.flow.store,self.h.observers['actor'].store,
                stage='cleanup',cleanup_store=self.h.admission.store,monotonic=lambda:self.h.native.host)
        self.adapter=SimpleNamespace(_chat_composition_store=lambda _target:self.parent,
            _scripts=lambda _target:SimpleNamespace(binding=deepcopy(self.sample.binding)),
            _chat_cache_absence=samples,_chat_observation=observation,_chat_cleanup_witness_store=lambda _target:self.h.store)
        # Exact wrapper shell is an explicit identity seam, not a claim that
        # this compiled fixture ran the actual Pico actor constructor.
        self.original=PicoChatWitness.__new__(PicoChatWitness)
        self.original.adapter=self.adapter;self.original.target=self.target;self.original.publisher=self.h.original
        self.original.lock=self.sample.locks[0];self.original.binding=deepcopy(self.sample.binding)
        self.original.native=SimpleNamespace(guard=lambda:True)
        self.original.peer=SimpleNamespace(lock=self.sample.locks[1],binding=deepcopy(self.sample.peer_binding),
            reader=lambda:self.sample.peer,guard=lambda:True,close_host=lambda:False)

    def create(self):return PicoChatCleanupWitness(self.adapter,self.target,self.original)

    def test_warm_actor_cleanup_keeps_exact_original_code_reader_locks_and_independent_client(self):
        owner=self.create();self.assertEqual(27,owner.publish())
        self.assertEqual(1,len(self.h.posts));self.assertIs(owner.observation.source,self.h.original.source)
        self.assertIs(owner.observation.samples.script_source,self.h.original.samples.script_source)
        call=self.calls[0];self.assertEqual('samples',call[0]);self.assertTrue(call[2]['witness']);self.assertEqual('final',call[2]['stage'])
        self.assertIs(self.original.lock,call[2]['source_lock']);self.assertIs(self.original.peer.lock,call[2]['peer_lock'])
        self.assertFalse(owner.detach());self.assertEqual('ready',self.h.store.read()['phase'])

    def test_parent_finalization_after_last_publishing_cas_prevents_post_via_actual_final_source_guard(self):
        owner=self.create();write=self.h.store.write
        def changed(value,previous):
            write(value,previous)
            if value['delivery']=='publishing':self.parent.write({**self.value,'phase':'caches-ipc-released'},self.value)
        self.h.store.write=changed
        with self.assertRaises(NativeUIError):owner.publish()
        self.assertEqual([],self.h.posts);self.assertEqual('publishing',self.h.store.read()['delivery'])
        count=self.h.queries()
        with self.assertRaises(NativeUIError):owner.publish()
        self.assertEqual(count,self.h.queries());self.assertFalse(owner.detach())

    def test_wrong_parent_binding_or_phase_fails_before_constructing_any_new_actor_sources(self):
        self.parent.write({**self.value,'phase':'profile-restored'},self.value)
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual([],self.calls);self.assertIsNone(self.h.store.read())
        self.parent.write({**self.value,'peerBinding':{**self.sample.peer_binding,'sourceRevision':'f'*40}},self.parent.read())
        with self.assertRaises(NativeUIError):self.create()
        self.assertEqual([],self.calls);self.assertEqual([],self.h.posts)


if __name__=='__main__':unittest.main()
