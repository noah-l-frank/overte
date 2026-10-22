"""Independent source joins reject requested state, aliases and lost effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_lifecycle_feature import Target,RUN
from adapters.normal_ui import NativeUIError
from overte_phone_lifecycle_measurements import measurement,continuity_sources
from overte_phone_lifecycle_actions import LifecycleActions
from feature_journeys.scenarios import VERSION


class LifecycleMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.target=Target(Path(self.tmp.name));self.flow=self.target.flow();self.owner=self.flow.prepare()
    def frame(self):
        with self.flow.serialized():self.flow.load();return self.flow.collect()[0]
    def project(self,frame,*,baseline=None,intents=None,origin=None):
        baseline=baseline or self.owner['baseline'];origin=origin or baseline['world']['motion']['feetPosition']
        return measurement(RUN,frame,baseline,intents if intents is not None else self.flow.owner['intents'],origin,pid=self.target.pid,epoch=self.target.epoch(),after_epoch=100000)
    def test_baseline_and_actual_editor_sources_do_not_consume_a_requested_checkpoint(self):
        self.assertEqual('none',self.project(self.frame())[0]['editor']);self.target.open('create');self.target.editor.body['current'].update(text='Overte ä Ω 東京 '+RUN,focused=True);self.target.editor.body['osKeyboardVisible']=True;self.target.sdk.screen='create'
        facts,resources=self.project(self.frame());self.assertEqual(('create',1,True,True),(facts['editor'],facts['generation'],facts['focused'],facts['keyboard']));self.assertEqual(['panel:lifecycle-tablet'],resources)
    def test_input_ack_without_actual_press_or_effect_has_zero_attempts_and_no_movement(self):
        frame=self.frame();frame['world']['source']['performed']=False
        intents=[dict(commandId='f'*32,action='phone-lifecycle-world-input',operation='hold')]
        facts,_=self.project(frame,intents=intents);self.assertEqual((0,0.,[]),(facts['worldAttempts'],facts['worldDisplacement'],facts['heldInputs']))
    def test_original_origin_cannot_be_replaced_with_a_requested_position(self):
        with self.assertRaises(NativeUIError):self.project(self.frame(),origin=[0,0,3])
    def test_context_order_or_duplicate_identity_cannot_be_a_generation(self):
        self.target.open('chat');self.target.sdk.screen='chat'
        with self.assertRaises(NativeUIError):self.project(self.frame())
        self.target.hide();self.target.editor.body['contexts']=[];self.target.open('create');self.target.sdk.screen='create';frame=self.frame();frame['editor']['source']['contexts'].append(deepcopy(frame['editor']['source']['contexts'][0]))
        with self.assertRaises(NativeUIError):self.project(frame)
    def test_actual_field_join_rejects_an_unrelated_scripts_object_with_the_same_text(self):
        self.target.open('create');self.target.hide();self.target.open('chat');self.target.hide();self.target.open('scripts');self.target.sdk.screen='scripts';frame=self.frame()
        self.assertEqual(3,self.project(frame)[0]['generation']);frame['pending']['current']['token']='9'*32
        with self.assertRaises(NativeUIError):self.project(frame)
    def test_foreign_attempt_or_unrecorded_intent_is_never_owned(self):
        self.target.open('create');self.target.sdk.screen='create'
        reader=self.target._lifecycle_world('controlled',read_only=False,intent=lambda value:None);reader.request(RUN,'hold');frame=self.frame()
        with self.assertRaises(NativeUIError):self.project(frame)
        frame['world']['source']['gestures'][0]['runId']='e'*32;frame['world']['source']['pendingRun']='e'*32
        with self.assertRaises(NativeUIError):self.project(frame)
    def test_source_birth_and_render_epoch_cannot_be_retimed_to_this_phase(self):
        for key in ('editor','world','native'):
            frame=self.frame();frame[key]['instance']='9'*32
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.project(frame)
        frame=self.frame();self.target.sdk.clock+=2
        with self.assertRaises(NativeUIError):self.project(frame)
    def test_fresh_clock_cannot_hide_native_pending_scene_or_renderer_history_reset(self):
        before=self.frame();after=self.frame();continuity_sources(before,after,self.target.pid)
        for fault in ('native-sequence','native-lifecycle','pending-sequence','scene-sequence','renderer','probe-sequence','principal'):
            changed=deepcopy(after)
            if fault=='native-sequence':changed['native']['sequence']=before['native']['sequence']
            elif fault=='native-lifecycle':before['native']['lifecycle']['backgrounds']=1
            elif fault=='pending-sequence':changed['pending']['sequence']=before['pending']['sequence']
            elif fault=='scene-sequence':changed['scene']['sequence']=before['scene']['sequence']
            elif fault=='renderer':changed['probe']['source']['render']['frameCount']=before['probe']['source']['render']['frameCount']
            elif fault=='probe-sequence':changed['probe']['source']['sampleSequence']=before['probe']['source']['sampleSequence']
            else:changed['native']['account']['principalSha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):continuity_sources(before,changed,self.target.pid)
            before['native']['lifecycle']['backgrounds']=0
    def test_scene_commit_ack_cannot_hide_pending_native_callback_or_foreign_scene(self):
        for fault in ('pending','foreign','markers','airborne','renderer-stale'):
            frame=self.frame()
            if fault=='pending':frame['scene']['requests'][-1].update(phase='queued',pending=True,releasedEpochMs=None);frame['scene']['pendingLeases']=1
            elif fault=='foreign':frame['probe']['source']['sceneUrl']=frame['probe']['source']['sceneUrl'].replace('/scene.json','/foreign.json')
            elif fault=='markers':frame['probe']['source']['fixtureMarkers']=[];frame['probe']['source']['fixtureMarkerCount']=0
            elif fault=='airborne':frame['world']['motion']['grounded']=False
            else:frame['probe']['source']['render']['lastFrameEpochMs']-=1600
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.project(frame)
    def test_original_archive_is_pure_and_does_not_query_or_retime_the_target(self):
        from overte_phone_lifecycle_evidence import LifecycleEvidence
        from unittest.mock import patch
        self.flow.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        with self.flow.serialized():
            self.flow.load();state=self.flow.role_state()
            with patch.object(self.flow,'runtime',side_effect=AssertionError('Archive must not query SDK')):
                frames=LifecycleEvidence(self.flow,state,'primary').frames()
        self.assertEqual(1,len(frames));self.assertEqual(100000,frames[0]['sources']['editor']['capturedEpochMs'])
    def test_ignored_focus_and_back_do_not_become_complete_and_uncertain_input_never_replays(self):
        t=self.target;t.input_fault='ignore-focus';ticket='8'*32;t.activate(ticket,'open-editor',dict(editor='create'))
        call=dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.flow.fixture_url,ticket=ticket,verb='open-editor',inputs=dict(editor='create'))
        with self.assertRaises(NativeUIError):self.flow.act(call)
        count=len(t.inputs)
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(count,len(t.inputs));self.assertFalse(t.editor.body['current']['focused'])
        t.input_fault='';t.activate('7'*32,'cleanup');self.flow.cleanup(dict(contractVersion=VERSION,runId=RUN));self.assertIsNone(t.sdk.screen)
    def test_shared_field_token_is_required_for_actual_guard_rejection_counter(self):
        t=self.target
        for editor in ('create','chat','scripts'):
            t.open(editor);t.sdk.screen=editor
        t.editor.body['current'].update(text='retry-'+RUN,focused=True);t.editor.body['osKeyboardVisible']=True
        with self.flow.serialized():
            self.flow.load();actions=LifecycleActions(self.flow,self.flow.owner);held=actions.pending(control=True).hold(RUN)
            self.assertEqual(1,self.project(self.flow.collect()[0])[0]['deferredInputs'])
            t.hide();t.open('scripts');t.sdk.screen='scripts';actions.pending(control=True).attempt_retired(RUN,held['commit']['observation']['eventId'])
            frame=self.flow.collect()[0];facts,_=self.project(frame);self.assertEqual((4,0,1),(facts['generation'],facts['deferredInputs'],facts['staleAttempts']))
            frame['pending']['commit']['fieldToken']=frame['editor']['source']['current']['fieldToken']
            with self.assertRaises(NativeUIError):self.project(frame)
    def test_expiry_or_release_is_not_a_guard_rejection_attempt(self):
        t=self.target
        for editor in ('create','chat','scripts'):t.open(editor);t.sdk.screen=editor
        t.editor.body['current'].update(text='retry-'+RUN,focused=True)
        with self.flow.serialized():
            self.flow.load();actions=LifecycleActions(self.flow,self.flow.owner);held=actions.pending(control=True).hold(RUN);reader=actions.pending(control=True);reader.release_owned(RUN,held['commit']['observation']['eventId'])
            facts,_=self.project(self.flow.collect()[0]);self.assertEqual((0,0),(facts['deferredInputs'],facts['staleAttempts']))

if __name__=='__main__':unittest.main()
