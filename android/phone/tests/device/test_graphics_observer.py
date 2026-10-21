"""Original synthetic sources plus real PNGs/journals; no product qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import json
import hashlib
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Journal,Client
from overte_phone_graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending
from overte_phone_graphics_observer import PhoneGraphicsObserver
from overte_phone_script_history import pack,unpack,canonical
import test_graphics_samples as samples_fixture
from test_graphics_samples import Originals
from self_tests.test_native_process_presence import Boundary as Presence
from self_tests.test_world_render_evidence import frame_view
from test_graphics_effects import Pair,POLICY as EFFECT_POLICY
from test_graphics_measurements import RUN,TICKET,SCENE,URL,POLICY


class Model(Originals):
    def __init__(self,root):
        super().__init__(root);self.journal=Journal(lambda:20000);self.published=[];self.transport_calls=[]
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('graphics')
        self.journal.activate(RUN,TICKET);self.confirm_race=False
        self.scene.ui['controls']=[];self.scene.tablet['scriptInventory']['tabletShown']=False
        self.client.request=lambda *args,**kwargs:self.request('primary',*args,**kwargs)
        self.actor=Client(URL,'y'*64);self.actor.run=RUN;self.actor.area='graphics';self.actor.graphics_instance=self.scene.instance
        self.actor.graphics_previous=None;self.actor.closed=False;self.actor.graphics_status=self.provider
        self.actor.request=lambda *args,**kwargs:self.request('actor',*args,**kwargs)
        self.client.closed=False;self.stage=0
        self.policy=deepcopy(POLICY);self.pid=31;self.exit_fault=None;self.presence_sources=[]
        self.status_count=0;actual=self.provider
        def provider():
            self.status_count+=1
            if self.confirm_race and self.status_count==4:self.phase('close')
            previous=deepcopy(self.client.graphics_previous);value=actual()
            if self.active_role=='actor':
                self.client.graphics_previous=previous;self.actor.graphics_previous=deepcopy(value)
            return value
        self.client.graphics_status=self.actor.graphics_status=provider
    def send(self,key,request):
        if self.stage==0:return super().send(key,request)
        journal=PrivateFeatureState(self.root/('phone-graphics-'+self.active_role+'-1-samples.json')).read()
        assert journal is not None and unpack(journal['payload'])[0]['phase']=='reading'
        self.calls.append((key,deepcopy(request)));self.counters[key]+=1
        template={'native':'before','subject':'subject_before','graphics':'ui','tablet':'tablet','capture':'capture'}[key]
        value=deepcopy(getattr(self.scene,template));value['commandId' if key in ('graphics','tablet') else 'requestId']=request['commandId']
        value['processId']=self.pid;value['sourceSequence' if key in ('graphics','tablet') else 'sequence']=self.counters[key]
        if key=='capture':
            value['source']['image']['name']=samples_fixture.image_name(request['commandId'])
            value['source']['acquisitionSequence']=self.counters[key]
            value['source']['renderTrace']['frameId']=uuid.uuid4().hex;self.storage.present=True
        self.values[key]=value
    def reader(self,key,cls):
        result=cls(lambda request:self.send(key,request),lambda:json.dumps(self.values[key]),
            self.epoch,self.guard,self.pid,**self.options());self.readers.append((key,result));return result
    def _world_render_capture(self,_selector,*,read_only,role,require_frame_view):
        assert read_only and require_frame_view
        f=samples_fixture;owner=f.WorldRenderOwner(PrivateFeatureState(self.root/('world-'+role+'.json')),self.binding,self.guard,role=role)
        storage=f.NativeWorldRenderStorage(self.storage_send,lambda name:(self.receipt_root/name).read_text(),
            self.epoch,self.guard,self.pid,receipt_intent=owner.receipt_intent,**self.options())
        cleanup=f.NativeWorldReceiptInventory(lambda request:self.inventory_send(owner,request),
            self.inventory.original,self.epoch,self.guard,self.pid,owner.owned,lambda:storage.instance,**self.options())
        files=f.NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.receipt_root/name).read_text()),cleanup)
        reader=f.NativeWorldRenderCapture(lambda request:self.send('capture',request),lambda:json.dumps(self.values['capture']),
            storage,self.epoch,self.guard,self.pid,intent=owner.intent,require_frame_view=True,**self.options())
        return f.OwnedWorldRenderCapture(reader,storage,owner,files)
    def _process_presence(self,_selector,*,read_only):
        assert read_only
        boundary=Presence(pid=self.pid,epoch_ms=self.epoch);boundary.presence=self.exit_fault or 'absent'
        boundary.edit=lambda value:value.update(instance=self.scene.before['instance'])
        self.presence_sources.append(boundary);return boundary.reader()
    def new_process(self):
        self.stage=1;self.pid=32;self.binding['processIdentity']='32:19'
        for key in ('before','after','subject_before','subject_after','ui','tablet','capture'):
            getattr(self.scene,key)['instance']='8'*32
        for key in ('ui','tablet'):getattr(self.scene,key)['generation']='9'*32
        self.scene.before['lifecycle']['launches']+=1;self.scene.before['lifecycle']['activations']+=1
        self.storage.mutate=lambda value:value.update(instance='8'*32,processId=32)
        self.inventory.mutate=lambda value:value.update(instance='8'*32,processId=32)
    def paint(self,ticket,fog=(230,230,230),orange=False):Pair.paint(SimpleNamespace(source=self),ticket,fog,orange)
    def effect_profile(self):
        self.policy=deepcopy(EFFECT_POLICY);self.scene.subject_before['source']['view']['aspectRatio']=16/9
        self.scene.capture['source'].update(sourceExtent=[416,234],sourceViewport=[0,0,416,234],targetExtent=[640,360])
        self.scene.capture['source']['renderTrace']['recordedView']=frame_view(16/9);self.paint(TICKET)
    def request(self,role,path,value=None,method=None,**kwargs):
        assert method is None and not kwargs;self.transport_calls.append((role,path))
        if path=='/runs/'+RUN+'/active':assert value is None;return self.journal.active(RUN)
        if path=='/runs/'+RUN:assert value is None;return self.journal.snapshot(RUN)
        if path=='/runs/'+RUN+'/samples':
            assert role=='actor';self.published.append(deepcopy(value));return self.journal.publish(RUN,value)
        raise AssertionError('Unexpected synthetic fixture transport')
    def phase(self,verb,inputs=None,ticket=None):
        ticket=ticket or uuid.uuid4().hex
        self.change_phase(ticket);self.active['stimulus']=dict(verb=verb,inputs=inputs or {})
        self.journal.activate(RUN,ticket,verb,inputs or {});return ticket
    def factory_observer(self,role='primary'):
        self.active_role=role;client=self.client if role=='primary' else self.actor
        source=GraphicsFixtureReader(client,RUN,epoch_ms=self.epoch)
        return PhoneGraphicsObserver(self,'controlled',source,role,self.lock,self.root,self.policy,**self.options())
    def archive_observer(self,value,role='primary'):
        return PhoneGraphicsObserver.archive(value,run=RUN,fixture_url=URL,provider_instance=self.scene.instance,
            role=role,artifact_root=self.root,image_policy=self.policy)


class GraphicsObserverTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.m=Model(self.root)
    def test_original_public_image_state_and_measured_baseline_are_not_requested_results(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();value=owner.read(0,0)
            self.assertEqual(.65,value['state']['resolution']);self.assertAlmostEqual((104/160+94/144)/2,value['state']['renderScale'])
            self.assertFalse(value['state']['dialog']);self.assertEqual([],value['resources'])
            self.assertEqual(value['state']['resolution'],owner.baseline()['resolution'])
            self.assertEqual('world-render-target',value['artifacts'][0]['source'])
            self.assertTrue((self.root/value['artifacts'][0]['name']).is_file());self.assertEqual(TICKET,value['artifacts'][0]['ticket'])
            self.assertEqual('ready',m.archive_observer(owner.previous)['phase'])
    def test_ignored_normal_setting_remains_original_false_and_is_not_replaced_by_requested_true(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();owner.read(0,0);ticket=m.phase('set-haze',dict(enabled=True))
            owner=m.factory_observer();value=owner.read(1,0)
            self.assertFalse(value['state']['haze']);self.assertFalse(value['state']['hazePass']);self.assertEqual([],owner.state['effects'])
            self.assertEqual(ticket,value['artifacts'][0]['ticket'])
    def test_new_observer_object_requires_new_gpu_frame_and_retains_all_source_floors(self):
        m=self.m
        with m.lock.held():
            first=m.factory_observer();one=first.read(0,0);before=deepcopy(first.state['last'])
            second=m.factory_observer();two=second.read(1,0)
            self.assertEqual(2,two['sequence']);self.assertNotEqual(one['artifacts'][0]['name'],two['artifacts'][0]['name'])
            self.assertGreater(second.state['last']['frame']['nativeAfter']['sequence'],before['frame']['nativeAfter']['sequence'])
            self.assertEqual(first.state['baseline'],second.state['baseline'])
    def test_primary_and_actor_acquire_distinct_originals_and_only_actor_publishes(self):
        m=self.m
        with m.lock.held():
            primary=m.factory_observer();p=primary.read(0,0);actor=m.factory_observer('actor');self.assertEqual(1,actor.publish(0,0))
            self.assertEqual(1,len(m.published));payload=m.published[0]
            self.assertEqual(actor.state['last']['frame']['ticket'],payload['ticket']);self.assertEqual(1,payload['actorSequence'])
            self.assertNotEqual(p['artifacts'][0]['name'],actor.state['last']['frame']['image']['name'])
            self.assertNotEqual(primary.store.path,actor.store.path)
            with self.assertRaises(NativeUIError):primary.publish(0,0)
            with self.assertRaises(NativeUIError):m.archive_observer(primary.previous,'actor')
    def test_changed_candidate_session_or_pid_cannot_be_adopted_without_explicit_restart_stage(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();owner.read(0,0);original=deepcopy(m.binding)
            for field,value in [('processIdentity','32:19'),('artifactSha256','f'*64),('generation',99),('sessionId','foreign')]:
                m.binding=original|{field:value};other=m.factory_observer()
                with self.subTest(field=field),self.assertRaises(NativeUIError):other.read(1,0)
            m.binding=original
    def test_nonbaseline_first_phase_or_open_baseline_cannot_establish_originals(self):
        m=self.m
        with m.lock.held():
            m.phase('close');owner=m.factory_observer()
            with self.assertRaises(NativeUIError):owner.read(0,0)
            self.assertIsNone(owner.state['baseline']);self.assertEqual('ready',owner.state['phase'])
    def test_missing_native_result_cannot_publish_and_reading_intent_survives_reconstruction(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();m.fault='subject-cursor'
            with self.assertRaises(NativeUIError):owner.read(0,0)
            self.assertEqual('reading',owner.state['phase']);m.fault=None
            with self.assertRaises(NativeUIError):m.factory_observer().read(0,0)
            self.assertEqual([],m.published)
    def test_reused_gpu_frame_or_native_cursor_is_rejected_even_with_fresh_ticket_and_file(self):
        for fault in ('frame-reuse','native-cursor','subject-cursor','graphics-cursor','tablet-cursor'):
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);m=Model(Path(temporary.name))
            with m.lock.held():
                owner=m.factory_observer();owner.read(0,0);m.phase('close');m.fault=fault
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):m.factory_observer().read(1,0)
                self.assertEqual([],m.published)
    def test_original_png_replacement_is_detected_by_the_historical_role_archive(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();owner.read(0,0);value=deepcopy(owner.previous)
        path=self.root/owner.state['last']['frame']['image']['name'];path.write_bytes(b'changed original file')
        with self.assertRaises(NativeUIError):m.archive_observer(value)
    def test_host_write_loss_or_ignored_write_cannot_return_a_green_public_sample(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();write=owner.store.write
            def lost(value,previous):write(value,previous);raise RuntimeError('Synthetic lost observer write')
            owner.store.write=lost
            with self.assertRaises(RuntimeError):owner.read(0,0)
            self.assertEqual('reading',m.factory_observer().state['phase'])
    def test_malformed_archive_unknown_fields_boolean_version_or_wrong_scope_is_refused(self):
        m=self.m
        with m.lock.held():owner=m.factory_observer();owner.read(0,0)
        for field,value in [('role','actor'),('providerInstance','f'*32),('runId','f'*32),('graphicsObserverVersion',True),('expectedState',{})]:
            other=deepcopy(owner.previous);other[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):m.archive_observer(other)
    def test_future_caller_cursor_is_rejected_before_any_native_acquisition(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();before=len(m.calls)
            for sequence in (True,-1,1):
                with self.subTest(sequence=sequence),self.assertRaises(NativeUIError):owner.read(sequence,0)
            self.assertEqual(before,len(m.calls))

    def test_actual_haze_and_mirror_target_pixels_are_compared_for_each_original_role(self):
        for feature,verb,role in [(feature,verb,role) for feature,verb in [('haze','set-haze'),('mirror','set-mirrors')] for role in ('primary','actor')]:
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);m=Model(Path(temporary.name));m.effect_profile()
            with m.lock.held():
                owner=m.factory_observer(role);owner.read(0,0)
                off=m.phase(verb,dict(enabled=False));m.paint(off);owner=m.factory_observer(role);owner.read(1,0)
                on=m.phase(verb,dict(enabled=True));m.paint(on,(30,110,210) if feature=='haze' else (230,230,230),feature=='mirror')
                m.scene.before['graphics']['hazeSetting' if feature=='haze' else 'mirrorsSetting']=True
                trace=m.scene.capture['source']['renderTrace'];trace[feature+'Batches']=2;trace[feature+'DrawCommands']=8
                owner=m.factory_observer(role);value=owner.read(2,0);self.assertTrue(value['state'][feature])
                self.assertEqual(1,len(owner.state['effects']));self.assertEqual(feature,owner.state['effects'][0]['feature'])
                self.assertEqual(1,len(m.archive_observer(owner.previous,role)['effects']))
    def test_preference_and_executed_batches_without_actual_target_pixel_effect_stay_red(self):
        m=self.m;m.effect_profile()
        with m.lock.held():
            owner=m.factory_observer();owner.read(0,0);ticket=m.phase('set-haze',dict(enabled=True));m.paint(ticket)
            m.scene.before['graphics']['hazeSetting']=True;m.scene.capture['source']['renderTrace'].update(hazeBatches=2,hazeDrawCommands=8)
            owner=m.factory_observer()
            with self.assertRaises(NativeUIError):owner.read(1,0)
            self.assertEqual([],m.published);self.assertEqual('reading',owner.state['phase'])
    def test_explicit_new_process_stage_requires_this_roles_own_original_frame_and_kernel_absence(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();owner.read(0,0);old=deepcopy(owner.state['last']['frame']);m.phase('restart-app');m.new_process()
            owner=m.factory_observer();value=owner.read(1,1);self.assertEqual(2,value['lifecycle']['launches'])
            transfer=owner.state['restart'];self.assertEqual(old,transfer['oldFrame']);self.assertEqual('ESRCH',transfer['exit']['errorSymbol'])
            self.assertEqual(31,transfer['exit']['queryProcessId']);self.assertEqual(32,transfer['exit']['processId'])
            self.assertEqual(1,m.archive_observer(owner.previous)['stage']);self.assertEqual(0,owner.state['baseline']['image']['stage'])
    def test_present_or_permission_unknown_old_process_cannot_qualify_the_new_stage(self):
        for fault in ('present','unknown'):
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);m=Model(Path(temporary.name))
            with m.lock.held():
                owner=m.factory_observer();owner.read(0,0);m.phase('restart-app');m.new_process();m.exit_fault=fault;owner=m.factory_observer()
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.read(1,1)
                self.assertEqual('reading',owner.state['phase']);self.assertIsNone(owner.state['restart'])
    def test_new_pid_without_native_birth_or_lifecycle_persistence_cannot_be_adopted(self):
        for fault in ('birth','launch','preferences'):
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);m=Model(Path(temporary.name))
            with m.lock.held():
                owner=m.factory_observer();owner.read(0,0);m.phase('restart-app');m.new_process()
                if fault=='birth':m.scene.before['instance']='a'*32
                elif fault=='launch':m.scene.before['lifecycle']['launches']=1
                else:m.scene.before['graphics']['requestedResolutionScale']=.5
                owner=m.factory_observer()
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.read(1,1)
                self.assertEqual([],m.published)
    def test_actor_ticket_race_after_complete_acquisition_retains_original_frame_without_sticking_reading(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer('actor');owner.read(0,0);actual=owner.source.read;calls=0
            def crossing(previous=None):
                nonlocal calls
                calls+=1
                if calls==2:m.phase('close')
                return actual(previous)
            owner.source.read=crossing
            with self.assertRaises(GraphicsPhasePending):owner.read(1,0)
            self.assertEqual('ready',owner.state['phase']);self.assertEqual(TICKET,owner.state['last']['frame']['ticket'])
            fresh=m.factory_observer('actor');fresh.publish(0,0)
            self.assertNotEqual(TICKET,m.published[-1]['ticket'])
    def test_actor_phase_bracket_race_after_complete_capture_recovers_without_old_fact_publication(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer('actor');owner.read(0,0);actual=owner.source.read;calls=0
            def crossing(previous=None):
                nonlocal calls
                calls+=1
                value=actual(previous)
                if calls==2:raise GraphicsPhasePending('Synthetic original bracket race')
                return value
            owner.source.read=crossing
            with self.assertRaises(GraphicsPhasePending):owner.read(1,0)
            self.assertEqual('ready',owner.state['phase']);self.assertEqual([],m.published)
            self.assertEqual(3,m.factory_observer('actor').publish(0,0))

    def test_both_roles_prove_their_own_new_process_frame_and_independent_original_exit_query(self):
        m=self.m
        with m.lock.held():
            primary=m.factory_observer();primary.read(0,0);actor=m.factory_observer('actor');actor.read(0,0)
            m.phase('restart-app');m.new_process();primary=m.factory_observer();primary.read(1,1)
            actor=m.factory_observer('actor');actor.read(1,1)
            self.assertNotEqual(primary.state['restart']['oldFrame']['capture']['requestId'],actor.state['restart']['oldFrame']['capture']['requestId'])
            self.assertNotEqual(primary.state['restart']['newFrame']['capture']['requestId'],actor.state['restart']['newFrame']['capture']['requestId'])
            self.assertNotEqual(primary.state['restart']['exit']['commandId'],actor.state['restart']['exit']['commandId'])
            self.assertEqual(2,len(m.presence_sources));self.assertEqual(1,m.archive_observer(actor.previous,'actor')['stage'])
    def test_actor_changed_ticket_during_acquisition_retires_its_exact_capture_before_new_frame(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer('actor');owner.read(0,0);send=m.send;changed=False
            def crossing(key,request):
                nonlocal changed
                send(key,request)
                if key=='subject' and m.counters['subject']>=4 and not changed:changed=True;m.phase('close')
            m.send=crossing
            with self.assertRaises(GraphicsPhasePending):owner.read(1,0)
            self.assertEqual('ready',owner.state['phase']);self.assertEqual(1,owner.state['sequence']);self.assertEqual([],m.published)
            sources=PrivateFeatureState(self.root/('phone-graphics-actor-0-samples.json')).read()
            self.assertEqual(1,len(unpack(sources['payload'])[0]['retirements']))
            self.assertFalse((self.root/'world-actor.json').exists())
            owner=m.factory_observer('actor');owner.publish(0,0);self.assertEqual(1,len(m.published));self.assertNotEqual(TICKET,m.published[0]['ticket'])
    def test_slow_final_confirmation_with_frozen_clocks_cannot_return_old_current_facts(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();actual=owner.source.read;calls=0
            def slow(previous=None):
                nonlocal calls
                calls+=1;value=actual(previous)
                if calls==2:m.clock+=1.501
                return value
            owner.source.read=slow
            with self.assertRaises(NativeUIError):owner.read(0,0)
            self.assertEqual([],m.published);self.assertTrue(owner.store.path.exists())
    def test_ignored_role_intent_write_prevents_any_native_input_or_capture(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();owner.store.write=lambda *_args:None;before=len(m.calls)
            with self.assertRaises(NativeUIError):owner.read(0,0)
            self.assertEqual(before,len(m.calls));self.assertEqual([],m.published)

    def test_an_explicit_stage_change_cannot_acquire_from_a_changed_candidate_or_session(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();owner.read(0,0);m.phase('restart-app');m.new_process();binding=deepcopy(m.binding)
            for field,value in [('artifactSha256','f'*64),('sourceRevision','f'*40),('sessionId','foreign-session'),('generation',99)]:
                m.binding=binding|{field:value};owner=m.factory_observer();before=len(m.calls)
                with self.subTest(field=field),self.assertRaises(NativeUIError):owner.read(1,1)
                self.assertEqual(before,len(m.calls))

    def test_v2_journal_uses_one_immutable_private_archive_per_original_frame(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();owner.read(0,0);wire=unpack(owner.previous['payload'])[0]
            self.assertEqual(2,owner.previous['graphicsObserverVersion']);self.assertIn('graphicsObserverFrameRefVersion',wire['baseline'])
            self.assertEqual(wire['baseline'],wire['last']['frame']);self.assertEqual(wire['baseline'],wire['offFrames']['haze'])
            self.assertEqual(1,len(list(self.root.glob('graphics-observer-*.json'))));owner=m.factory_observer();owner.read(1,0)
            self.assertEqual(2,len(list(self.root.glob('graphics-observer-*.json'))));self.assertEqual('ready',m.archive_observer(owner.previous)['phase'])
    def test_missing_or_changed_original_frame_archive_cannot_be_replaced_by_journal_values(self):
        m=self.m
        with m.lock.held():owner=m.factory_observer();owner.read(0,0)
        reference=unpack(owner.previous['payload'])[0]['baseline'];path=self.root/reference['name'];original=path.read_bytes()
        path.unlink()
        with self.assertRaises(NativeUIError):m.archive_observer(owner.previous)
        path.write_bytes(original);path.chmod(0o600);value=json.loads(original);value['requestId']='f'*32
        path.write_text(json.dumps(value))
        with self.assertRaises(NativeUIError):m.archive_observer(owner.previous)
    def test_borrowed_archive_is_rejected_even_with_a_recomputed_outer_reference_digest(self):
        m=self.m
        with m.lock.held():owner=m.factory_observer();owner.read(0,0)
        value=deepcopy(owner.previous);state=unpack(value['payload'])[0];reference=state['baseline'];path=self.root/reference['name']
        packet=json.loads(path.read_text());packet['role']='actor';path.write_text(json.dumps(packet));path.chmod(0o600)
        reference['sha256']=hashlib.sha256(canonical(packet)).hexdigest();value['payload']=pack([state])
        with self.assertRaises(NativeUIError):m.archive_observer(value)
    def test_frame_reference_cannot_escape_scope_or_accept_unknown_desired_fields(self):
        m=self.m
        with m.lock.held():owner=m.factory_observer();owner.read(0,0)
        for edit in [dict(name='../foreign.json'),dict(stage=1),dict(expectedGraphics={}),dict(graphicsObserverFrameRefVersion=True)]:
            value=deepcopy(owner.previous);state=unpack(value['payload'])[0];state['baseline'].update(edit);value['payload']=pack([state])
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):m.archive_observer(value)
    def test_v1_or_unreferenced_full_frame_journals_cannot_be_implicitly_upgraded(self):
        m=self.m
        with m.lock.held():owner=m.factory_observer();owner.read(0,0)
        value=deepcopy(owner.previous);value['graphicsObserverVersion']=1
        with self.assertRaises(NativeUIError):m.archive_observer(value)
        value=deepcopy(owner.previous);value['payload']=pack([owner.state])
        with self.assertRaises(NativeUIError):m.archive_observer(value)
    def test_ignored_original_frame_archive_write_cannot_return_a_green_sample(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();write=PrivateFeatureState.write
            def ignored(store,value,previous):
                if store.path.name.startswith('graphics-observer-'):return
                return write(store,value,previous)
            with patch.object(PrivateFeatureState,'write',ignored),self.assertRaises(NativeUIError):owner.read(0,0)
            self.assertEqual('reading',m.factory_observer().state['phase']);self.assertEqual([],m.published)
    def test_lost_original_archive_write_response_preserves_red_intent_and_diagnostics(self):
        m=self.m
        with m.lock.held():
            owner=m.factory_observer();write=PrivateFeatureState.write
            def lost(store,value,previous):
                result=write(store,value,previous)
                if store.path.name.startswith('graphics-observer-'):raise RuntimeError('Synthetic lost archive write response')
                return result
            with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(RuntimeError):owner.read(0,0)
            self.assertEqual(1,len(list(self.root.glob('graphics-observer-*.json'))));self.assertEqual('reading',m.factory_observer().state['phase'])


if __name__=='__main__':unittest.main()
