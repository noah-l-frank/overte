"""Appearance from actual normal recipes and original files at synthetic Qt/VM seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters import normal_input
from ios.adapters.avatar_actions import IOSAvatarActions
from ios.adapters.avatar_observation import source_history,appearance
from ios.self_tests import test_ios_avatar_actions as fixture_module
from ios.self_tests import test_ios_avatar_entities as entity_fixture


class AvatarObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.AvatarActionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.lock=self.fixture.lock;held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        transport=patch.object(normal_input,'urlopen',self.fixture.fixture.widget.post);transport.start();self.addCleanup(transport.stop)
        self.fixture.source=self.fixture.make_sources();self.actions=self.fixture.owner();self.actions.prepare()
        self.baseline=self.actions.state['baseline']['revision']
    def history(self):
        source=self.fixture.source
        return source_history(source.previous,None,store=source.store,root=source.root,binding=source.binding,
            run=source.run,role=source.role,lock=source.lock)
    def measure(self):
        sources=self.history();return appearance(sources,self.baseline,len(sources.frames),
            fixture_url=self.fixture.fixture.phase.fixture_url,expected_code=entity_fixture.EXPECTED)
    def act(self,verb,inputs,index):
        query=self.fixture.action(verb,inputs,format(index,'032x'));self.actions.act(query)
        return self.measure()
    def test_eight_genuine_normal_appearance_steps_restore_without_primary_ack_inference(self):
        baseline=self.measure()['state'];self.assertEqual(dict(avatar='original',requestedAvatar='original',modelLoaded=True,loadFailed=False,
            scale=1.,wearable=False,bookmarked=False),baseline)
        cases=[('avatar-url',dict(resource='avatar-a.fst'),dict(avatar='A',requestedAvatar='A')),
            ('avatar-bookmark-save',dict(name='e2e-'+self.fixture.fixture.run),dict(bookmarked=True)),
            ('avatar-scale',dict(value=1.5),dict(scale=1.5)),
            ('wearable-add',dict(resource='gltf-bundle/main.gltf'),dict(wearable=True)),
            ('avatar-url',dict(resource='missing.fst'),dict(avatar='fallback',requestedAvatar='missing',loadFailed=True)),
            ('avatar-bookmark-choose',dict(name='e2e-'+self.fixture.fixture.run),dict(avatar='A',requestedAvatar='A',loadFailed=False,scale=1.,wearable=False)),
            ('avatar-restore',{},dict(avatar='original',requestedAvatar='original')),
            ('avatar-bookmark-delete',dict(name='e2e-'+self.fixture.fixture.run),dict(bookmarked=False))]
        expected=baseline
        for index,(verb,inputs,delta) in enumerate(cases,1):
            expected=expected|delta;actual=self.act(verb,inputs,index)
            self.assertEqual(expected,actual['state'],verb)
        sources=self.history();calls=len(self.fixture.fixture.widget.requests)
        historical=IOSAvatarActions.history(self.actions.previous,self.actions.inputs.previous,sources,
            fixture_url=self.fixture.fixture.phase.fixture_url,peer=self.actions.peer,expected_code=entity_fixture.EXPECTED)
        self.assertEqual(self.actions.state,historical.state);self.assertEqual(calls,len(self.fixture.fixture.widget.requests))
        with self.assertRaises(NativeUIError):historical.act(self.actions.state['calls'][-1]['query'])
    def test_original_recipes_and_source_files_validate_without_live_guard_sdk_or_mutable_action_owner(self):
        self.act('avatar-url',dict(resource='avatar-a.fst'),1)
        source=self.fixture.source;value=deepcopy(source.previous);actions=deepcopy(self.actions.previous);inputs=deepcopy(self.actions.inputs.previous)
        calls=len(self.fixture.fixture.widget.requests);source.guard=lambda:(_ for _ in ()).throw(AssertionError('live guard'))
        sources=source_history(value,None,store=source.store,root=source.root,binding=source.binding,run=source.run,role=source.role,lock=source.lock)
        historical=IOSAvatarActions.history(actions,inputs,sources,fixture_url=self.fixture.fixture.phase.fixture_url,
            peer=self.actions.peer,expected_code=entity_fixture.EXPECTED)
        self.assertEqual('A',appearance(sources,self.baseline,len(sources.frames),fixture_url=self.fixture.fixture.phase.fixture_url,
            expected_code=entity_fixture.EXPECTED)['state']['avatar'])
        self.assertEqual(1,len(historical.state['calls']));self.assertEqual(calls,len(self.fixture.fixture.widget.requests))
        wrong=deepcopy(inputs);rows=unpack(wrong['payload'])
        rows[0]['calls'][0]['events'][0]['intent']['nativeCommand']['commandId']='ios-'+'f'*32
        wrong['payload']=pack(rows)
        with self.assertRaises(NativeUIError):IOSAvatarActions.history(actions,wrong,sources,fixture_url=self.fixture.fixture.phase.fixture_url,
            peer=self.actions.peer,expected_code=entity_fixture.EXPECTED)
    def test_loaded_bookmark_without_matching_original_persisted_bytes_is_not_bookmarked(self):
        self.act('avatar-url',dict(resource='avatar-a.fst'),1)
        self.act('avatar-bookmark-save',dict(name='e2e-'+self.fixture.fixture.run),2)
        mutate=self.fixture.fixture.mutate
        def divergent(name,value):
            mutate(name,value)
            if name=='state':
                raw=b'{}';value['source']['bookmarkFile'].update(bytes=2,sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())
        self.fixture.fixture.mutate=divergent;self.fixture.source.read()
        with self.assertRaises(NativeUIError):self.measure()
    def test_actual_loaded_foreign_resource_does_not_inherit_requested_A_label_from_primary_ack(self):
        self.act('avatar-url',dict(resource='avatar-a.fst'),1)
        f=self.fixture.fixture;foreign='https://foreign.invalid/loaded.fst';f.widget.avatar_url=foreign
        native=f.prototypes['state'];generation=native['source']['modelHistory']['currentGeneration']+1
        fixture_module.state_tests.requested(native,generation,foreign,generation)
        fixture_module.state_tests.event(native,'finished',generation,foreign,assignment=generation,resource=foreign,success=True)
        for event in native['source']['modelHistory']['events'][-3:]:event.update(epochMs=f.now(),monotonicMs=round(f.clock*1000))
        self.fixture.source.read()
        self.assertEqual('acknowledged',self.actions.state['calls'][-1]['phase'])
        with self.assertRaises(NativeUIError):self.measure()
    def test_historical_decoder_consumes_every_abandoned_source_prefix_and_retains_reset_failure(self):
        from ios.self_tests import test_ios_avatar_source_recovery as recovery_fixture
        from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
        f=recovery_fixture.AvatarSourceRecoveryTests();f.setUp();self.addCleanup(f.doCleanups)
        with f.lock.held():
            owner=f.interrupt();IOSAvatarSourceRecovery(owner).recover();current=f.sources();current.read()
            recovered=IOSAvatarSourceRecovery(current);original=recovered.store.read();commands=deepcopy(f.fixture.sources)
            decoded=source_history(current.previous,original,store=current.store,root=current.root,binding=current.binding,
                run=current.run,role=current.role,lock=current.lock)
            self.assertEqual(current.frames,decoded.frames);self.assertEqual(commands,f.fixture.sources)
        other=recovery_fixture.AvatarSourceRecoveryTests();other.setUp();self.addCleanup(other.doCleanups)
        with other.lock.held():
            interrupted=other.interrupt();recovery=IOSAvatarSourceRecovery(interrupted);recovery.recover();original=recovery.store.read()
            other.fixture.prototypes['entities']['instance']='9'*32
            # With no earlier completed frame, this new source is individually
            # valid. Its genuine old birth survives only in the abandoned read.
            foreign=other.sources();foreign.read()
            with self.assertRaises(NativeUIError):source_history(foreign.previous,original,store=foreign.store,root=foreign.root,
                binding=foreign.binding,run=foreign.run,role=foreign.role,lock=foreign.lock)

    def test_mutated_in_memory_native_results_do_not_replace_immutable_original_frames(self):
        self.act('avatar-url',dict(resource='avatar-a.fst'),1);sources=self.history()
        sources.frames[-1]['originals']['state']['source']['geometryLoaded']=False
        with self.assertRaises(NativeUIError):appearance(sources,self.baseline,len(sources.frames),
            fixture_url=self.fixture.fixture.phase.fixture_url,expected_code=entity_fixture.EXPECTED)


if __name__=='__main__':unittest.main()
