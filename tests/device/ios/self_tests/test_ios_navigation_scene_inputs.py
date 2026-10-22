"""Real normal Python inputs/private journals; SDK/native world are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters import normal_input
from ios.adapters.navigation_scene_inputs import NavigationSceneInputs
from ios.self_tests import test_ios_navigation_admission_owner as admission_tests
from ios.self_tests.test_ios_normal_navigation import IOSBoundary
from ios.self_tests.test_ios_navigation_sample import Navigation as MarkerNavigation
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from navigation_observation import viewpoint_urls


class NativeReturn(NativeFeatureObservation):
    def __init__(self,harness,first,last):
        self.h=harness;self.ios=True;self.pid=42;self.sequence=2;self.values=[global_packet(first,3),global_packet(last,4)]
        self.guard=lambda:harness.okay
    def read(self,after):
        self.h.reads.append('return-native');value=self.values.pop(0);self.sequence=value['sequence']
        self.h.advance(value['capturedEpochMs']);return deepcopy(value)


class NavigationSceneInputsTests(unittest.TestCase):
    def setUp(self):
        self.h=admission_tests.NavigationAdmissionOwnerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.b=IOSBoundary();self.b.scene=self.h.fixture.inputs['sceneUrl']
        self.b.current=viewpoint_urls(self.h.fixture.base['url'])['A']
        observed=self.b.observed
        def capture():
            value=observed();value['sampleEpochMs']=self.native_epoch();return value
        self.b.observed=capture
        self.native=normal_input.NativeInput(self.b.native_boundary,'owned-session',self.b.target,
            self.b.native_boundary.process,monotonic=lambda:self.b.clock,sleep=self.b.sleep,native_epoch_ms=self.native_epoch)
        def post(request,timeout):
            response=self.b.post(request,timeout);receipt=self.b.native_boundary.receipt
            key='observation' if 'observation' in receipt else 'status'
            receipt[key]['sampleEpochMs']=self.native_epoch();return response
        self.http=patch.object(normal_input,'urlopen',post);self.http.start();self.addCleanup(self.http.stop)
        with self.h.lock.held():self.admission=self.h.owner();self.h.take(self.admission)
    def owner(self):
        return NavigationSceneInputs(PrivateFeatureState(self.h.root/'ios-navigation-scene-inputs.json'),
            self.admission,self.b.ui,self.native,epoch_ms=self.h.epoch,monotonic=self.h.mono)

    def native_epoch(self):return self.h.native_first+self.h.ms+round(self.b.clock*1000)

    def owned_scene(self):
        fixture=self.h.fixture;harness=fixture.harness
        # Give the actual loopback provider the deterministic native fixture's
        # run identity before it serves real scene bytes. No product fact is
        # supplied through the provider.
        with patch('feature_journeys.witness.secrets.token_hex',return_value=self.h.provider.run):
            self.assertEqual(self.h.provider.run,harness.open())
        _,raw,_=harness.get('/navigation/scene.json');inventory=fixture.inventory
        inventory.clock+=(max(fixture.join['nativeAfter']['capturedEpochMs'],self.native_epoch())-inventory.epoch())/1000+.01
        inventory.url=viewpoint_urls(fixture.inputs['sceneUrl'])['A'];inventory.body=raw
        inventory.raw={row['id'].strip('{}'):json.dumps(row,sort_keys=True).encode() for row in json.loads(raw)['Entities']}
        inventory.revision=inventory.after_revision=3;inventory.commit()
        current=inventory.reader().read(self.h.provider.run)
        # Use actual original import history in the modeled native source,
        # matching the observed independent complete inventory.
        class Clock:
            clock=inventory.clock+.002
        clock=Clock();navigation=MarkerNavigation(clock,self.h.provider.run,inventory.url,json.loads(raw))
        clock.clock=inventory.clock+.002
        navigation.sequence=current['source']['sceneLoads']['sequence']
        navigation.mutate=lambda value:value['source']['sceneLoads'].update(
            currentGeneration=inventory.generation,requests=deepcopy(inventory.loads))
        observed=navigation.reader().read(self.h.provider.run)
        ui=deepcopy(fixture.originals['ui']);ui.update(sampleEpochMs=observed['clockAfter']['epochMs']+1,
            elapsedMs=observed['clockAfter']['monotonicMs']+1,lastSequence=self.b.sequence_native)
        first=current['clockBefore']['epochMs']-1;last=ui['sampleEpochMs']+1
        fixture.originals.update(inventory=current,navigation=observed,ui=ui)
        self.h.ms=first-self.h.native_first;self.admission.native=NativeReturn(self.h,first,last)

    def test_normal_entry_and_return_acknowledge_delivery_without_claiming_scene_or_cleanup_success(self):
        with self.h.lock.held():
            owner=self.owner();self.assertEqual({'performed':True},owner.enter())
            self.assertEqual(viewpoint_urls(self.h.fixture.inputs['sceneUrl'])['A'],self.b.current)
            self.assertEqual('entered',owner.state['phase']);self.assertIsNotNone(owner.state['enterUi'])
            self.owned_scene();self.assertEqual({'performed':True},owner.return_to_original())
            self.assertEqual(viewpoint_urls(self.h.fixture.base['url'])['A'],self.b.current)
            self.assertEqual('return-delivered',owner.state['phase']);self.assertEqual(2,self.b.inputs.count('PhoneAddressGoButton'))
            self.assertEqual(3,len(owner.state['gate']['originals']));self.assertIsNotNone(owner.state['gate']['result'])
            before=list(self.b.inputs);again=self.owner();self.assertEqual({'performed':True},again.return_to_original())
            self.assertEqual(before,self.b.inputs);self.assertIsNotNone(again.store.read())
            self.assertIsNotNone(self.admission.store.read());self.assertNotIn('restored',owner.state)

    def test_ignored_enter_still_requires_independent_scene_effect_and_cannot_authorize_return(self):
        with self.h.lock.held():
            self.b.mutation='goto-ignored';owner=self.owner();before=self.b.current
            self.assertEqual({'performed':True},owner.enter());self.assertEqual(before,self.b.current)
            self.assertEqual('entered',owner.state['phase']);self.assertNotIn('passed',owner.state)
            with self.assertRaises((NativeUIError,ValueError)):owner.return_to_original()
            self.assertEqual(1,self.b.inputs.count('PhoneAddressGoButton'))

    def test_lost_entry_result_keeps_issued_intent_and_never_resends_any_normal_input(self):
        with self.h.lock.held():
            owner=self.owner();write=owner.store.write
            def lose(value,previous):
                if unpack(value['payload'])[0]['phase']=='entered':raise OSError('Synthetic lost input result')
                write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):owner.enter()
            before=list(self.b.inputs);again=self.owner();self.assertEqual('enter-issued',again.state['phase'])
            with self.assertRaises(NativeUIError):again.enter()
            with self.assertRaises(NativeUIError):again.return_to_original()
            self.assertEqual(before,self.b.inputs);self.assertEqual(1,before.count('PhoneAddressGoButton'))

    def test_lost_return_result_keeps_return_issued_without_replaying_go_to(self):
        with self.h.lock.held():
            owner=self.owner();owner.enter();self.owned_scene();write=owner.store.write
            def lose(value,previous):
                if unpack(value['payload'])[0]['phase']=='return-delivered':raise OSError('Synthetic lost return result')
                write(value,previous)
            owner.store.write=lose
            with self.assertRaises(OSError):owner.return_to_original()
            before=list(self.b.inputs);again=self.owner();self.assertEqual('return-issued',again.state['phase'])
            with self.assertRaises(NativeUIError):again.return_to_original()
            self.assertEqual(before,self.b.inputs)

    def test_unsaved_edit_or_additional_entity_refuses_return_before_any_input(self):
        for fault in ('edit','extra'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                with self.h.lock.held():
                    owner=self.owner();owner.enter();self.owned_scene();before=list(self.b.inputs)
                    packet=self.h.fixture.originals['inventory'];tree=packet['source']['tree']
                    if fault=='edit':tree['entities'][0]['semanticSha256']='f'*64
                    else:
                        row=deepcopy(tree['entities'][0]);row['id']='00000000-0000-4000-8000-000000000099'
                        for value in (tree,packet['source']['commitOrigin']['latest']['tree']):
                            value['entities'].append(deepcopy(row));value['entities'].sort(key=lambda row:row['id']);value['totalEntities']+=1
                    with self.assertRaises(NativeUIError):owner.return_to_original()
                    self.assertEqual(before,self.b.inputs);self.assertEqual('return-checking',self.owner().state['phase'])

    def test_partial_return_read_retains_original_prefix_and_cannot_restart_gate(self):
        with self.h.lock.held():
            owner=self.owner();owner.enter();self.owned_scene();self.h.fault='navigation';before=list(self.b.inputs)
            with self.assertRaises(OSError):owner.return_to_original()
            again=self.owner();self.assertEqual({'inventory'},set(again.state['gate']['originals']))
            self.assertIsNotNone(again.state['gate']['nativeStart']);self.h.fault=None
            reads=list(self.h.reads)
            with self.assertRaises(NativeUIError):again.return_to_original()
            self.assertEqual(reads,self.h.reads);self.assertEqual(before,self.b.inputs)

    def test_foreign_native_ui_source_or_expired_admission_never_sends_first_input(self):
        for fault in ('source','expired'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                with self.h.lock.held():
                    owner=self.owner()
                    if fault=='source':self.b.native_boundary.instance='11111111-2222-3333-4444-777777777777'
                    else:self.h.ms+=2000
                    with self.assertRaises(NativeUIError):owner.enter()
                    self.assertEqual([],self.b.inputs)

    def test_rewound_input_history_foreign_scene_body_or_open_tablet_prevents_return(self):
        for fault in ('input-counter','body','tablet'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp()
                with self.h.lock.held():
                    owner=self.owner();owner.enter();self.owned_scene();before=list(self.b.inputs)
                    if fault=='input-counter':self.h.fixture.originals['ui']['lastSequence']=0
                    elif fault=='tablet':self.h.fixture.originals['ui']['tabletShown']=True
                    else:self.h.fixture.originals['inventory']['source']['commitOrigin']['latest']['bodySha256']='f'*64
                    with self.assertRaises(NativeUIError):owner.return_to_original()
                    self.assertEqual(before,self.b.inputs)

    def test_late_return_validation_retains_preflight_but_never_delivers_an_expired_input(self):
        with self.h.lock.held():
            owner=self.owner();owner.enter();self.owned_scene();before=list(self.b.inputs);validate=owner.validate_gate
            def late():
                value=validate();self.h.ms+=2000;return value
            owner.validate_gate=late
            with self.assertRaises(NativeUIError):owner.return_to_original()
            self.assertEqual('return-checking',owner.state['phase']);self.assertIsNotNone(owner.state['gate']['result'])
            self.assertEqual(before,self.b.inputs)

    def test_an_acknowledged_phase_without_original_input_history_cannot_be_reconstructed(self):
        with self.h.lock.held():
            owner=self.owner();owner.enter();raw=owner.store.read();state=unpack(raw['payload'])[0]
            state['enteredUi']=None;changed=deepcopy(raw);changed['payload']=pack([state]);owner.store.write(changed,raw)
            before=list(self.b.inputs)
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(before,self.b.inputs)
