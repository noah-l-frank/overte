"""Real durable editor/token/session/readers over explicit UI/native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_editor import PicoLifecycleEditor,run_create_world_back
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
from adapters.pico4.lifecycle_world import PicoLifecycleWorld
from adapters.script_journey.history import unpack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import TokenCreateUI
from adapters.token_lifecycle_ui import TokenLifecycleUI
from self_tests.test_token_create_ui import Controls
from self_tests.test_normal_create_adapter import NativeCreate
from self_tests.test_token_lifecycle_ui import Boundary as FieldBoundary
from self_tests.test_pico_lifecycle_world import Native,BINDING,RUN
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests.test_pico_lifecycle_join import XTransport
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from feature_journeys.fixtures import context


class LifecycleEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='lifecycle-editor-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.path=self.root/'lifecycle-editor-owner.json'
        self.native=Native();self.binding=BINDING|dict(sessionId='3'*32)
        self.model=NativeCreate(self.root);self.model.tablet=False;self.model.page='home'
        self.controls=Controls(self.model);self.controls.instance='3'*32;self.controls.generation='2'*32;self.controls.pid=123
        self.field=FieldBoundary();self.lock=ScriptSourceLock(self.root/'script-sources.lock')
        self.transport=FakeTransport();original_stage=self.transport.stage;self.lost_tablet=False;self.ignore_tablet=False
        def stage(envelope,profile):
            disk=unpack(json.loads(self.path.read_text())['payload'])[0]
            self.assertEqual(envelope,disk['tablet']['envelope']);result=original_stage(envelope,profile)
            if not self.ignore_tablet:self.native.ui.shown=self.native.ui.home=self.model.tablet=True
            return result
        self.transport.stage=stage;original_status=self.transport.read_status
        def status(**kwargs):
            if self.lost_tablet and kwargs.get('expected_sequence') is not None:raise NativeUIError('Explicit lost tablet ack')
            return original_status(**kwargs)|dict(updatedEpochMs=self.native.epoch())
        self.transport.read_status=status
        self.session=PicoOpenXrAdapterSession(self.transport,'explicit-editor-target',self.root);self.session.begin(self.binding['processIdentity'])
        original_input=self.field.input
        def field_input(*args,**kwargs):
            disk=unpack(json.loads(self.path.read_text())['payload'])[0];self.assertIsNone(disk['inputs'][-1]['consumed'])
            try:return original_input(*args,**kwargs)
            finally:
                if self.native.ui.rows:
                    self.native.ui.rows[0].update(focused=self.field.focused,text=self.field.text);self.native.ui.raised=self.field.focused
                self.controls.sequence=self.field.sequence
        self.field.input=field_input
        outer=self
        class Route:
            def capture(self):return outer.controls.capture()
            def activate(self,identifier,*,reference):
                disk=unpack(json.loads(outer.path.read_text())['payload'])[0];intent=disk['inputs'][-1]['intent']
                outer.assertEqual(identifier,intent['controlId']);outer.controls.intents.append(intent)
                outer.controls.input(identifier,'activate',reference)
                outer.field.sequence=outer.controls.sequence;outer.field.clock=outer.model.clock
                if outer.model.page=='create' and not outer.native.ui.rows:
                    outer.native.create();outer.native.ui.rows[0]['focused']=False;outer.native.ui.raised=False;outer.native.ui.home=False
        self.route_io=Route();self.owner=self.make();self.owner.prepare()
    def make(self):
        source=self.native.sources()[0];source.source_lock=self.lock
        route=TokenCreateUI(self.route_io,lambda _v:None,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        field=TokenLifecycleUI(self.field,lambda _v:None,RUN,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        return PicoLifecycleEditor(self.path,RUN,self.binding,source,self.session,route,field,self.lock)
    def focused(self):
        self.owner.tablet();self.owner.open_create();return self.owner.focus_create()
    def joined(self):
        tablet=self.transport
        class Transport(XTransport):
            def stage(self,envelope,profile):
                if envelope['commands'][0]['operation']=='tablet.open':return tablet.stage(envelope,profile)
                return super().stage(envelope,profile)
        transport=Transport(self.native,self.root/'lifecycle-world-owner.json')
        transport.back_path=self.root/'lifecycle-x-back-owner.json';tablet.envelopes=transport.envelopes
        self.session.transport=transport;self.composed_transport=transport
        world=PicoLifecycleWorld(*self.native.sources(),self.session,transport.path,RUN,self.binding,lambda:self.native.alive,self.lock,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        back=PicoLifecycleBack(self.native.sources()[0],self.session,transport.back_path,RUN,self.binding,lambda:self.native.alive,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep,source_lock=self.lock)
        return PicoLifecycleXJoin(world,back,self.root/'lifecycle-x-join.json')
    def test_normal_tablet_create_empty_focus_unicode_are_independently_observed_and_journaled(self):
        result=self.focused();self.assertEqual(('create','',True,True,1),(result['editor'],result['text'],result['focused'],result['keyboard'],result['generation']))
        identity=result['originalId'];typed=self.owner.type_create();self.assertEqual(context(RUN)['unicode'],typed['text'])
        self.assertEqual(identity,typed['originalId']);self.assertEqual('typed',self.owner.state['phase'])
        self.assertEqual([],self.model.entities);self.assertEqual(1,len(self.transport.envelopes))
        self.assertTrue(all(row['consumed'] is not None for row in self.owner.state['inputs']))
        restored=self.make();self.assertEqual(typed,restored.observe());self.assertTrue(self.path.exists())
    def test_opened_unfocused_original_context_already_has_generation_one(self):
        self.owner.tablet();opened=self.owner.open_create()
        self.assertEqual(('create','',1,False,False),(opened['editor'],opened['text'],opened['generation'],opened['focused'],opened['keyboard']))
        self.assertEqual('opened',self.owner.state['phase']);self.assertEqual(opened,self.owner.observe())
    def test_late_report_copy_native_clock_jump_is_rejected_after_final_result_build_in_reconcile_and_observe(self):
        self.owner.tablet();self.owner.open_create();report=self.owner.report;clock=self.owner.source.clock_ms
        def late():
            result=report();self.owner.source.clock_ms=lambda:clock()+2000;return result
        before=self.native.clock
        with patch.object(self.owner,'report',side_effect=late),self.assertRaises(NativeUIError):self.owner.focus_create()
        self.assertEqual(before,self.native.clock);self.assertEqual('focused',self.owner.state['phase']);self.assertEqual(1,len(self.field.calls))
        self.owner.source.clock_ms=clock
        with patch.object(self.owner,'report',side_effect=late),self.assertRaises(NativeUIError):self.owner.observe()
        self.assertEqual(before,self.native.clock);self.assertEqual(1,len(self.field.calls));self.assertTrue(self.path.exists())
    def test_lost_tablet_ack_only_reconciles_original_grant_and_source_without_toggling_again(self):
        self.lost_tablet=True
        with self.assertRaises(NativeUIError):self.owner.tablet()
        self.lost_tablet=False;restored=self.make();self.assertEqual('none',restored.reconcile()['editor']);self.assertEqual('tablet-open',restored.state['phase'])
        self.assertEqual(1,len(self.transport.envelopes))
        with self.assertRaises(NativeUIError):restored.tablet()
        self.assertEqual(1,len(self.transport.envelopes))
    def test_tablet_ack_without_original_visible_home_is_not_open_or_replayed(self):
        self.ignore_tablet=True
        with self.assertRaises(NativeUIError):self.owner.tablet()
        with self.assertRaises(NativeUIError):self.make().reconcile()
        self.assertEqual(1,len(self.transport.envelopes));self.assertEqual('tablet-issued',self.owner.state['phase'])
    def test_uncertain_ime_recovers_only_original_effect_on_same_objects_without_resend(self):
        self.focused();self.field.lost=True
        with self.assertRaises(NativeUIError):self.owner.type_create()
        self.field.lost=False;restored=self.make();result=restored.reconcile()
        self.assertEqual(context(RUN)['unicode'],result['text']);self.assertEqual('typed',restored.state['phase'])
        self.assertEqual(2,len(self.field.calls))
        with self.assertRaises(NativeUIError):restored.type_create()
        self.assertEqual(2,len(self.field.calls))
    def test_ignored_focus_and_ime_cursor_do_not_become_keyboard_or_text_effects(self):
        self.owner.tablet();self.owner.open_create();self.field.ignore={'activate'}
        with self.assertRaises(NativeUIError):self.owner.focus_create()
        self.assertEqual('focusing',self.owner.state['phase']);self.assertEqual(1,len(self.field.calls))
        with self.assertRaises(NativeUIError):self.make().reconcile()
        self.assertEqual(1,len(self.field.calls))
    def test_ignored_ime_advances_only_input_cursor_and_never_types_or_retries(self):
        self.focused();self.field.ignore={'replace'}
        with self.assertRaises(NativeUIError):self.owner.type_create()
        with self.assertRaises(NativeUIError):self.make().reconcile()
        self.assertEqual('typing',self.owner.state['phase']);self.assertEqual('',self.field.text)
        self.assertEqual(2,len(self.field.calls))
    def test_lost_create_entry_answer_adopts_actual_original_page_without_repeating_entry(self):
        self.owner.tablet();original=self.route_io.activate
        def lost(identifier,**options):
            original(identifier,**options)
            if identifier=='create.entry':raise NativeUIError('Explicit lost original Create click response')
        self.route_io.activate=lost
        with self.assertRaises(NativeUIError):self.owner.open_create()
        self.route_io.activate=original;restored=self.make();self.assertEqual('create',restored.reconcile()['editor'])
        self.assertEqual('opened',restored.state['phase']);self.assertEqual(1,[row[0] for row in self.controls.inputs].count('create.entry'))
        with self.assertRaises(NativeUIError):restored.open_create()
        self.assertEqual(1,[row[0] for row in self.controls.inputs].count('create.entry'))
    def test_failed_pretransport_owner_write_prevents_any_controller_or_normal_input(self):
        with patch.object(self.owner.store,'write',side_effect=OSError('Explicit failed fsync')),self.assertRaises(NativeUIError):self.owner.tablet()
        self.assertEqual([],self.transport.envelopes);self.assertEqual([],self.controls.inputs);self.assertEqual([],self.field.calls)
    def test_foreign_field_identity_after_focus_cannot_receive_owned_unicode(self):
        self.focused();self.field.field='8'*32
        with self.assertRaises(NativeUIError):self.owner.type_create()
        self.assertEqual('',self.field.text);self.assertEqual(1,len(self.field.calls));self.assertTrue(self.path.exists())
    def test_normal_draft_original_blocked_consumption_neutral_and_x_are_composed_without_context_retirement(self):
        joined=self.joined();result=run_create_world_back(self.owner,joined)
        self.assertEqual((1,[],0.,'none','',0,False,False),(result['worldAttempts'],result['heldInputs'],result['worldDisplacement'],
            result['editor'],result['text'],result['generation'],result['focused'],result['keyboard']))
        self.assertTrue(result['back']['routeObserved']);self.assertTrue(result['back']['retainedContext']);self.assertFalse(result['back']['editorRetired'])
        self.assertEqual(['tablet.open','input.move','controller.button'],[row['commands'][0]['operation'] for row in self.composed_transport.envelopes])
        self.assertEqual('quiet',joined.world.state['attempts'][0]['phase']);self.assertEqual('typed',self.owner.state['phase'])
        self.assertTrue(all(path.exists() for path in (self.path,joined.world.store.path,joined.back.store.path,joined.store.path)))
        with patch.object(self.owner,'observe',side_effect=AssertionError('Historical typed editor is no longer current')):
            repeated=run_create_world_back(self.owner,joined)
        self.assertEqual(result['back'],repeated['back']);self.assertEqual(3,len(self.composed_transport.envelopes))
    def test_composed_lost_world_ack_reconciles_original_consumption_without_retyping_or_resending(self):
        joined=self.joined();original=self.composed_transport.stage
        def stage(envelope,profile):
            if envelope['commands'][0]['operation']=='input.move':self.composed_transport.fail='ack'
            return original(envelope,profile)
        self.composed_transport.stage=stage
        with self.assertRaises(NativeUIError):run_create_world_back(self.owner,joined)
        self.assertEqual('typed',self.owner.state['phase']);self.assertEqual(2,len(self.composed_transport.envelopes))
        self.composed_transport.stage=original;self.composed_transport.fail=None;result=run_create_world_back(self.make(),joined)
        self.assertEqual(1,result['worldAttempts']);self.assertEqual(3,len(self.composed_transport.envelopes));self.assertEqual(2,len(self.field.calls))
    def test_composed_lost_x_ack_reconciles_original_back_without_requesting_another_press(self):
        joined=self.joined();original=self.composed_transport.stage
        def stage(envelope,profile):
            if envelope['commands'][0]['operation']=='controller.button':self.composed_transport.fail='ack'
            return original(envelope,profile)
        self.composed_transport.stage=stage
        with self.assertRaises(NativeUIError):run_create_world_back(self.owner,joined)
        self.assertEqual(1,self.composed_transport.back_count);self.composed_transport.fail=None
        result=run_create_world_back(self.make(),joined)
        self.assertTrue(result['back']['retainedContext']);self.assertEqual(1,self.composed_transport.back_count)
    def test_exact_typed_original_is_rechecked_before_first_world_transport_write(self):
        joined=self.joined();joined.world.prepare();self.focused();self.owner.type_create()
        for identifier,text in (('9'*32,context(RUN)['unicode']),(self.owner.state['originalId'],'')):
            self.native.ui.rows[0]['text']=text
            with self.subTest(identifier=identifier,text=text),self.assertRaises(NativeUIError):joined.world.world_input(editor_id=identifier)
        self.assertEqual(1,len(self.composed_transport.envelopes));self.assertEqual([],joined.world.state['attempts'])
    def test_prior_world_attempt_without_original_typed_source_cannot_be_adopted_for_x(self):
        joined=self.joined();joined.world.prepare();self.focused();self.owner.type_create()
        self.native.ui.rows[0]['text']='';joined.world.world_input();self.native.ui.rows[0]['text']=context(RUN)['unicode']
        with self.assertRaises(NativeUIError):run_create_world_back(self.make(),joined)
        self.assertEqual(0,self.composed_transport.back_count);self.assertEqual(2,len(self.composed_transport.envelopes))
    def test_composed_result_final_copy_native_jump_cannot_escape_final_freshness(self):
        joined=self.joined();report=joined.world.report;clock=joined.world.axes.clock_ms
        class LateCopy(dict):
            def update(self,*args,**options):
                result=super().update(*args,**options);joined.world.axes.clock_ms=lambda:clock()+2000;return result
        def wrapped(*args):return LateCopy(report(*args))
        with patch.object(joined.world,'report',side_effect=wrapped),self.assertRaises(NativeUIError):run_create_world_back(self.owner,joined)
        self.assertEqual('observed',joined.state['phase']);self.assertEqual(3,len(self.composed_transport.envelopes))
        self.assertTrue(self.path.exists());self.assertTrue(joined.store.path.exists())


if __name__=='__main__':unittest.main()
