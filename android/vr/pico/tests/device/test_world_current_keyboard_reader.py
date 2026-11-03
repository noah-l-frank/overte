"""No-build owning Host reader counters; every Native/Qt value is a model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
import time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device'),str(HERE)]
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.world_current_keyboard import PicoWorldCurrentKeyboard,command
from test_world_current_input_reader import CurrentBoundary,RUN,URL,OWNER
from test_world_current_consumption_reader import TraceBoundary


class KeyboardBoundary:
    def __init__(self,focus,retain):
        self.focus=focus;self.retained=retain;self.calls=[];self.getters=0;self.sequence=0;self.raw='';self.mutate=None
        self.source=PicoWorldCurrentKeyboard(focus.current,self.send,self.read,retain,lambda:None)
    def send(self,call):
        self.calls.append(deepcopy(call));self.sequence+=1;b=self.focus;focus=b.current.last;a=b.pair();z=b.pair()
        key_id='00000000-0000-0000-0000-000000000009';anchor='00000000-0000-0000-0000-000000000400'
        key=dict(id=key_id,layer=0,type=0,effectiveUtf16Hex='0061',switchLayer=0,pressed=False,ready=True,visible=True,
            hostType='local',entityType='Text',parentId=anchor,createdEpochUs='10000000000',entityInstance='a'*32,
            geometry=dict(worldCenter=[0,1.3,-2.5],worldRotation=[0,0,0,1],worldDimensions=[.08,.08,.02]))
        keyboard=dict(keyboardVersion=1,instance='b'*32,sequence=self.sequence,capturedEpochMs=b.epoch,
            created=True,enabled=True,raised=True,inputToHud=False,inputTarget=a['native']['sourceIdentity'][len('web-entity:'):],
            focusedEntity=None,anchor=anchor,activeLayer=0,caps=False,preferMallets=False,ready=True,traceKeyboardObject=None,
            acceptedSequence=0,lastAccepted=None,sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],headPosition=[0,1.6,-.35],
            hmd=dict(display='DECLARED_MODEL',active=True,visible=True,mounted=True),
            layerMembership=[dict(layer=0,entityIds=[key_id]),dict(layer=1,entityIds=['00000000-0000-0000-0000-000000000010'])],keys=[key])
        source=dict(focusReference={k:focus[k] for k in ('commandId','instance','sequence')},
            nativeBefore=dict(native=a['native'],finish=deepcopy(focus['source']['originalFinish'])),
            nativeAfter=dict(native=z['native'],finish=deepcopy(focus['source']['originalFinish'])),
            nativeEditor=deepcopy(focus['source']['nativeEditor']),keyboard=keyboard)
        packet=dict(picoWorldCurrentKeyboardVersion=1,commandId=call['commandId'],runId=RUN,ownerToken=OWNER,
            focusNonce=call['focusNonce'],instance='c'*32,sequence=self.sequence,processId=b.pid,requestedEpochMs=b.epoch,
            capturedEpochMs=b.epoch,requestedMonotonicMs=b.native_mono,capturedMonotonicMs=b.native_mono,status='ready',source=source)
        if self.mutate:self.mutate(packet)
        self.raw=json.dumps(packet)
    def read(self):self.getters+=1;return self.raw


class WorldCurrentKeyboardReaderTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='pico-current-keyboard-reader-'));self.root.chmod(0o700)
        print('Retained modeled Keyboard originals:',self.root,flush=True)
        self.records=[];self.lock=ScriptSourceLock(self.root/'sources.lock');self.b=CurrentBoundary(self.lock);self.b.focused=True
        self.boundary=KeyboardBoundary(self.b,self.retain);self.source=self.boundary.source
    def retain(self,value):
        path=self.root/('raw-%03d.json'%len(self.records));path.write_text(json.dumps(value,sort_keys=True));path.chmod(0o600)
        self.records.append(deepcopy(value));return len(self.records)-1
    def read(self):return self.source.read(RUN,URL,OWNER)

    def test_complete_membership_and_actual_active_rows_leave_inactive_click_geometry_unavailable(self):
        value=self.read();self.assertEqual(2,len(value['source']['keyboard']['layerMembership']))
        self.assertEqual(1,len(value['source']['keyboard']['keys']));self.source.require_warm(self.source.original())
        self.assertEqual(1,len(self.boundary.calls));self.assertEqual(1,self.boundary.getters)
        self.assertIn('focusOriginal',self.records[0]);self.assertEqual(self.boundary.raw,self.records[1]['raw'])

    def test_raw_malformed_and_oversize_are_retained_before_parser_and_limit_refusal(self):
        for raw in ('{','x'*65537,42):
            with self.subTest(rawType=type(raw).__name__,size=len(raw) if isinstance(raw,str) else 0):
                b=KeyboardBoundary(self.b,self.retain);b.source.read_raw=lambda:raw
                with self.assertRaises((NativeUIError,ValueError,TypeError)):b.source.read(RUN,URL,OWNER)
                self.assertEqual(raw,self.records[-1]['raw']);self.assertTrue(b.source.failed)
                sent=len(b.calls)
                with self.assertRaises(NativeUIError):b.source.read(RUN,URL,OWNER)
                self.assertEqual(sent,len(b.calls))

    def test_foreign_pid_focus_owner_and_malformed_utf16_are_retained(self):
        mutations=[lambda p:p.update(processId=124),lambda p:p.update(ownerToken='f'*32),
            lambda p:p['source']['keyboard']['keys'][0].update(effectiveUtf16Hex='d800'),
            lambda p:p['source']['keyboard']['layerMembership'][0]['entityIds'].append('00000000-0000-0000-0000-000000000010'),
            lambda p:p['source']['keyboard']['keys'][0].update(geometry=None)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                b=KeyboardBoundary(self.b,self.retain);b.mutate=mutate
                with self.assertRaises((NativeUIError,UnicodeError)):b.source.read(RUN,URL,OWNER)
                self.assertEqual(b.raw,self.records[-1]['raw']);self.assertTrue(b.source.failed)

    def test_original_pre_send_capacity_expiry_has_zero_native_keyboard_send(self):
        self.source.capacity=lambda:setattr(self.b,'elapsed',self.b.elapsed+1.6)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.boundary.calls);self.assertEqual(0,self.boundary.getters);self.assertTrue(self.source.failed)

    def test_original_pre_getter_capacity_expiry_has_zero_getter(self):
        calls=[]
        def capacity():
            calls.append(True)
            if len(calls)==2:self.b.elapsed+=1.6
        self.source.capacity=capacity
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.boundary.calls));self.assertEqual(0,self.boundary.getters);self.assertTrue(self.source.failed)

    def test_real_outer_source_exit_age_cannot_renew_capture(self):
        held=self.lock.held;fired=[]
        @contextmanager
        def release():
            with held():yield
            if self.boundary.calls and not fired:self.b.elapsed+=1.6;fired.append(True)
        self.lock.held=release
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([True],fired);self.assertEqual(self.boundary.raw,self.records[-1]['raw']);self.assertTrue(self.source.failed)

    def test_unavailable_and_ignored_ui_remain_observed_not_input_success(self):
        self.boundary.mutate=lambda p:p['source']['keyboard'].update(raised=False,ready=False)
        value=self.read();self.assertFalse(value['source']['keyboard']['raised'])
        from adapters.pico4.world_current_gesture import calibration
        with self.assertRaises(NativeUIError):calibration(self.source.original(),key_id=value['source']['keyboard']['keys'][0]['id'])
        self.assertEqual(1,len(self.boundary.calls))

    def test_getter_protocol_has_no_requested_key_text_or_input_operation(self):
        request=dict(schemaVersion=1,commandId='1'*32,action='pico-world-web',runId=RUN,fixtureUrl=URL,
            operation='observe-current-keyboard',ownerToken=OWNER,focusNonce='2'*32)
        command(request)
        for wrong in (dict(request,text='a'),dict(request,keyEntity='00000000-0000-0000-0000-000000000009'),dict(request,operation='type-key')):
            with self.assertRaises(NativeUIError):command(wrong)
        self.assertEqual([],self.b.sends)

    def test_malformed_original_document_and_focus_are_retained_in_optin_source(self):
        for source in ('document','input'):
            with self.subTest(source=source):
                b=CurrentBoundary(self.lock);b.focused=True
                b.doc_source.retain=b.current.retain=self.retain;b.doc_source.capacity=b.current.capacity=lambda:None
                if source=='document':b.doc_source.read_raw=lambda:'{'
                else:b.current.read_raw=lambda:'{'
                with self.assertRaises((NativeUIError,ValueError)):b.current.read(RUN,URL,OWNER,'observe-current-focus','text')
                self.assertEqual('{',self.records[-1]['raw'])

    def test_original_document_and_focus_capacity_expiry_prevents_their_actual_writer(self):
        for source in ('document','input'):
            with self.subTest(source=source):
                b=CurrentBoundary(self.lock);b.focused=True
                def capacity():b.elapsed+=1.6
                if source=='document':b.doc_source.capacity=capacity
                else:b.current.capacity=capacity
                with self.assertRaises(NativeUIError):b.current.read(RUN,URL,OWNER,'observe-current-focus','text')
                refused='observe-current-document' if source=='document' else 'observe-current-focus'
                self.assertFalse(any(c['operation']==refused for c in b.sends))

    def test_original_trace_capacity_expiry_has_zero_writer_or_getter(self):
        for delayed in (1,2):
            with self.subTest(delayed=delayed):
                b=CurrentBoundary(self.lock);b.focused=True;b.current.read(RUN,URL,OWNER,'observe-current-focus','text')
                trace=TraceBoundary(b);counter=[];getters=[]
                def capacity():
                    counter.append(True)
                    if len(counter)==delayed:b.elapsed+=1.6
                trace.source.capacity=capacity;trace.source.read_raw=lambda:(getters.append(True) or trace.raw)
                with self.assertRaises(NativeUIError):trace.source.arm()
                self.assertEqual(0 if delayed==1 else 1,len(trace.calls));self.assertEqual([],getters)
                self.assertTrue(trace.source.issued);self.assertTrue(trace.source.failed)

    def test_actual_native_source_runtime_gates_and_unchanged_product_branch_without_compiling(self):
        """Structural source proof only; this does not execute C++/Qt/Android."""
        def body(text,signature):
            start=text.index(signature);opening=text.index('{',start);depth=0
            for index in range(opening,len(text)):
                if text[index]=='{':depth+=1
                elif text[index]=='}':
                    depth-=1
                    if depth==0:return text[start:index+1]
            self.fail('unclosed source body')
        source=(ROOT/'interface/src/ui/Keyboard.cpp').read_text();trigger=body(source,'void Keyboard::handleTriggerBegin(')
        gate='if(_featureWorldKeyboardSequence>0 && QCoreApplication::arguments().contains("--testScript"))'
        gated=body(trigger,gate)
        self.assertIn('findEntityByEntityItemID',gated);self.assertIn('_featureWorldAccepted=',gated)
        self.assertLess(trigger.index('picoCurrentTraceTrigger'),trigger.index(gate))
        self.assertEqual(1,trigger.count('findEntityByEntityItemID'))
        # Exact reviewed pre-observer product body, excluding its already
        # existing compile-gated trace block. Off-test/newobserver work is zero.
        lines=[];depth=0
        for line in trigger.splitlines():
            if line.lstrip().startswith('#if') and 'OVERTE_E2E_FEATURE_TESTS' in line:depth+=1;continue
            if depth:
                if line.lstrip().startswith('#if'):depth+=1
                elif line.lstrip().startswith('#endif'):depth-=1
                continue
            lines.append(line)
        self.assertEqual('68319853c7acfca58333c3af5be597bc06ebc2b28379cfdf82ae4d198502b2c5',
                         hashlib.sha256('\n'.join(lines).encode()).hexdigest())
        observer=body(source,'QVariantMap Keyboard::featureWorldCurrentObservation(')
        self.assertLess(observer.index('--testScript'),observer.index('getEntityTree'))
        for setter in ('editEntity(','setRaised(','setUse3DKeyboard(','setIsPressed('):self.assertNotIn(setter,observer)
        bridge=(ROOT/'android/common/web/src/PicoWorldCurrentDocumentBridge.cpp').read_text()
        anchor=body(bridge,'PicoCurrentAnchor picoCurrentKeyboardAnchor(')
        self.assertLess(anchor.index('--testScript'),anchor.index('static QHash'))
        trace=(ROOT/'android/common/web/src/PicoWorldCurrentConsumptionE2E.inc').read_text()
        accessor=body(trace,'QString picoCurrentTraceKeyboardIdentity(')
        self.assertIn('constFind',accessor);self.assertNotIn('insert(',accessor);self.assertNotIn('consumeId(',accessor)

    def test_real_two_second_ack_keeps_old_calibration_historical_and_reads_fresh_focus(self):
        from adapters.pico4.world_current_gesture import PicoWorldCurrentGesture
        from adapters.pico4.world_current_focus_parent import focus_matches
        from openxr_input.adapter_session import PicoOpenXrAdapterSession
        from self_tests.test_pico_openxr_adapter_session import FakeTransport
        self.b.focused=False
        for source in (self.b.current,self.b.doc_source):source.monotonic=time.monotonic;source.sleep=time.sleep
        self.b.current.retain=self.b.doc_source.retain=self.retain
        started=time.monotonic();requested=self.b.clock()
        self.b.current.read(RUN,URL,OWNER,'measure-current-ray','text');old=self.b.current.original()
        session=PicoOpenXrAdapterSession(FakeTransport(),'DECLARED_WORLD_HOST_GESTURE',self.root);session.begin('123:456')
        intents=[];envelopes=[]
        def stage(pose,*,intent,before_publish):
            value=session.stage('123:456','input.primary',pose,intent=intent,before_publish=before_publish)
            time.sleep(2.01) # Actual Host elapsed, not a renewed/native model clock.
            return value
        owner=PicoWorldCurrentGesture(self.b.current,stage,intents.append,envelopes.append,lambda _value:None,started=started,requested=requested)
        result=owner.publish();self.assertGreaterEqual(time.monotonic()-started,2)
        self.assertEqual(old,result['calibrationOriginal']);self.assertEqual(1,len(envelopes));self.assertEqual(1,len(session.transport.envelopes))
        with self.assertRaises(NativeUIError):self.b.current.require_warm(old)
        _compiled,presses=self.b.consume_published(result['streamEnvelope'],session.profile);self.assertEqual(1,presses)
        self.b.current.read(RUN,URL,OWNER,'observe-current-focus','text');fresh=self.b.current.original()
        self.assertNotEqual(old['request']['commandId'],fresh['request']['commandId']);self.assertTrue(focus_matches(old,fresh))
        self.b.current.require_warm(fresh);self.assertLess(time.monotonic()-started,5)
        self.retain(dict(kind='actual-host-two-second-ack',intents=intents,envelopes=envelopes,receipt=result,freshFocus=fresh))


if __name__=='__main__':unittest.main()
