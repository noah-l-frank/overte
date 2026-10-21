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
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from test_emote_controls import RawWidgets
from audio_native_boundary import ControlNativeBoundary
from test_graphics_images import BINDING

RUN='d'*32;TICKET='c'*32;OTHER='f'*32
URL='http://controlled.invalid/feature-fixture/v1'


class Originals(RigPackets):
    def __init__(self,root):
        super().__init__();self.root=root;self.clock=0.;self.binding=deepcopy(BINDING);self.okay=True
        self.calls=[];self.value=None;self.fault=None;self.phase_reads=0;self.idle=False;self.idle_frames=[]
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
        if self.idle:
            self.sequence+=1;evaluation=self.sequence*10
            pose=[0.,0.,0.,1.,self.sequence*.0001,.2,.3]
            self.idle_frames.append(dict(frameSequence=self.sequence,overrideSequence=0,evaluationSequence=evaluation,
                capturedEpochMs=self.epoch,overrideActive=False,joints=[dict(index=0,pose=pose)]))
            self.idle_frames=self.idle_frames[-32:]
            def observed(value):
                value.update(instance='a'*32,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,processId=31,
                    animationFence=dict(rigId=2,sequence=evaluation-1,requestedEpochMs=self.epoch))
                value['animation'].update(rigId=2,evaluationSequence=evaluation,capturedEpochMs=self.epoch,
                    joints=[pose],overrideActive=False,history=dict(historyVersion=2,instance='e'*32,available=True,
                        callSequence=0,overrideSequence=0,frameSequence=self.sequence,droppedEvents=0,
                        droppedFrames=self.sequence-len(self.idle_frames),events=[],frames=deepcopy(self.idle_frames)))
                value['animation'].pop('clip',None)
            original=NativeBoundary();original.sequence=self.sequence-1;original.mutate=observed;original.send(request)
            value=deepcopy(original.sample)
        else:
            value=self.native(self.epoch,active=True);value['requestId']=request['commandId']
            # The independent native fixture models a held final one-shot
            # pose when input is ignored. Keep original prefixes immutable and
            # expose the actual native 32-frame ring, rather than an unbounded
            # history or an impossible clip position beyond its loaded range.
            for frame in self.frames:
                if 'clip' in frame:frame['clip']['frame']=min(frame['clip']['frame'],120.)
                for joint in frame['joints']:joint['pose'][4]=min(joint['pose'][4],1.)
            history=value['animation']['history'];history['frames']=deepcopy(self.frames[-32:])
            history['droppedFrames']=len(self.frames)-len(history['frames'])
            value['animation']['joints']=[deepcopy(row['pose']) for row in self.frames[-1]['joints']]
            value['animation']['clip']['frame']=min(value['animation']['clip']['frame'],120.)
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
    def source(self,role='primary',*,segment=0):
        phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=lambda:self.epoch,monotonic=lambda:self.clock)
        return PhoneEmoteSources(self,'synthetic-selector',phase,role,self.lock,artifact_root=self.root,monotonic=lambda:self.clock,segment=segment)


class PhoneEmoteSourcesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-sources-');self.addCleanup(temporary.cleanup)
        self.model=Originals(Path(temporary.name))

    def test_bounded_segments_keep_previous_metadata_and_original_files_and_link_actual_native_ui_roots(self):
        m=self.model;m.idle=True
        with m.lock.held():
            first=m.source();old=first.read();header=deepcopy(first.previous)
            second=m.source(segment=1);self.assertEqual([],second.frames);self.assertEqual(old,second.predecessor)
            current=second.read();self.assertEqual(header,first.store.read());self.assertEqual(old,first.frames[-1])
            self.assertNotEqual(first.store.path,second.store.path);self.assertEqual(1,second.state['revision'])
            self.assertGreater(current['group']['native']['sequence'],old['group']['native']['sequence'])
            self.assertGreater(current['group']['rootsBefore']['sequence'],old['group']['rootsAfter']['sequence'])
            self.assertGreater(current['widgets']['sourceSequence'],old['widgets']['sourceSequence'])
            reconstructed=m.source(segment=1);self.assertEqual(second.frames,reconstructed.frames);reconstructed.read()
            third=m.source(segment=2);third.read();self.assertEqual(1,len(third.frames));self.assertIsNotNone(first.store.read());self.assertIsNotNone(second.store.read())

    def test_segment_cannot_skip_missing_predecessor_take_active_run_or_expand_closed_namespace(self):
        m=self.model
        with m.lock.held():
            for segment in (True,-1,16,1,2):
                with self.subTest(segment=segment),self.assertRaises((NativeUIError,ValueError)):m.source(segment=segment)
            m.source().read()
            with self.assertRaises(NativeUIError):m.source(segment=1)
            self.assertFalse((m.root/'phone-emote-primary-sources-segment-1.json').exists())

    def test_prior_segment_original_loss_or_changed_header_cannot_be_hidden_by_cached_predecessor(self):
        for fault in ('source-file','manifest','header'):
            temporary=tempfile.TemporaryDirectory(prefix='overte-emote-prior-');self.addCleanup(temporary.cleanup)
            m=Originals(Path(temporary.name));m.idle=True
            with self.subTest(fault=fault),m.lock.held():
                first=m.source();first.read();second=m.source(segment=1);calls=deepcopy(m.calls)
                if fault=='source-file':second.originals.path(second.originals.expand(second.prior_reference)).unlink()
                elif fault=='manifest':second.originals.manifest_path(second.prior_manifest).unlink()
                else:first.store.discard(first.previous)
                with self.assertRaises((NativeUIError,OSError,ValueError)):second.read()
                self.assertEqual(calls,m.calls);self.assertIsNone(second.store.read())

    def test_actor_namespace_never_reuses_primary_predecessor(self):
        m=self.model;m.idle=True
        with m.lock.held():
            m.source().read()
            with self.assertRaises(NativeUIError):m.source(role='actor',segment=1)
            first=m.source(role='actor');first.read();second=m.source(role='actor',segment=1);second.read()
            self.assertEqual('actor',second.previous['role']);self.assertEqual(1,len(second.frames))
    def test_fresh_sources_are_durable_originals_without_feature_or_peer_verdicts(self):
        m=self.model
        with m.lock.held():source=m.source();value=source.read()
        self.assertEqual('ready',source.state['phase']);self.assertEqual(1,source.state['revision'])
        self.assertEqual(TICKET,value['phaseAfter']['activations'][-1]['ticket'])
        self.assertEqual(value,source.frames[0]);self.assertEqual(1,len(source.state['manifests']))
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
                changed=deepcopy(original);state=unpack(changed['payload'])[0];frame=deepcopy(source.frames[0])
                if fault=='native-birth':frame['group']['native']['instance']='f'*32
                elif fault=='root':frame['group']['rootsAfter']['source']['defaultScriptsUrl']='file:///foreign/scripts'
                elif fault=='pose':frame['group']['native']['animation']['joints'][0][4]+=.1
                elif fault=='phase-prefix':frame['phaseAfter']['activations'][0]['stimulus']['verb']='open'
                elif fault=='ui':frame['ui']['scope']['sequence']+=1
                else:state['pending']={}
                if fault=='pending':
                    changed['payload']=pack([state]);source.store.write(changed,source.store.read())
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):m.source()
                    source.store.write(original,source.store.read())
                else:
                    # Storage must reject changed originals before any native
                    # facts can be replayed, even when their JSON stays valid.
                    entry=source.originals.manifest(source.state['manifests'][0])[0]
                    value=source.originals.expand(entry);path=source.originals.path(value);raw=path.read_bytes()
                    body=json.loads(raw);body['frame']=frame;path.write_text(json.dumps(body))
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):m.source()
                    path.write_bytes(raw)
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
    def test_legacy_inline_journal_is_preserved_and_never_upgraded_to_current_evidence(self):
        m=self.model
        with m.lock.held():
            source=m.source();legacy=dict(emoteSourcesVersion=1,runId=RUN,fixtureUrl=source.phase.fixture_url,role='primary',
                binding=m.binding,payload=pack([dict(phase='ready',revision=0,transcript=pack([]),pending=None)]))
            source.store.write(legacy,None)
            with self.assertRaises(NativeUIError):m.source()
        self.assertEqual(legacy,source.store.read());self.assertEqual([],m.calls)
    def test_v2_source_journal_is_preserved_without_adopting_its_legacy_native_origin(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.read();old=deepcopy(source.previous);old['emoteSourcesVersion']=2
            source.store.write(old,source.previous);before=list(m.calls)
            with self.assertRaises(NativeUIError):m.source()
            self.assertEqual(old,source.store.read());self.assertEqual(before,m.calls)

    def test_legacy_native_history_cannot_publish_a_v3_source_or_erase_pending_read(self):
        m=self.model;original=m.native_send
        def legacy(request):
            original(request);history=m.value['animation']['history'];history['historyVersion']=1
            for event in history['events']:event.pop('caller')
        m.native_send=legacy
        with m.lock.held():
            source=m.source()
            with self.assertRaises(NativeUIError):source.read()
            self.assertEqual('reading',source.state['phase']);self.assertEqual([],source.frames)
            before=list(m.calls)
            with self.assertRaises(NativeUIError):source.read()
            self.assertEqual(before,m.calls)
            self.assertEqual('reading',m.source().state['phase'])

    def test_historical_replay_uses_existing_script_transitions_beyond_512_originals(self):
        m=self.model;reader=m._script_execution_observer('synthetic',read_only=True);frames=[]
        for _ in range(600):
            packet=reader.read(reader.sequence,require_effects=True,require_code_identity=True,require_load_history=True,require_membership=True)
            frames.append(dict(group=dict(script=packet)))
        candidate=m._script_execution_observer('synthetic',read_only=True)
        PhoneEmoteSources.replay_scripts(candidate,frames);self.assertEqual(600,candidate.sequence)
        packet=candidate.read(600,require_code_identity=True,require_membership=True);self.assertEqual(601,packet['sequence'])
        changed=deepcopy(frames);changed[550]['group']['script']['source']['engines'][0]['code']['sha256']='f'*64
        candidate=m._script_execution_observer('synthetic',read_only=True)
        with self.assertRaises(NativeUIError):PhoneEmoteSources.replay_scripts(candidate,changed)
    def test_historical_replay_time_does_not_retime_the_later_live_acquisition_barrier(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.read();factory=m._script_execution_observer
            def slow(*args,**kwargs):m.clock+=2;return factory(*args,**kwargs)
            m._script_execution_observer=slow
            second=source.read()
        self.assertEqual(2.,m.clock);self.assertEqual(20200,second['epochMs'])
    def test_file_loss_or_namespace_swap_blocks_reconstruction_before_product_input(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.read();reference=source.state['manifests'][0]
            original=source.originals.manifest(reference)[0]
            source.originals.path(source.originals.expand(original)).unlink()
            with self.assertRaises(NativeUIError):m.source()
        self.assertEqual([],m.controls.input_requests)
    def test_failed_write_with_lost_guard_cannot_become_fresh_after_guard_restoration(self):
        m=self.model
        with m.lock.held():
            source=m.source();source.read();write=source.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['phase']=='ready':
                    m.okay=False;raise NativeUIError('Synthetic lost guard during commit')
                write(value,previous)
            source.store.write=lost
            with self.assertRaises(NativeUIError):source.read()
            m.okay=True;before=len(m.calls)
            with self.assertRaises(NativeUIError):source.read()
        self.assertEqual(before,len(m.calls));self.assertTrue(source.failed)


if __name__=='__main__':unittest.main()
