"""Real durable Phone acquisition over explicit synthetic native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from overte_phone_emote_controls import PhoneEmoteIO
from overte_phone_emote_sources import PhoneEmoteSources,EmotePhaseChanged
from overte_phone_script_history import pack,unpack
from overte_phone_script_lock import PhoneScriptSourceLock
from test_emote_rig_measurements import RigPackets
from test_emote_controls import RawWidgets
from audio_native_boundary import ControlNativeBoundary
from test_graphics_images import BINDING

RUN='d'*32;TICKET='c'*32;OTHER='f'*32
URL='http://controlled.invalid/feature-fixture/v1'


class Originals(RigPackets):
    def __init__(self,root):
        super().__init__();self.root=root;self.clock=0.;self.binding=deepcopy(BINDING);self.okay=True
        self.calls=[];self.value=None;self.fault=None;self.phase_reads=0
        self.widgets=RawWidgets();self.controls=ControlNativeBoundary(self.widgets,'phone-emote-ui')
        self.controls.mutate=self.widget_original
        self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('emotes')
        self.journal.activate(RUN,TICKET)
        self.client=Client(URL,'x'*64);self.client.request=self.fixture_request
        self.lock=PhoneScriptSourceLock(root/'phone-script-sources.lock')
        original=self.code.mutate
        def script(value):
            original(value)
            value['source'].update(effectSourceVersion=1,effects=dict(complete=True,scanRadiusMeters=64,
                scannedEntities=0,absentIds=[],entities=[]),loadSourceVersion=1,
                loads=dict(complete=True,instance='9'*32,sequence=0,events=[]))
            if self.fault=='manager':
                value['source']['engines'][0]['required']['instance']='8'*32
                value['source']['membership']['managers'][0]['instance']='8'*32
        self.code.mutate=script

    def state_path(self,_selector):return self.root/'session.json'
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only;binding=deepcopy(self.binding)
        return None,None,binding,lambda:self.okay and self.binding==binding,dict(bound=True)
    def sleep(self,seconds):self.clock+=seconds
    def options(self):return dict(monotonic=lambda:self.clock,sleep=self.sleep)
    def _script_roots(self,_selector,*,read_only):
        assert read_only;self.calls.append('roots-factory');return self.roots.reader()
    def _script_execution_observer(self,_selector,*,read_only):
        assert read_only;self.calls.append('scripts-factory');reader=self.code.reader()
        reader.clock_ms=lambda:self.epoch;return reader
    def native_send(self,request):
        self.calls.append('native-read');self.epoch+=100;self.roots.epoch=self.epoch
        value=self.native(self.epoch,active=True);value['requestId']=request['commandId']
        if self.fault=='old-native':value['sequence']=1
        elif self.fault=='native-birth':value['instance']='6'*32
        self.value=value
        if self.fault=='lost-return':raise RuntimeError('Synthetic native dispatch return lost')
        if self.fault=='slow':self.clock+=2
    def _native_feature_observer(self,_selector,*,read_only):
        assert read_only;self.calls.append('native-factory')
        return NativeFeatureObservation(self.native_send,lambda:json.dumps(self.value),lambda:self.epoch,
            lambda:self.okay,31,**self.options())
    def widget_original(self,value):
        # Producer clock at native capture, before the original is serialized.
        if value['action']=='observe':
            value['capturedEpochMs']=self.epoch
            if self.fault=='old-ui':value['sourceSequence']=1
    def _emote_controls(self,_selector,intent,*,read_only):
        assert read_only;self.calls.append('ui-factory')
        io=PhoneEmoteIO(self.controls.send,lambda:json.dumps(self.controls.value),lambda:self.epoch,
            lambda:self.okay,31,tablet_shown=lambda:self.widgets.tablet,**self.options())
        return SimpleNamespace(io=io)
    def fixture_request(self,path,**kwargs):
        assert path=='/runs/'+RUN+'/phase' and set(kwargs)=={'phase_nonce'}
        self.calls.append('phase-read');self.phase_reads+=1
        if self.fault=='phase-race' and self.phase_reads==2:self.journal.activate(RUN,OTHER,'open',{})
        return self.journal.phase(RUN,kwargs['phase_nonce'])
    def source(self,role='primary'):
        phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=lambda:self.epoch,monotonic=lambda:self.clock)
        return PhoneEmoteSources(self,'synthetic-selector',phase,role,self.lock,monotonic=lambda:self.clock)


class PhoneEmoteSourcesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-sources-');self.addCleanup(temporary.cleanup)
        self.model=Originals(Path(temporary.name))
    def test_fresh_sources_are_durable_originals_without_feature_or_peer_verdicts(self):
        m=self.model
        with m.lock.held():source=m.source();value=source.read()
        self.assertEqual('ready',source.state['phase']);self.assertEqual(1,source.state['revision'])
        self.assertEqual(TICKET,value['phaseAfter']['activations'][-1]['ticket'])
        self.assertEqual(value,source.frames[0]);self.assertEqual(1,len(unpack(source.state['transcript'])))
        self.assertNotIn('state',value);self.assertNotIn('facts',value);self.assertNotIn('resources',value)
        self.assertEqual([],m.controls.input_requests)
    def test_reconstructed_reader_acquires_new_originals_beyond_every_retained_cursor(self):
        m=self.model
        with m.lock.held():
            first=m.source().read();source=m.source();before=len(m.calls);second=source.read()
        self.assertGreater(len(m.calls),before);self.assertEqual(2,source.state['revision'])
        self.assertGreater(second['group']['rootsBefore']['sequence'],first['group']['rootsAfter']['sequence'])
        for field in ('script','native'):
            self.assertGreater(second['group'][field]['sequence'],first['group'][field]['sequence'])
            self.assertNotEqual(second['group'][field]['requestId'],first['group'][field]['requestId'])
        self.assertGreater(second['widgets']['sourceSequence'],first['widgets']['sourceSequence'])
        second['group']['native']['instance']='mutated-copy'
        self.assertEqual('a'*32,source.frames[-1]['group']['native']['instance'])
    def test_each_role_has_its_own_original_transcript_without_copying_other_roles(self):
        m=self.model
        with m.lock.held():
            primary=m.source();left=primary.read();actor=m.source('actor');right=actor.read()
        self.assertNotEqual(primary.store.path,actor.store.path)
        self.assertGreater(right['group']['native']['sequence'],left['group']['native']['sequence'])
        self.assertNotEqual(left['group']['script']['requestId'],right['group']['script']['requestId'])
        self.assertEqual(1,primary.state['revision']);self.assertEqual(1,actor.state['revision'])
    def test_consumed_widget_input_does_not_derive_animation_from_its_highlight(self):
        m=self.model;m.widgets.page=True;m.widgets.active='Crying'
        with m.lock.held():value=m.source().read()
        page=next(row for row in value['ui']['controls'] if row['id']=='emote.page')
        self.assertEqual('Crying',page['activeName'])
        self.assertTrue(value['group']['native']['animation']['clip']['url'].endswith('/Waving.fbx'))
        self.assertNotIn('animation',value['ui'])
    def test_lost_return_leaves_pending_responsibility_and_cannot_be_reset_by_reconstruction(self):
        m=self.model;m.fault='lost-return'
        with m.lock.held():
            source=m.source()
            with self.assertRaises(NativeUIError):source.read()
            before=len(m.calls);reconstructed=m.source()
            with self.assertRaises(NativeUIError):reconstructed.read()
        self.assertEqual(before,len(m.calls));self.assertEqual('reading',reconstructed.state['phase'])
        self.assertEqual(0,reconstructed.state['revision']);self.assertEqual([],m.controls.input_requests)
    def test_role_process_candidate_run_or_url_cannot_adopt_another_transcript(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.read();original=source.store.read()
            for key,value in [('role','actor'),('runId','f'*32),('fixtureUrl',URL+'/foreign/')]:
                changed=deepcopy(original);changed[key]=value;source.store.write(changed,source.store.read())
                with self.subTest(key=key),self.assertRaises(NativeUIError):m.source()
            source.store.write(original,source.store.read());m.binding['artifactSha256']='f'*64
            with self.assertRaises(NativeUIError):m.source()
    def test_tampered_transcript_is_recomputed_instead_of_trusting_cached_history(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.read();original=source.store.read()
            for fault in ('native-birth','root','pose','phase-prefix','ui','pending'):
                changed=deepcopy(original);state=unpack(changed['payload'])[0];rows=unpack(state['transcript']);frame=rows[0]
                if fault=='native-birth':frame['group']['native']['instance']='f'*32
                elif fault=='root':frame['group']['rootsAfter']['source']['defaultScriptsUrl']='file:///foreign/scripts'
                elif fault=='pose':frame['group']['native']['animation']['joints'][0][4]+=.1
                elif fault=='phase-prefix':frame['phaseAfter']['activations'][0]['stimulus']['verb']='open'
                elif fault=='ui':frame['ui']['scope']['sequence']+=1
                else:state['pending']={}
                state['transcript']=pack(rows);changed['payload']=pack([state]);source.store.write(changed,source.store.read())
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):m.source()
    def test_changed_source_manager_native_birth_or_reused_cursors_never_become_fresh(self):
        for fault in ('manager','native-birth','old-native','old-ui'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(prefix='overte-emote-counterexample-') as root:
                m=Originals(Path(root))
                with m.lock.held():
                    m.source().read();m.fault=fault;source=m.source()
                    with self.assertRaises(NativeUIError):source.read()
                    self.assertEqual('reading',source.state['phase']);self.assertEqual(1,source.state['revision'])
    def test_phase_crossing_is_retained_under_original_tickets_without_returning_current_facts(self):
        m=self.model;m.fault='phase-race'
        with m.lock.held():
            source=m.source()
            with self.assertRaises(EmotePhaseChanged):source.read()
            first=source.frames[0];self.assertEqual('ready',source.state['phase']);m.fault=None
            next_value=m.source().read()
        self.assertEqual(TICKET,first['phaseBefore']['activations'][-1]['ticket'])
        self.assertEqual(OTHER,first['phaseAfter']['activations'][-1]['ticket'])
        self.assertEqual(OTHER,next_value['phaseBefore']['activations'][-1]['ticket'])
    def test_frozen_device_clock_cannot_hide_whole_acquisition_delay(self):
        m=self.model;m.fault='slow'
        with m.lock.held():
            source=m.source()
            with self.assertRaises(NativeUIError):source.read()
        self.assertEqual('reading',source.state['phase']);self.assertEqual([],source.frames)
    def test_slow_final_durable_write_cannot_return_aged_originals_as_current(self):
        m=self.model
        with m.lock.held():
            source=m.source();write=source.store.write
            def delayed(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['phase']=='ready':m.clock+=2
            source.store.write=delayed
            with self.assertRaises(NativeUIError):source.read()
            # Accepted originals remain historical evidence; the failed fresh
            # delivery never removes or retimes that complete acquisition.
            reconstructed=m.source()
        self.assertEqual(1,reconstructed.state['revision']);self.assertEqual('ready',reconstructed.state['phase'])
        self.assertEqual(20100,reconstructed.frames[0]['epochMs'])
    def test_failed_final_write_cannot_reset_pending_state_on_the_same_live_object(self):
        m=self.model
        with m.lock.held():
            source=m.source();write=source.store.write
            def fail(value,previous):
                if unpack(value['payload'])[0]['phase']=='ready':raise NativeUIError('Synthetic final source write failure')
                write(value,previous)
            source.store.write=fail
            with self.assertRaises(NativeUIError):source.read()
            before=len(m.calls)
            with self.assertRaises(NativeUIError):source.read()
        self.assertEqual(before,len(m.calls));self.assertEqual('reading',source.state['phase']);self.assertEqual([],source.frames)
    def test_retirement_crossing_acquisition_returns_no_active_facts(self):
        m=self.model;request=m.client.request
        def retire(path,**kwargs):
            if m.phase_reads==1:m.journal.close(RUN)
            return request(path,**kwargs)
        m.client.request=retire
        with m.lock.held():
            source=m.source()
            with self.assertRaises(NativeUIError):source.read()
        self.assertEqual('reading',source.state['phase']);self.assertEqual([],source.frames)
    def test_missing_lock_or_lost_session_guard_sends_no_observation(self):
        m=self.model
        with self.assertRaises(NativeUIError):m.source()
        self.assertEqual([],m.calls)
        with m.lock.held():
            source=m.source();m.okay=False
            with self.assertRaises(NativeUIError):source.read()
        self.assertEqual([],m.calls)
    def test_foreign_store_change_is_not_overwritten_before_acquisition(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.store.write(dict(foreign=True),None)
            with self.assertRaises(NativeUIError):source.read()
        self.assertEqual(dict(foreign=True),source.store.read())
        self.assertNotIn('phase-read',m.calls);self.assertNotIn('native-read',m.calls)


if __name__=='__main__':unittest.main()
