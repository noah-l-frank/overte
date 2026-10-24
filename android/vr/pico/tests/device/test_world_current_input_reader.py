"""Current sources, real shared Session, pure publication and independent state.

Controller/DOM/entity dependencies are explicit models. Native source/Qt/JNI
bodies have a separate original counter; no device or target effect from ACK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from adapters.pico4.world_current_document import PicoWorldCurrentDocument
from adapters.pico4.world_current_input import PicoWorldCurrentInput,validate,command
from adapters.pico4.world_current_ray import PicoWorldCurrentRay
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from adapters.android.input_geometry import _axis,_multiply
from adapters.pico4.world_browser_ray import rotate
from self_tests.test_pico_world_browser_ray import WorldBoundary,RUN,URL,OWNER,VIEW
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import compile_envelope,PrototypeOpenXrInputConsumer


class CurrentBoundary(WorldBoundary):
    def __init__(self,lock):
        super().__init__(lock);self.focused=False;self.focused_control='text';self.pid=123;self.dom_sequence=0;self.sequence=0
        self.doc_packets={};self.doc_raw='';self.input_raw='';self.sends=[];self.native_mono=100000;self.java_mono=200000
        self.doc_source=PicoWorldCurrentDocument(self.send,lambda:self.doc_raw,self.clock,self.guard,self.pid,lock,
            monotonic=lambda:self.elapsed,sleep=lambda delay:setattr(self,'elapsed',self.elapsed+delay))
        self.current=PicoWorldCurrentInput(self.doc_source,self.send,lambda:self.input_raw)
    def pair(self):
        base={key:VIEW[key] for key in ('handle','creation','grant','page','url','sourceUrl')}
        native=dict(base,itemInstance='2'*32,sourceIdentity=VIEW['sourceIdentity'],created=True,authorized=True,
            sessionActive=True,suspended=False,loading=False,capturedEpochMs=self.epoch,capturedMonotonicMs=self.native_mono)
        java=dict(base,ownerCurrent=True,active=True,foreground=True,windowFocused=True,destroyed=False,closing=False,loading=False,
            capturedEpochMs=self.epoch,capturedElapsedMs=self.java_mono)
        return dict(native=native,java=java)
    def send(self,call):
        self.sends.append(deepcopy(call));self.sequence+=1;self.dom_sequence+=1
        head=dict(commandId=call['commandId'],runId=RUN,ownerToken=OWNER,instance='3'*32,sequence=self.sequence,processId=self.pid,
            requestedEpochMs=self.epoch,requestedMonotonicMs=self.native_mono,capturedEpochMs=self.epoch,capturedMonotonicMs=self.native_mono,status='ready')
        a=self.pair();b=self.pair();finish={key:VIEW[key] for key in ('handle','creation','page','url')};finish.update(grant=1,finishedEpochMs=19000)
        if call['operation']=='observe-current-document':
            dom=dict(webDOMVersion=1,requestId=call['commandId'],instance='c'*32,sequence=self.dom_sequence,capturedEpochMs=self.epoch,
                document=dict(runId=RUN,href=VIEW['url'],responseId='d'*32,readyState='complete'),
                editor=dict(text='',focused=self.focused and self.focused_control=='text'),attempts=[],echoes=[])
            wrapper=dict(before=a['java'],domRaw=json.dumps(json.dumps(dom)),after=b['java'])
            packet=dict(head,picoWorldCurrentDocumentVersion=1,source=dict(authorityBefore=a,authorityAfter=b,originalFinish=finish,
                documents=[deepcopy(finish)],domRaw=json.dumps(wrapper),dom=dom))
            self.doc_packets[call['commandId']]=deepcopy(packet);self.doc_raw=json.dumps(packet);return
        # Reuse the existing pure geometry fixture. No old wire is returned.
        super().send(call);old=self.packet;geometry=json.loads(json.loads(old['source']['geometryRaw']))
        focused=self.focused and self.focused_control==call['control']
        geometry['sequence']=self.dom_sequence;geometry['editor']=dict(focused=focused,text='',cursor=0,anchor=0)
        wrapper=dict(before=a['java'],geometryRaw=json.dumps(json.dumps(geometry)),after=b['java'])
        doc=self.doc_packets[call['documentNonce']]
        source=dict(documentReference={key:doc[key] for key in ('commandId','instance','sequence')},originalFinish=finish,
            authorityBefore=a,authorityAfter=b)
        if call['operation']=='measure-current-ray':source.update(geometryRaw=json.dumps(wrapper),worldRay=old['source']['worldRay'])
        else:source.update(focusRaw=json.dumps(wrapper),nativeEditor=dict(text='',cursor=0,anchor=0,absoluteCursor=0,
                kind=('url' if self.focused_control=='foreign' else 'text') if focused else '',sensitive=False,focused=focused,enabled=focused))
        self.input_raw=json.dumps(dict(head,picoWorldCurrentInputVersion=1,documentNonce=call['documentNonce'],source=source))
    def consume_published(self,envelope,profile):
        """Actual existing model query consumer; no focus from performed/ACK."""
        compiled=compile_envelope(envelope,profile);consumer=PrototypeOpenXrInputConsumer(compiled)
        key=profile['controls']['scalars']['right.trigger'];pose_key=profile['controls']['poses']['right.grip'];previous=0.;presses=0
        rotation=_multiply(_axis([0,0,1],math.pi/2),_axis([1,0,0],math.pi/4));inverse=[-rotation[0],-rotation[1],-rotation[2],rotation[3]]
        correction=_multiply(_axis([1,0,0],-math.pi/8),_multiply(inverse,_multiply(_axis([0,1,0],math.pi),_axis([1,0,0],math.pi/2))))
        for event in compiled['events']:
            consumer.sync_actions(event['atMs']);scalar=consumer.query('float',key);pose=consumer.query('pose',pose_key)
            value=scalar['currentState'] if scalar and scalar['isActive'] else 0.
            if value>=.95 and previous<.95 and pose and pose['isActive']:
                actual=pose['currentState'];origin=actual['positionMeters'];direction=rotate(_multiply(actual['orientation'],correction),[0,1,0])
                distance=(self.position[2]-origin[2])/direction[2];point=[origin[i]+distance*direction[i] for i in range(3)]
                uv=[(point[0]-self.position[0])/self.dimensions[0]+.5,.5-(point[1]-self.position[1])/self.dimensions[1]]
                x,y=uv[0]*640,uv[1]*480
                if distance>0 and 80<=x<=240 and 60<=y<=140:self.focused=True;presses+=1
            previous=value
        duration=compiled['watchdogDeadlineMs'];self.epoch+=duration;self.elapsed+=duration/1000;self.native_mono+=duration;self.java_mono+=duration
        return compiled,presses


class WorldCurrentInputReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='world-current-input-reader-');self.tmp._finalizer.detach();self.root=Path(self.tmp.name);self.root.chmod(0o700)
        print('Retained CurrentInput model originals:',self.root,flush=True)
        self.lock=ScriptSourceLock(self.root/'script-sources.lock');self.b=CurrentBoundary(self.lock);self.source=self.b.current
        self.transport=FakeTransport();self.session=PicoOpenXrAdapterSession(self.transport,'current-source-model',self.root);self.session.begin('123:456')
        self.events=[]
    def read(self,operation='measure-current-ray'):return self.source.read(RUN,URL,OWNER,operation,'text')
    def publisher(self,*,intent=None,stream=None,publication=None,stage=None):
        original=self.transport.stage
        def transport(envelope,profile,*,before_publish):
            self.b.under_input=True
            try:before_publish(deepcopy(envelope));return original(envelope,profile,before_publish=before_publish)
            finally:self.b.under_input=False
        self.transport.stage=transport
        def save(value):
            self.events.append('intent');PrivateFeatureState(self.root/'intent.json').write(value,None)
            if intent:intent(value)
        def stream_save(value):
            self.events.append('stream');PrivateFeatureState(self.root/'stream.json').write(value,None)
            if stream:stream(value)
        def publish(value):
            self.events.append('publish');self.assertTrue(self.b.under_input)
            self.assertEqual(value,PrivateFeatureState(self.root/'stream.json').read())
            if publication:publication(value)
        if stage is None:stage=lambda pose,**hooks:self.session.stage('123:456','input.primary',pose,**hooks)
        return PicoWorldCurrentRay(self.source,stage,save,stream_save,publish)
    def test_actual_existing_session_then_independent_modeled_consumption_and_new_focus_dom(self):
        packet=self.read();original=self.source.original();self.assertEqual(2,len(self.b.sends));owner=self.publisher();receipt=owner.publish()
        self.assertEqual(['intent','stream','publish','publish'],self.events);self.assertEqual(1,len(self.transport.envelopes));self.assertFalse(self.b.focused)
        self.assertNotIn('featureSucceeded',receipt);self.assertNotIn('focused',receipt)
        self.read('observe-current-focus')
        with self.assertRaises(NativeUIError):owner.check_focus(receipt,self.source.original())
        compiled,presses=self.b.consume_published(receipt['streamEnvelope'],self.session.profile);self.assertEqual(1,presses)
        self.assertGreaterEqual(compiled['watchdogDeadlineMs'],2000)
        focus=self.read('observe-current-focus');checked=owner.check_focus(receipt,self.source.original())
        self.assertTrue(focus['source']['nativeEditor']['focused']);self.assertEqual(self.source.original(),checked)
        self.assertEqual(original,receipt['calibrationOriginal']);self.assertNotEqual(packet['capturedEpochMs'],focus['capturedEpochMs'])
        with self.assertRaises(NativeUIError):owner.publish()
        self.assertEqual(1,len(self.transport.envelopes))
    def test_readonly_schema_and_fresh_lease_refuses_unknown_ops_before_sources(self):
        for op in ('commit-current-text','observe-current-consumption','focus','reload'):
            with self.assertRaises(NativeUIError):self.read(op)
        self.assertEqual([],self.b.sends)
        packet=self.read();original=self.source.original();validate(packet,original['request'],123,self.b.epoch,original['documentOriginal'])
        for mutate in (lambda p:p.update(picoWorldCurrentInputVersion=True),lambda p:p.update(documentNonce='0'*32),
                       lambda p:p['source']['documentReference'].update(sequence=True),lambda p:p['source']['originalFinish'].update(page=True),
                       lambda p:p['source']['authorityAfter']['native'].update(grant=99),lambda p:p['source'].update(extra=1)):
            bad=deepcopy(packet);mutate(bad)
            with self.assertRaises(NativeUIError):validate(bad,original['request'],123,self.b.epoch,original['documentOriginal'])
    def test_actual_outer_second_exit_native_future_host_and_guard_refuse(self):
        for fault in ('native','future','host','guard'):
            with self.subTest(fault=fault):
                self.b=CurrentBoundary(self.lock);self.source=self.b.current;held=self.lock.held;exits=[]
                @contextmanager
                def release():
                    with held():yield
                    self.assertIsNone(self.lock._owner);exits.append(True)
                    if len(exits)==2:
                        if fault=='native':self.b.epoch+=2000
                        if fault=='future':self.b.epoch-=2000
                        if fault=='host':self.b.elapsed+=2
                        if fault=='guard':self.source.guard=lambda:False
                with patch.object(self.lock,'held',release),self.assertRaises(NativeUIError):self.read()
                self.assertEqual(2,len(exits));self.assertEqual(2,len(self.b.sends));self.assertIsNone(self.source.last)
    def test_slow_final_grammar_frozen_clock_and_nested_refuse_without_resend(self):
        import adapters.pico4.world_current_input as module
        original=module.validate
        def late(*args,**kwargs):
            result=original(*args,**kwargs)
            if self.lock._owner is None:self.b.elapsed+=2
            return result
        with patch.object(module,'validate',late),self.assertRaises(NativeUIError):self.read()
        self.assertIsNone(self.source.last);self.assertEqual(2,len(self.b.sends))
        with self.lock.held():
            with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(2,len(self.b.sends))
    def test_original_clock_skew_plus_outer_exit_host_age_is_combined(self):
        send=self.b.doc_source.send;held=self.lock.held;exits=[]
        def earlier_original(call):
            # Original producer clock is within allowed 250-ms clock skew;
            # preserve those raw times after restoring the current clock.
            self.b.epoch-=200
            try:return send(call)
            finally:self.b.epoch+=200
        @contextmanager
        def slow_release():
            with held():yield
            exits.append(True)
            if len(exits)==2:self.b.elapsed+=1.4
        self.b.doc_source.send=earlier_original
        with patch.object(self.lock,'held',slow_release),self.assertRaises(NativeUIError):self.read()
        self.assertEqual(2,len(exits));self.assertEqual(2,len(self.b.sends));self.assertIsNone(self.source.last)
    def test_mutable_return_or_original_cannot_change_warm_authority(self):
        packet=self.read();original=self.source.original();packet['source']['worldRay']['entityId']='foreign'
        owner=self.publisher();self.assertTrue(owner.publish()['publication']['performed'])
        self.assertEqual(original,self.source.original())
        self.read();self.source.last_request['control']='bridge';owner=self.publisher()
        with self.assertRaises(NativeUIError):owner.publish()
        self.assertEqual(1,len(self.transport.envelopes))
    def test_slow_parent_cas_frozen_native_prevents_first_publication(self):
        self.read();owner=self.publisher(intent=lambda _value:setattr(self.b,'elapsed',self.b.elapsed+2))
        with self.assertRaises(NativeUIError):owner.publish()
        self.assertTrue(owner.issued and owner.failed);self.assertEqual([],self.transport.envelopes)
    def test_slow_locked_stream_or_publication_has_no_native_reentry_or_replay(self):
        base=self.root
        for phase in ('stream','publish'):
            with self.subTest(phase=phase):
                self.root=base/phase;self.root.mkdir(mode=0o700);self.lock=ScriptSourceLock(self.root/'script-sources.lock')
                self.b=CurrentBoundary(self.lock);self.source=self.b.current;self.read();self.transport=FakeTransport()
                self.session=PicoOpenXrAdapterSession(self.transport,'current-source-model',self.root);self.session.begin('123:456')
                delay=lambda _value:setattr(self.b,'elapsed',self.b.elapsed+2)
                owner=self.publisher(stream=delay if phase=='stream' else None,publication=delay if phase=='publish' else None)
                with self.assertRaises(NativeUIError):owner.publish()
                self.assertTrue(owner.issued and owner.failed);self.assertEqual([],self.transport.envelopes)
    def test_lost_applied_return_keeps_actual_stream_and_no_second_input(self):
        self.read()
        def stage(pose,**hooks):
            self.session.stage('123:456','input.primary',pose,**hooks);raise RuntimeError('lost actual return')
        owner=self.publisher(stage=stage)
        with self.assertRaises(NativeUIError):owner.publish()
        self.assertEqual(1,len(self.transport.envelopes));self.assertTrue((self.root/'stream.json').exists())
        with self.assertRaises(NativeUIError):owner.publish()
        self.assertEqual(1,len(self.transport.envelopes))
    def test_changed_grant_after_publication_never_resolves_old_input(self):
        self.read();owner=self.publisher();receipt=owner.publish();self.b.consume_published(receipt['streamEnvelope'],self.session.profile)
        pair=self.b.pair
        def changed():
            result=pair();result['native']['grant']+=1;result['java']['grant']+=1;return result
        self.b.pair=changed;self.read('observe-current-focus')
        with self.assertRaises(NativeUIError):owner.check_focus(receipt,self.source.original())
        self.assertEqual(1,len(self.transport.envelopes))

    def test_actual_foreign_focus_transition_cannot_resolve_original_text_ray(self):
        self.read();owner=self.publisher();receipt=owner.publish()
        self.b.consume_published(receipt['streamEnvelope'],self.session.profile)
        self.assertTrue(self.b.focused and self.b.focused_control=='text')
        send=self.source.send;transitions=[]
        def foreign_field_before_new_geometry(call):
            self.assertEqual('observe-current-focus',call['operation'])
            self.assertEqual('foreign',call['control'])
            # Actual new Doc has already observed text focus. A subsequent
            # independently modeled field-focus callback changes the producer
            # before its new geometry/native-editor original is captured.
            self.assertTrue(decode(self.b.doc_raw)['source']['dom']['editor']['focused'])
            self.b.focused_control='foreign';transitions.append(True)
            return send(call)
        from adapters.pico4.world_current_input import decode
        with patch.object(self.source,'send',foreign_field_before_new_geometry):
            packet=self.source.read(RUN,URL,OWNER,'observe-current-focus','foreign')
        focus=self.source.original();validate(packet,focus['request'],123,self.b.epoch,focus['documentOriginal'])
        self.assertEqual([True],transitions);self.assertEqual('url',packet['source']['nativeEditor']['kind'])
        self.assertTrue(packet['source']['nativeEditor']['focused'])
        self.assertTrue(decode(focus['documentOriginal']['raw'])['source']['dom']['editor']['focused'])
        PrivateFeatureState(self.root/'foreign-focus-originals.json').write(dict(
            calibrationOriginal=receipt['calibrationOriginal'],streamEnvelope=receipt['streamEnvelope'],focusOriginal=focus),None)
        with self.assertRaises(NativeUIError):owner.check_focus(receipt,focus)
        self.assertEqual(1,len(self.transport.envelopes))

    def test_actual_foreign_ray_and_foreign_focus_do_not_require_text_field_focus(self):
        self.b.focused_control='foreign'
        self.source.read(RUN,URL,OWNER,'measure-current-ray','foreign');owner=self.publisher();receipt=owner.publish()
        self.assertFalse(self.b.focused)
        self.b.consume_published(receipt['streamEnvelope'],self.session.profile)
        packet=self.source.read(RUN,URL,OWNER,'observe-current-focus','foreign');focus=self.source.original()
        from adapters.pico4.world_current_input import decode
        doc=decode(focus['documentOriginal']['raw'])
        self.assertFalse(doc['source']['dom']['editor']['focused'])
        self.assertTrue(packet['source']['nativeEditor']['focused']);self.assertEqual('url',packet['source']['nativeEditor']['kind'])
        validate(packet,focus['request'],123,self.b.epoch,focus['documentOriginal'])
        PrivateFeatureState(self.root/'matching-foreign-focus-originals.json').write(dict(
            calibrationOriginal=receipt['calibrationOriginal'],streamEnvelope=receipt['streamEnvelope'],focusOriginal=focus),None)
        self.assertEqual(focus,owner.check_focus(receipt,focus));self.assertEqual(1,len(self.transport.envelopes))

    def test_original_java_clock_skew_plus_slow_stream_cas_prevents_publication(self):
        pair=self.b.pair
        def original_earlier_java_capture():
            value=pair()
            # Java's actual producer wall clock is within the allowed native
            # skew. Both new raw transactions keep these original captures.
            value['java']['capturedEpochMs']=self.b.epoch-200
            return value
        self.b.pair=original_earlier_java_capture
        packet=self.read();original=self.source.original()
        validate(packet,original['request'],123,self.b.epoch,original['documentOriginal'])
        self.assertEqual(self.b.epoch-200,packet['source']['authorityBefore']['java']['capturedEpochMs'])
        clock=self.b.epoch
        owner=self.publisher(stream=lambda _command:setattr(self.b,'elapsed',self.b.elapsed+1.4))
        with self.assertRaises(NativeUIError):owner.publish()
        PrivateFeatureState(self.root/'java-clock-skew-stream-originals.json').write(dict(
            calibrationOriginal=original,actualEnvelopes=deepcopy(self.transport.envelopes),
            actualStream=PrivateFeatureState(self.root/'stream.json').read()),None)
        self.assertEqual(clock,self.b.epoch);self.assertGreaterEqual(self.b.elapsed,1.4)
        self.assertEqual([],self.transport.envelopes);self.assertTrue(owner.issued and owner.failed)


class WorldCurrentInputFactoryTests(unittest.TestCase):
    def setUp(self):
        import test_normal_scripts as original
        self.h=original.PicoNormalScriptsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.adapter,self.native=self.h.instance,self.h.native
        self.lock=self.adapter._script_journey()._lock(self.native.target)
    def test_actual_private_sources_and_normal_session_primary_keep_original_lock_and_no_ack_effect(self):
        from adapters.pico4.world_current_document import FILE as DOC_FILE
        from adapters.pico4.world_current_input import FILE as INPUT_FILE
        boundary=CurrentBoundary(self.lock);boundary.pid=int(self.native.identity.split(':')[0]);old_write=self.native.write_debug_app_file;old_read=self.native.read_debug_app_file
        def write(target,package,path,raw):
            call=json.loads(raw)
            if call.get('action')!='pico-world-web':return old_write(target,package,path,raw)
            boundary.epoch=self.native.epoch_milliseconds(target);boundary.send(call)
        def read(target,package,path,**options):
            if path=='files/overte-e2e/'+DOC_FILE:self.assertEqual({'attempts':1},options);return boundary.doc_raw
            if path=='files/overte-e2e/'+INPUT_FILE:self.assertEqual({'attempts':1},options);return boundary.input_raw
            return old_read(target,package,path,**options)
        transport=FakeTransport();session=PicoOpenXrAdapterSession(transport,self.native.target,self.lock.path.parent);session.begin(self.native.identity)
        intents=[];streams=[];publications=[];admissions=[]
        with patch.object(self.native,'write_debug_app_file',side_effect=write),patch.object(self.native,'read_debug_app_file',side_effect=read), \
             patch.object(self.adapter,'require_pico_session_identity',return_value=self.native.identity),patch.object(self.adapter,'pico_input_session',return_value=session):
            source=self.adapter._world_current_input_originals(self.native.target,source_lock=self.lock)
            self.assertIs(source.lock,self.lock);self.assertIs(source.documents.lock,self.lock);self.assertEqual([],transport.envelopes)
            with self.lock.held():
                with self.assertRaises(NativeUIError):source.read(RUN,URL,OWNER,'measure-current-ray','text')
            self.assertEqual([],boundary.sends)
            source.read(RUN,URL,OWNER,'measure-current-ray','text')
            publisher=self.adapter._world_current_ray(self.native.target,source=source,intent=intents.append,stream_intent=streams.append,
                before_publish=publications.append,admission=lambda:admissions.append(True))
            result=publisher.publish();self.assertEqual(1,len(admissions));self.assertEqual(1,len(transport.envelopes))
            self.assertEqual(1,len(intents));self.assertEqual(streams,[result['streamEnvelope']]);self.assertTrue(publications)
            self.assertIs(source.lock,self.lock);self.assertFalse(boundary.focused)
            self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
            self.assertEqual(['observe-current-document','measure-current-ray'],[v['operation'] for v in boundary.sends])
    def test_foreign_lock_or_non_source_refuses_private_ray_factory(self):
        from types import SimpleNamespace
        with self.assertRaises((ValueError,NativeUIError)):
            self.adapter._world_current_ray(self.native.target,source=SimpleNamespace(lock=self.lock),intent=lambda _:None,
                stream_intent=lambda _:None,before_publish=lambda _:None,admission=lambda:None)


if __name__=='__main__':unittest.main()
