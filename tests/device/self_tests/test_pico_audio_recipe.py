"""Original normal recipe children with explicit native/UI/transport seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from copy import deepcopy
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_recipe import PicoAudioRecipe
from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner
from adapters.pico4.audio_final_close import PicoAudioFinalClose
from adapters.pico4.audio_background_owner import PicoAudioBackground
from adapters.token_audio_ui import TokenAudioUI
from adapters.script_journey.history import pack,unpack
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Journal,Client
from self_tests.test_pico_audio_page_owner import Boundary


class AudioRecipeIO:
    def __init__(self,physical):self.physical=physical;self.callback=None
    def bind_before_send(self,callback):
        if self.callback is not None and self.callback is not callback:raise NativeUIError('Explicit original transport already bound')
        self.callback=callback
    def capture(self):return self.physical.capture()
    def before(self,identifier,action,token,**fields):
        if self.callback is not None:
            observed=self.capture();self.callback(dict(schemaVersion=1,commandId=str(uuid.uuid4()),bridgeId=observed['bridgeId'],
                generation=observed['generation'],sequence=observed['lastCommandSequence']+1,observedElapsedMs=observed['elapsedMs'],
                controlId=identifier,controlToken=token,action=action,**fields))
    def activate(self,identifier,*,token):
        self.before(identifier,'activate',token);return self.physical.activate(identifier,token=token)
    def scroll(self,identifier,direction,*,token):
        self.before(identifier,'scroll',token,direction=direction);return self.physical.scroll(identifier,direction,token=token)


class AudioRecipeFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        self.native=Boundary(self.path,lifetime=True);self.journal=Journal(clock=self.native.epoch)
        self.run=self.native.preview.run;generated=self.journal.register('audio');self.journal.runs[self.run]=self.journal.runs.pop(generated)
        test=self
        class PhaseClient(Client):
            def request(self,path,*args,phase_nonce=None,**kwargs):return test.journal.phase(test.run,phase_nonce)
        self.source=PhaseFixtureReader(PhaseClient('http://127.0.0.1:9876/feature-fixture/v1','a'*64),self.run,'audio',
            monotonic=lambda:self.native.clock,epoch_ms=self.native.epoch)
        self.activate('baseline');self.parents=[];self.foreground=True;self.os_inputs=[];self.os_fault=''
        self.counts=deepcopy(self.native.native_reader.lifecycle);original=self.native.native.mutate
        def metadata(packet):
            original(packet)
            if self.counts is None:self.counts=deepcopy(packet['lifecycle'])
            packet['lifecycle']=deepcopy(self.counts)
        self.native.native.mutate=metadata
        original_stage=self.native.transport.stage
        def stage(envelope,profile,*,before_publish=None):
            if before_publish is not None:before_publish(deepcopy(envelope))
            return original_stage(envelope,profile)
        self.native.transport.stage=stage
        self.owner=self.recipe()
    def activate(self,verb,inputs=None):
        ticket=uuid.uuid4().hex;self.journal.activate(self.run,ticket,verb,{} if inputs is None else inputs);return ticket
    def page(self):
        parent=self.native.owner();route=AudioRecipeIO(self.native);preview=AudioRecipeIO(self.native)
        parent.route.io=route;parent.preview.controls=lambda intent:TokenAudioUI(preview,lambda *args:(intent(*args),self.native.intent(*args)),monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.parents.append(parent);return parent
    def status(self,binding):return dict(binding=binding,running=True,foreground=self.foreground)
    def os_input(self,operation,binding,*,before_input):
        before_input();self.os_inputs.append(operation)
        if operation=='lifecycle.background':
            if self.os_fault!='ack-only':
                self.foreground=False;self.native.guard_okay=False;self.counts['backgrounds']+=1
                self.native.publish('cancelled',self.native.events[-1]['capturedBytes'],error='backgrounded')
        else:self.foreground=True;self.native.guard_okay=True;self.counts['activations']+=1
        if self.os_fault=='lost':raise NativeUIError('Explicit original OS response loss')
    def recipe(self):
        recipe=None
        def background(cycle,capture):
            return PicoAudioBackground(self.path/f'audio-background-cycle-{cycle:02d}.json',self.run,self.native.binding,self.native.lock,
                self.status,self.os_input,lambda:capture or recipe.child(f'capture{cycle}.prepare'),self.source,
                monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        recipe=PicoAudioRecipe(self.path/'audio-recipe-owner.json',self.run,self.native.binding,self.native.lock,self.source,
            self.page,lambda cycle,parent:PicoAudioCaptureOwner(self.path/f'audio-capture-cycle-{cycle:02d}.json',parent,self.source),
            background,lambda cycle,capture:PicoAudioFinalClose(self.path/'audio-final-close.json',capture),self.status,monotonic=lambda:self.native.clock)
        return recipe
    def act(self,verb,inputs=None):
        ticket=self.activate(verb,inputs);self.last_call=dict(contractVersion=16,runId=self.run,fixtureUrl=self.source.fixture_url,
            verb=verb,inputs={} if inputs is None else inputs,ticket=ticket);return self.owner.act(self.last_call)
    def opened(self):
        self.owner.prepare();self.act('open');self.act('mute',dict(enabled=True));self.act('record-start');self.act('mute',dict(enabled=False))
    def completed(self):
        self.opened();self.act('record-start');self.act('record-cancel');self.act('record-start')
        self.native.auto_complete=True;self.act('await-completion');self.native.auto_complete=False
    def background_ready(self):
        self.completed();self.act('record-start');self.act('mute',dict(enabled=True));self.act('mute',dict(enabled=False));self.act('record-start')


class AudioRecipeTests(AudioRecipeFixture):
    def test_original_cancel_and_complete_link_prior_pcm_into_immutable_parent(self):
        self.completed();self.assertEqual(8,self.owner.state['cursor']);self.assertEqual(3,self.native.cycle)
        self.assertEqual(4,self.native.actions.count('audio.record'))
        for cycle in (2,3):
            child=self.owner.child(f'capture{cycle}.retain')
            self.assertEqual('retained',child.state['phase']);self.assertTrue(child.state['artifacts'])
        recovered=self.recipe();self.assertEqual(self.owner.report(),recovered.report())
        count=len(self.native.actions);recovered.act(self.last_call);self.assertEqual(count,len(self.native.actions))

    def test_actual_open_mute_rejection_restore_follow_shared_order(self):
        self.owner.prepare();self.act('open');self.act('mute',dict(enabled=True));self.act('record-start');result=self.act('mute',dict(enabled=False))
        self.assertEqual(4,result['normalStagesDispatched']);self.assertFalse(result['fullAudioQualified']);self.assertFalse(self.native.muted)
        self.assertEqual('microphone-muted',self.native.events[-1]['error']);self.assertEqual(1,self.native.cycle)
        self.assertEqual(['audio.mute','audio.record','audio.mute'],[value for value in self.native.actions if value.startswith('audio.')])
    def test_completed_ticket_is_read_only_and_cold_wrong_step_is_refused(self):
        self.owner.prepare();self.act('open');original=deepcopy(self.last_call);count=len(self.native.actions);streams=len(self.native.transport.envelopes)
        cold=self.recipe();cold.act(original)
        self.assertEqual(count,len(self.native.actions));self.assertEqual(streams,len(self.native.transport.envelopes))
        wrong=dict(original,verb='record-start')
        with self.assertRaises(NativeUIError):cold.act(wrong)
    def test_lost_normal_mute_response_recovers_original_child_without_toggle(self):
        self.owner.prepare();self.act('open');self.native.input_fault='lost-result'
        with self.assertRaises(NativeUIError):self.act('mute',dict(enabled=True))
        original=deepcopy(self.last_call);self.native.input_fault='';self.native.transform=lambda value:value
        cold=self.recipe();result=cold.act(original)
        self.assertEqual(2,result['normalStagesDispatched']);self.assertEqual(1,self.native.actions.count('audio.mute'))
        cold.act(original);self.assertEqual(1,self.native.actions.count('audio.mute'))
    def test_pending_wrong_ticket_cannot_reconcile_or_send_another_child(self):
        self.owner.prepare();self.act('open');self.native.input_fault='lost-result'
        with self.assertRaises(NativeUIError):self.act('mute',dict(enabled=True))
        count=len(self.native.actions);wrong=dict(self.last_call,ticket=uuid.uuid4().hex)
        self.native.input_fault='';self.native.transform=lambda value:value
        with self.assertRaises(NativeUIError):self.recipe().act(wrong)
        self.assertEqual(count,len(self.native.actions));self.assertIsNotNone(self.owner.state['pending'])
    def test_issued_parent_without_child_delivery_remains_unresolved_after_cold_recovery(self):
        self.owner.prepare();self.act('open');original=self.owner.invoke_child
        def interrupted(name):
            if name=='page.mute':raise NativeUIError('Explicit interruption before original child action')
            return original(name)
        with patch.object(self.owner,'invoke_child',side_effect=interrupted):
            with self.assertRaises(NativeUIError):self.act('mute',dict(enabled=True))
        with self.assertRaises(NativeUIError):self.recipe().act(self.last_call)
        self.assertFalse(self.native.muted);self.assertEqual(0,self.native.actions.count('audio.mute'))
    def test_archived_duplicate_reference_and_cold_host_regression_are_rejected(self):
        self.owner.prepare();self.act('open');disk=self.owner.store.read();state=unpack(disk['payload'])[0]
        state['steps'][0]['actions'][1]['before']=state['steps'][0]['actions'][0]['before']
        changed=dict(disk,payload=pack([state]));self.owner.store.write(changed,disk)
        with self.assertRaises(NativeUIError):self.recipe()
        self.owner.store.write(disk,changed);self.native.clock=-1
        with self.assertRaises(NativeUIError):self.recipe()
    def test_controller_intent_and_publish_are_host_only_and_late_publish_never_sends(self):
        self.owner.prepare();original=self.native.session.stage
        def stage(*args,**kwargs):
            intent,publish=kwargs['intent'],kwargs['before_publish']
            def host_intent(command):
                with patch.object(self.source,'status',side_effect=AssertionError('HTTP in locked intent')),patch.object(self.source,'epoch_ms',side_effect=AssertionError('Clock source in locked intent')):
                    intent(command)
            def late_publish(command):
                self.native.clock+=2
                with patch.object(self.source,'status',side_effect=AssertionError('HTTP in publication')),patch.object(self.owner.store,'read',side_effect=AssertionError('IO in publication')):
                    publish(command)
            return original(*args,**dict(kwargs,intent=host_intent,before_publish=late_publish))
        with patch.object(self.native.session,'stage',side_effect=stage):
            with self.assertRaises(NativeUIError):self.act('open')
        self.assertEqual([],self.native.transport.envelopes);self.assertFalse(self.native.shown)
        self.assertEqual('page.tablet',self.owner.report()['pending'])

    def test_cold_parent_controller_cannot_borrow_another_original_envelope(self):
        self.owner.prepare();self.act('open');disk=self.owner.store.read();state=unpack(disk['payload'])[0]
        command=state['steps'][0]['actions'][0]['deliveries'][0]['original'];command['sequence']+=1
        command['commands'][0]['id']='tablet-open-'+str(command['sequence'])
        self.owner.store.write(dict(disk,payload=pack([state])),disk)
        with self.assertRaises(NativeUIError):self.recipe()
        self.assertEqual(1,len(self.native.transport.envelopes));self.assertTrue(self.owner.store.path.exists())
    def test_cold_parent_cannot_reuse_an_original_qml_command_id(self):
        self.owner.prepare();self.act('open');self.act('mute',dict(enabled=True));disk=self.owner.store.read();state=unpack(disk['payload'])[0]
        first=state['steps'][0]['actions'][1]['deliveries'][0]['original']['commandId']
        state['steps'][1]['actions'][0]['deliveries'][0]['original']['commandId']=first
        self.owner.store.write(dict(disk,payload=pack([state])),disk)
        with self.assertRaises(NativeUIError):self.recipe()
        self.assertEqual(1,self.native.actions.count('audio.mute'))

    def test_frozen_fixture_and_native_clocks_include_last_parent_cas_host_age(self):
        self.owner.prepare();self.act('open');epoch=self.native.epoch();self.source.epoch_ms=lambda:epoch;self.journal.clock=lambda:epoch
        offset=[0];self.owner.monotonic=lambda:self.native.clock+offset[0];original=self.owner.save
        def slow(state,**kwargs):
            original(state,**kwargs)
            if state['pending'] is not None and state['pending']['name']=='page.mute' and state['pending']['deliveries']:offset[0]+=2
        with patch.object(self.owner,'save',side_effect=slow):
            with self.assertRaises(NativeUIError):self.act('mute',dict(enabled=True))
        self.assertFalse(self.native.muted);self.assertEqual(0,self.native.actions.count('audio.mute'))
        self.assertTrue(self.owner.store.path.exists())
    def test_cold_background_recovery_never_queries_qt_or_repeats_home(self):
        self.background_ready();self.os_fault='lost'
        with self.assertRaises(NativeUIError):self.act('background-resume')
        self.assertFalse(self.foreground);self.os_fault=''
        with patch.object(self.native,'owner',side_effect=AssertionError('Qt construction while backgrounded')):
            cold=self.recipe();result=cold.act(self.last_call)
        self.assertEqual('background5.home',self.owner.report()['pending']);self.assertIsNone(result['pending'])
        self.assertEqual(['lifecycle.background'],self.os_inputs);self.assertFalse(self.foreground)
        self.owner=cold;result=cold.act(self.last_call)
        self.assertEqual(13,result['normalStagesDispatched']);self.assertEqual(['lifecycle.background','app.launch'],self.os_inputs)

    def test_phase_progress_after_last_parent_cas_prevents_child_input(self):
        self.owner.prepare();self.act('open');original=self.owner.save
        def changed(state,**kwargs):
            original(state,**kwargs)
            if state['pending'] is not None and state['pending']['name']=='page.mute' and state['pending']['deliveries']:
                self.activate('record-start')
        with patch.object(self.owner,'save',side_effect=changed):
            with self.assertRaises(NativeUIError):self.act('mute',dict(enabled=True))
        self.assertFalse(self.native.muted);self.assertEqual(0,self.native.actions.count('audio.mute'));self.assertTrue(self.owner.store.path.exists())


class AudioRecipeFlowTests(AudioRecipeFixture):
    def test_all_fourteen_shared_normal_stages_keep_originals_and_partial_verdict(self):
        self.background_ready();self.act('background-resume')
        def callbacks(seconds):
            self.native.sleep(seconds)
            for cycle,epoch in self.native.record_starts.items():
                if cycle not in self.native.callback_events and self.native.epoch()-epoch>=30000:
                    self.native.callback_events[cycle]=dict(enteredEpochMs=self.native.epoch(),completedEpochMs=self.native.epoch(),retiredEpochMs=self.native.epoch(),retired=True)
        parent=self.owner.child('page.prepare');parent.settings.sleep=callbacks
        result=self.act('close')
        self.assertEqual(14,result['normalStagesDispatched']);self.assertEqual('partial-complete',self.owner.disk['phase'])
        self.assertFalse(result['fullAudioQualified']);self.assertFalse(result['acousticObserved']);self.assertFalse(result['independentPeerObserved'])
        self.assertEqual(['lifecycle.background','app.launch'],self.os_inputs);self.assertFalse(self.native.shown);self.assertFalse(self.native.opened)
        self.assertFalse(self.native.peak);self.assertFalse(self.native.muted);self.assertEqual({},self.native.files)
        self.assertEqual(5,self.native.cycle);self.assertEqual(3,len(self.native.transport.envelopes))
        self.assertTrue(self.owner.child('final5.deferred').report()['contextAlive'])
        self.assertEqual(result,self.recipe().report())



if __name__=='__main__':unittest.main()
