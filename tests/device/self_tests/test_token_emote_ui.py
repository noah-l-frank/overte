"""Independent synthetic widget model, without native Rig or feature effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import TokenEmoteUI,NAMES,snapshot,same_reference


class EmoteBoundary:
    def __init__(self):
        self.clock=0.;self.page=False;self.tablet=True;self.active='';self.offset=0
        self.instance='a'*32;self.generation='b'*32;self.source_sequence=self.command_sequence=0
        self.actions=[];self.intents=[];self.fault=None;self.moving_until=0.;self.before_input=None
        self.transform=lambda value:value
    def sleep(self,seconds):self.clock+=seconds
    def intent(self,value):
        self.intents.append(deepcopy(value))
        if self.fault=='intent':raise NativeUIError('Synthetic missing input intent')
    def capture(self):
        self.source_sequence+=1;moving=self.clock<self.moving_until
        def row(identifier,**fields):
            value=dict(id=identifier,enabled=True,focused=False,inputReady=True);value.update(fields)
            value['token']=hashlib.sha256(repr((value,self.active,self.offset)).encode()).hexdigest()[:32];return value
        controls=[]
        if self.tablet:
            controls=[row('tablet.home')]
            if not self.page:controls.append(row('emote.entry'))
            else:
                controls += [row('emote.page',inputReady=False,profile='phone-native-chooser-v1',activeName=self.active,
                    names=list(NAMES),componentSourceSha256='c'*64),
                    row('emote.grid',contentY=self.offset*60.,originY=0.,contentHeight=600.,viewportHeight=240.,
                        moving=moving,dragging=False,inputReady=not moving)]
                controls += [row('emote.play.'+name,name=name,index=index,highlighted=self.active==name,inputReady=not moving)
                    for index,name in enumerate(NAMES) if self.offset<=index<self.offset+4]
        value=dict(emoteControlsVersion=1,open=self.tablet,ready=True,controls=controls,
            scope=dict(instance=self.instance,generation=self.generation,sourceSequence=self.source_sequence,
                sequence=self.command_sequence,elapsedMs=round(self.clock*1000),capturedEpochMs=20000+round(self.clock*1000),processId=31))
        return self.transform(value)
    def current(self,identifier,token):
        rows=[row for row in self.capture()['controls'] if row['id']==identifier]
        need(len(rows)==1 and rows[0]['token']==token and rows[0]['inputReady'])
    def activate(self,identifier,*,token):
        self.current(identifier,token);self.command_sequence+=1;self.actions.append(identifier)
        if self.fault=='ignored':return
        if identifier=='emote.entry':self.page=True
        elif identifier=='tablet.home':self.page=False
        elif identifier.startswith('emote.play.'):
            name=identifier[len('emote.play.'):];self.active='' if self.active==name else name
    def scroll(self,identifier,direction,*,token):
        self.current(identifier,token);need(identifier=='emote.grid' and direction in ('up','down'))
        self.command_sequence+=1;self.actions.append(direction)
        if self.fault=='ignored-scroll':return
        self.offset=max(0,min(6,self.offset+(-2 if direction=='up' else 2)));self.moving_until=self.clock+.2


class EmoteIO:
    def __init__(self,boundary):self.boundary=boundary
    def capture(self):return self.boundary.capture()
    def activate(self,identifier,*,reference):
        if self.boundary.before_input:self.boundary.before_input()
        row=same_reference(reference,self.capture(),identifier);self.boundary.activate(identifier,token=row['token'])
    def scroll(self,identifier,direction,*,reference):
        row=same_reference(reference,self.capture(),identifier);self.boundary.scroll(identifier,direction,token=row['token'])


class EmoteUiTests(unittest.TestCase):
    def ui(self):
        model=EmoteBoundary();return model,TokenEmoteUI(EmoteIO(model),model.intent,monotonic=lambda:model.clock,sleep=model.sleep)
    def test_all_ten_actual_buttons_and_offscreen_grid_are_reached_with_original_inputs(self):
        model,ui=self.ui();ui.open()
        for name in NAMES:ui.play(name)
        self.assertEqual('Love',model.active);self.assertIn('down',model.actions)
        ui.cancel();self.assertEqual('',model.active);ui.close();self.assertFalse(model.page)
        self.assertEqual(1,model.actions.count('emote.entry'))
        self.assertTrue(all(value['original']['scope']['sequence']+1==value['sequence']
            and any(row['id']==value['controlId'] for row in value['original']['controls']) for value in model.intents))
    def test_actual_widget_changes_are_not_reported_as_animation_measurements(self):
        model,ui=self.ui();ui.open();self.assertIsNone(ui.play('Waving'))
        self.assertEqual('Waving',ui.row(ui.capture(),'emote.page')['activeName'])
        self.assertNotIn('animation',ui.capture());self.assertNotIn('poseProgress',ui.capture())
    def test_ignored_play_can_consume_input_without_fabricating_actual_rig_success(self):
        model,ui=self.ui();ui.open();model.fault='ignored';ui.play('Crying')
        self.assertEqual('',model.active);self.assertEqual('emote.play.Crying',model.actions[-1])
    def test_ignored_open_and_scroll_fail_without_replaying_the_uncertain_input(self):
        model,ui=self.ui();model.fault='ignored'
        with self.assertRaises(NativeUIError):ui.open()
        self.assertEqual(['emote.entry'],model.actions)
        model,ui=self.ui();ui.open();model.fault='ignored-scroll'
        with self.assertRaises(NativeUIError):ui.play('Love')
        self.assertEqual(1,model.actions.count('down'));self.assertNotIn('emote.play.Love',model.actions)
    def test_failed_durable_intent_sends_no_input(self):
        model,ui=self.ui();model.fault='intent'
        with self.assertRaises(NativeUIError):ui.open()
        self.assertEqual([],model.actions)
    def test_foreign_recreated_or_changed_original_button_is_never_adopted(self):
        for change in ('generation','active','sequence'):
            model,ui=self.ui();ui.open()
            def replaced():
                if change=='generation':model.generation='e'*32
                elif change=='active':model.active='Love'
                else:model.command_sequence+=1
            model.before_input=replaced
            with self.subTest(change=change),self.assertRaises(NativeUIError):ui.play('Crying')
            self.assertNotIn('emote.play.Crying',model.actions)
    def test_duplicate_missing_foreign_or_expectation_bearing_widget_metadata_is_refused(self):
        model,ui=self.ui();ui.open();original=ui.capture()
        for fault in ('duplicate','missing-grid','foreign-highlight','wrong-name','bool-index','expected'):
            value=deepcopy(original)
            button=next(row for row in value['controls'] if row['id'].startswith('emote.play.'))
            if fault=='duplicate':value['controls'].append(deepcopy(button))
            elif fault=='missing-grid':value['controls']=[row for row in value['controls'] if row['id']!='emote.grid']
            elif fault=='foreign-highlight':button['highlighted']=True
            elif fault=='wrong-name':button['name']='Love'
            elif fault=='bool-index':button['index']=True
            else:button['expectedAnimation']='Crying'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):snapshot(value)
    def test_source_sequence_clock_or_birth_regression_is_refused(self):
        for fault in ('sequence','clock','instance','pid'):
            model,ui=self.ui();original=ui.capture()
            def changed(value):
                scope=value['scope']
                if fault=='sequence':scope['sourceSequence']=original['scope']['sourceSequence']
                elif fault=='clock':scope['capturedEpochMs']-=1
                elif fault=='instance':scope['instance']='e'*32
                else:scope['processId']=32
                return value
            model.transform=changed
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):ui.capture()
    def test_unknown_names_direct_sit_variants_or_grid_activation_are_rejected(self):
        model,ui=self.ui();ui.open();before=list(model.actions)
        for name in ('Sit1','Sit2','Sit3','Unknown',True):
            with self.subTest(name=name),self.assertRaises(NativeUIError):ui.play(name)
        with self.assertRaises(NativeUIError):ui.input('emote.grid')
        self.assertEqual(before,model.actions)
    def test_motion_must_settle_and_whole_input_budget_cannot_be_extended_by_each_scroll(self):
        model,ui=self.ui();ui.open();model.moving_until=.5;ui.play('Crying');self.assertGreaterEqual(model.clock,.5)
        model,ui=self.ui();ui.open();original=model.scroll
        def slow(*args,**kwargs):original(*args,**kwargs);model.clock+=8
        model.scroll=slow
        with self.assertRaises(NativeUIError):ui.play('Love')
        self.assertNotIn('emote.play.Love',model.actions);self.assertLessEqual(model.actions.count('down'),3)


if __name__=='__main__':unittest.main()
