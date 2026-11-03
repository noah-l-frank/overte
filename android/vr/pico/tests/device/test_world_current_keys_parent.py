"""Normal Parent/Session/codec with explicit Native/Qt/XR/Java producer models.

No compiler/device runs. Model keys come from the actual layout, and effects
come from the compiled normal pointer gesture, never a requested text effect.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
import time
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device'),str(HERE)]
import test_world_current_focus_parent as focus_fixture
import test_world_current_consumption_reader as trace_fixture
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.world_current_keyboard import FILE as KEYBOARD_FILE
from adapters.pico4.world_current_document import FILE as DOCUMENT_FILE
from adapters.pico4.world_current_input import FILE as INPUT_FILE
from adapters.pico4.world_current_consumption import FILE as TRACE_FILE
from adapters.pico4.world_current_keys_parent import FOCUS,KEY
from adapters.pico4.world_browser_ray import rotate
from adapters.android.input_geometry import _axis,_multiply
from openxr_input.controller_protocol import compile_envelope,PrototypeOpenXrInputConsumer
from self_tests import test_pico_world_web_prefix as existing
from adapters.pico4.binding import create_adapter
from adapters.script_journey.history import unpack


class FactoryBase:
    def __init__(self,kind):self.kind=kind


# Obtain the original closure-defined functions without candidate/device IO.
# No cleanup action is called. This qualifies those actual factory functions,
# not candidate admission or the complete production adapter initialization.
Canonical=type(create_adapter(SimpleNamespace(kind='pico',action='cleanup'),FactoryBase))


class KeyboardTarget(focus_fixture.CurrentTarget):
    # Existing WorldTarget composes a narrow explicit method set rather than
    # inheriting the binding class. Bind the EXACT canonical new factories;
    # their normal Scriptlock/Session/type checks execute in these cases.
    _world_current_keyboard_originals=Canonical._world_current_keyboard_originals
    _world_current_gesture=Canonical._world_current_gesture
    _world_current_consumption_originals=Canonical._world_current_consumption_originals
    _world_current_owned_neutral=Canonical._world_current_owned_neutral
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.keyboard_instance=uuid.uuid4().hex;self.trace_keyboard=uuid.uuid4().hex
        self.key_sequence=self.accepted=0;self.accepted_original=None;self.layer=0;self.caps=False;self.trace_seen=False
        self.keyboard_raw='';self.trace_boundary=None;self.focus_sources=[];self.key_hits=[];self.ignore_keys=False
        self.key_hook=None;self.late_ack=False;self.malformed_keyboard=False;self.key_getters=0;self.key_sends=0
        self.layout=json.loads((ROOT/'interface/resources/config/keyboard.json').read_text())['layers']
        self.keys=[];namespace=uuid.uuid4()
        types={'caps':1,'close':2,'layer':3,'backspace':4,'space':5,'enter':6,'select_all':7,'copy':8,'cut':9,'paste':10,
               'cursor_up':11,'cursor_right':12,'cursor_down':13,'cursor_left':14}
        # These world entity transforms are DECLARED UI fixtures, not a GPU or
        # actual Keyboard observation. The real Python readers validate them.
        for layer,rows in enumerate(self.layout):
            for index,row in enumerate(rows):
                self.keys.append(dict(id=str(uuid.uuid5(namespace,str(layer)+':'+str(index))),layer=layer,
                    type=types.get(row.get('type'),0),label=row['key'],switchLayer=row.get('switchToLayer',0),
                    entityInstance=uuid.uuid4().hex,createdEpochUs='1700000000000000',
                    center=[(index%10-4.5)*.12,1.1+(3-index//10)*.12,-2.5]))
        status=self.transport.read_status
        def current_status(*,expected_nonce=None,expected_sequence=None):
            if expected_sequence is None and self.pending_current is not None:
                self.clock.sleep(max(0,2.01-(self.clock.now()-self.pending_current[2])))
                self.consume_current_stream()
            return status(expected_nonce=expected_nonce,expected_sequence=expected_sequence)
        self.transport.read_status=current_status
        stage=self.transport.stage
        def actual_ack(envelope,profile,*,before_publish=None):
            value=stage(envelope,profile,before_publish=before_publish)
            if self.late_ack and envelope['commands'][0]['operation']=='input.primary':self.clock.sleep(2.01);self.consume_current_stream()
            return value
        self.transport.stage=actual_ack

    def _native_feature_observer(self,target):
        native=super()._native_feature_observer(target);send=native.send
        def route(command):
            if command.get('action')=='pico-world-web':return self.current_send(command)
            return send(command)
        native.send=route;return native

    def _world_current_input_originals(self,target,*,source_lock):
        # The actual canonical factory, with only its Native/OS transport
        # supplied by the explicit producer model above.
        source=Canonical._world_current_input_originals(self,target,source_lock=source_lock)
        self.focus_sources.append(source);return source

    def read(self,target,package,path,**kwargs):
        if path.endswith(DOCUMENT_FILE):return self.doc_raw
        if path.endswith(INPUT_FILE):return self.input_raw
        if path.endswith(KEYBOARD_FILE):self.key_getters+=1;return self.keyboard_raw
        if path.endswith(TRACE_FILE):return self.trace_boundary.raw
        return super().read(target,package,path,**kwargs)

    def current_send(self,call):
        if call['operation']=='observe-current-keyboard':
            self.lock.assert_held();self.consume_current_stream();self.key_sends+=1;self.key_sequence+=1
            start=self.clock.tick();mono=round(self.clock.now()*1000);a=self.pair();focus=json.loads(self.input_raw)
            rows=[]
            for original in self.keys:
                if original['layer']!=self.layer:continue
                key={k:deepcopy(v) for k,v in original.items() if k not in ('label','center')}
                text=original['label'].upper() if self.caps else original['label']
                key.update(effectiveUtf16Hex=text.encode('utf-16-be').hex(),pressed=False,ready=True,
                    visible=key['layer']==self.layer,hostType='local',entityType='Text',parentId=str(uuid.UUID(int=400)),
                    geometry=dict(worldCenter=deepcopy(original['center']),worldRotation=[0,0,0,1],worldDimensions=[.08,.08,.02]) if key['layer']==self.layer else None)
                rows.append(key)
            key=dict(keyboardVersion=1,instance=self.keyboard_instance,sequence=self.key_sequence,capturedEpochMs=self.clock.tick(),
                created=True,enabled=True,raised=True,inputToHud=False,inputTarget=self.entity_id,focusedEntity=self.entity_id,
                anchor=str(uuid.UUID(int=400)),activeLayer=self.layer,caps=self.caps,preferMallets=False,ready=True,
                traceKeyboardObject=self.trace_keyboard if self.trace_seen else None,
                acceptedSequence=self.accepted,lastAccepted=deepcopy(self.accepted_original),
                hmd=dict(display='DECLARED_NATIVE_HMD_MODEL',active=True,visible=True,mounted=True),
                sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],headPosition=[0,1.6,-.35],
                layerMembership=[dict(layer=i,entityIds=[k['id'] for k in self.keys if k['layer']==i]) for i in range(len(self.layout))],keys=rows)
            if self.key_hook:self.key_hook(key)
            b=self.pair();source=dict(focusReference={k:focus[k] for k in ('commandId','instance','sequence')},
                nativeBefore=dict(native=a['native'],finish=deepcopy(self.documents[-1])),
                nativeAfter=dict(native=b['native'],finish=deepcopy(self.documents[-1])),
                nativeEditor=deepcopy(focus['source']['nativeEditor']),keyboard=key)
            packet=dict(picoWorldCurrentKeyboardVersion=1,commandId=call['commandId'],runId=call['runId'],ownerToken=call['ownerToken'],
                focusNonce=call['focusNonce'],instance='5'*32,sequence=self.key_sequence,processId=31,requestedEpochMs=start,
                requestedMonotonicMs=mono,capturedEpochMs=self.clock.tick(),capturedMonotonicMs=round(self.clock.now()*1000),status='ready',source=source)
            self.keyboard_raw='{' if self.malformed_keyboard else json.dumps(packet,separators=(',',':'))
            PrivateFeatureState(self.current_originals/('keyboard-'+str(self.key_sequence)+'.json')).write(dict(call=call,raw=self.keyboard_raw),None)
            return
        if call['operation'] in ('arm-current-consumption','observe-current-consumption'):
            trace_started=self.clock.tick();trace_mono=round(self.clock.now()*1000)
            if call['operation']=='arm-current-consumption':
                matches=[s for s in self.focus_sources if s.last_request and s.last_request['commandId']==call['focusNonce']]
                if len(matches)!=1:raise AssertionError('model received a foreign focus original')
                model=self
                class Focus:
                    current=matches[0];pid=31
                    @property
                    def epoch(self):return model.clock.epoch()
                    @property
                    def native_mono(self):return round(model.clock.now()*1000)
                    def pair(self):return model.pair()
                self.trace_boundary=trace_fixture.TraceBoundary(Focus())
            self.trace_boundary.send(call)
            packet=json.loads(self.trace_boundary.raw)
            # Standalone TraceBoundary's default scope belongs to its own
            # component. This producer serves the actual current World run.
            packet.update(runId=call['runId'],ownerToken=call['ownerToken'],requestedEpochMs=trace_started,requestedMonotonicMs=trace_mono,
                capturedEpochMs=self.clock.tick(),capturedMonotonicMs=round(self.clock.now()*1000))
            self.trace_boundary.raw=json.dumps(packet);return
        return super().current_send(call)

    def consume_current_stream(self):
        if not self.pending_current or self.clock.now()-self.pending_current[2]<2:return
        if not self.current['focused']:return super().consume_current_stream()
        envelope,profile,_started=self.pending_current;self.pending_current=None
        compiled=compile_envelope(envelope,profile);consumer=PrototypeOpenXrInputConsumer(compiled);previous=0.;picked=[]
        rotation=_multiply(_axis([0,0,1],math.pi/2),_axis([1,0,0],math.pi/4));inverse=[-rotation[0],-rotation[1],-rotation[2],rotation[3]]
        correction=_multiply(_axis([1,0,0],-math.pi/8),_multiply(inverse,_multiply(_axis([0,1,0],math.pi),_axis([1,0,0],math.pi/2))))
        for event in compiled['events']:
            consumer.sync_actions(event['atMs']);trigger=consumer.query('float',profile['controls']['scalars']['right.trigger'])
            grip=consumer.query('pose',profile['controls']['poses']['right.grip']);value=trigger['currentState'] if trigger and trigger['isActive'] else 0.
            if value>=.95 and previous<.95 and grip and grip['isActive']:
                pose=grip['currentState'];origin=pose['positionMeters'];direction=rotate(_multiply(pose['orientation'],correction),[0,1,0])
                distance=(-2.5-origin[2])/direction[2];point=[origin[i]+distance*direction[i] for i in range(3)]
                hits=[k for k in self.keys if k['layer']==self.layer and abs(point[0]-k['center'][0])<.04 and abs(point[1]-k['center'][1])<.04]
                if distance>0 and len(hits)==1 and not self.ignore_keys:
                    key=hits[0];picked.append(key['id']);self.accept_key(key)
            previous=value
        self.key_hits.extend(picked)
        PrivateFeatureState(self.current_originals/('key-consumed-'+str(envelope['sequence'])+'.json')).write(
            dict(envelope=envelope,compiled=compiled,picked=picked),None)

    def accept_key(self,key):
        self.accepted+=1;self.accepted_original=dict(sequence=self.accepted,keyEntity=key['id'],keyType=key['type'],
            keyEntityInstance=key['entityInstance'],
            layerBefore=self.layer,capsBefore=self.caps,epochMs=self.clock.tick())
        if key['type'] in (1,3):
            self.caps=not self.caps if key['type']==1 else False;self.layer=key['switchLayer'];return
        text=key['label'].upper() if self.caps else key['label'];before=deepcopy(self.current)
        self.current['text']+=text;self.current['sequence']+=1
        trace=self.trace_boundary
        if trace is None:return
        self.trace_seen=True
        event=uuid.uuid4().hex;authority=self.pair()['native'];target=self.entity_id;units=text.encode('utf-16-be').hex()
        trace.frame('keyboard-event',dict(keyboardObject=self.trace_keyboard,keyEntity=key['id'],keyType=key['type'],eventType='press',
            key=ord(text[0]),modifiers=0,textUtf16Hex=units,requestedEntity=target),event=event)
        trace.frame('application-target',dict(eventType='press',requestedEntity=target,focusedBefore=target,focusedAfter=target,
            handlerMatchesWindow=True,focusItemMatches=True,handled=True),event=event)
        editor=dict(text=before['text'],cursor=len(before['text']),anchor=len(before['text']),absoluteCursor=len(before['text']),
            kind='text',sensitive=False,focused=True,enabled=True)
        trace.frame('native-input',dict(authority=authority,editor=editor,eventType='key-press',key=ord(text[0]),modifiers=0,
            textUtf16Hex=units,commitUtf16Hex=None,preeditUtf16Hex=None,replacementStart=None,replacementLength=None,attributes=[],accepted=True),event=event)
        command=json.dumps(dict(text=text),separators=(',',':'))
        jni=dict({k:authority[k] for k in ('handle','creation','grant','page','url','sourceIdentity')},
            commandUtf16Hex=command.encode('utf-16-be').hex(),commandUtf8Hex=command.encode().hex())
        trace.frame('jni-command',jni,event=event)
        release=uuid.uuid4().hex
        trace.frame('keyboard-event',dict(keyboardObject=self.trace_keyboard,keyEntity=key['id'],keyType=key['type'],eventType='release',
            key=ord(text[0]),modifiers=0,textUtf16Hex=units,requestedEntity=target),event=release)
        trace.frame('application-target',dict(eventType='release',requestedEntity=target,focusedBefore=target,focusedAfter=target,
            handlerMatchesWindow=True,focusItemMatches=True,handled=False),event=release)
        java={k:jni[k] for k in ('handle','grant','page','url','commandUtf16Hex','commandUtf8Hex')}
        trace.frame('java-entry',dict(java,isMainThread=True,capturedEpochMs=self.clock.tick(),capturedElapsedMs=1000+round(self.clock.now()*1000)),event=event)
        pair=self.pair();trace.frame('java-consume',dict(java,before=pair['java'],after=self.pair()['java']),event=event);trace.terminal=True


class WorldCurrentKeysParentTests(unittest.TestCase):
    run=existing.WorldWebPrefixTests.run
    stop=existing.WorldWebPrefixTests.stop;activate=existing.WorldWebPrefixTests.activate;call=existing.WorldWebPrefixTests.call
    baseline=existing.WorldWebPrefixTests.baseline;open=existing.WorldWebPrefixTests.open
    def setUp(self):
        with patch.object(existing,'WorldTarget',KeyboardTarget):existing.WorldWebPrefixTests.setUp(self)

    def test_normal_real_session_focus_caps_ascii_prefix_retains_unicode_action(self):
        self.open();call=self.call(1);started=time.perf_counter();result=self.primary.focus_current_keyboard_prefix(call)
        elapsed=time.perf_counter()-started;timing=self.root/'normal-component-timing.json'
        timing.write_text(json.dumps(dict(actualCallSeconds=elapsed,originalCallLimitSeconds=60,result=result),indent=2));timing.chmod(0o600)
        self.assertLess(elapsed,60,'the real Host call must fit the original adapter deadline')
        self.assertEqual('Overte ',result['typedPrefix']);self.assertEqual('00e4',result['blockedCodepoint'])
        self.assertFalse(result['commonActionComplete']);self.assertEqual('acting',self.primary.state['phase'])
        self.assertEqual(call,self.primary.state['active']);self.assertEqual(1,len(self.primary.state['completed']))
        self.assertEqual('Overte ',self.target.current['text']);self.assertEqual(9,len(self.target.key_hits))
        rows=[r for r in self.primary.state['inputs'] if FOCUS in r['original'] or KEY in r['original']]
        self.assertEqual(10,len(rows));self.assertTrue(all(r['complete'] for r in rows))
        self.assertEqual(2,rows[0]['original'][FOCUS]);self.assertEqual('blocked',rows[-1]['original']['phase'])
        self.assertEqual(1,len({r['original']['callStartedMonotonic'] for r in rows}))
        before=deepcopy(self.target.transport.envelopes)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with cold.lock.held():cold.read()
        with self.assertRaises(NativeUIError):cold.focus_current_keyboard_prefix(call)
        self.assertEqual(before,self.target.transport.envelopes)

    def test_late_two_second_ack_old_current_ray_refuses_without_replay(self):
        self.open();self.target.late_ack=True;call=self.call(1)
        with self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual(3,len(self.target.transport.envelopes));self.assertEqual('acting',self.primary.state['phase'])
        self.assertFalse(self.primary.state['inputs'][-1]['complete'])

    def test_ignored_key_retains_actual_input_and_raw_without_second_send(self):
        self.open();self.target.ignore_keys=True;call=self.call(1)
        with self.assertRaises(NativeUIError):self.primary.focus_current_keyboard_prefix(call)
        self.assertEqual('',self.target.current['text']);self.assertEqual([],self.target.key_hits)
        self.assertEqual(4,len(self.target.transport.envelopes));row=self.primary.state['inputs'][-1]
        self.assertFalse(row['complete']);self.assertIsNotNone(row['envelope']);self.assertTrue(row['original']['records'])


class WorldCurrentKeyJoinTests(unittest.TestCase):
    """The real Host join over explicit event DTOs, not a Native execution."""
    def values(self):
        from adapters.pico4.world_current_keys_parent import consumed
        key=dict(id=str(uuid.UUID(int=9)),type=0,effectiveUtf16Hex='0061');target=str(uuid.UUID(int=77));keyboard='8'*32
        event=dict(keyboardObject=keyboard,keyEntity=key['id'],keyType=0,eventType='press',key=97,modifiers=0,
            textUtf16Hex='0061',requestedEntity=target)
        app=dict(eventType='press',requestedEntity=target,handled=True,handlerMatchesWindow=True,focusItemMatches=True)
        native=dict(accepted=True,eventType='key-press',key=97,modifiers=0,textUtf16Hex='0061')
        jni=dict(commandUtf16Hex=json.dumps(dict(text='a')).encode('utf-16-be').hex())
        press={k:('vr-key',v) for k,v in {'keyboard-event':event,'application-target':app,'native-input':native,
            'jni-command':jni,'java-entry':dict(isMainThread=True),'java-consume':{}}.items()}
        release={'keyboard-event':('vr-key',dict(event,eventType='release')),
                 'application-target':('vr-key',dict(app,eventType='release',handled=False))}
        trace=SimpleNamespace(arm_packet={},last=dict(raw=json.dumps(dict(source=dict(terminal=True)))),events=dict(press=press,release=release))
        return consumed,trace,key,dict(traceKeyboardObject=None),dict(traceKeyboardObject=keyboard)

    def test_actual_release_truth_false_handled_is_retained_and_joined(self):
        function,trace,key,before,after=self.values();function(trace,key,before,after)
        self.assertFalse(trace.events['release']['application-target'][1]['handled'])

    def test_missing_foreign_or_control_modified_release_never_completes_key(self):
        for mutation in ('missing','foreign-instance','modified','foreign-target','wrong-application'):
            with self.subTest(mutation=mutation):
                function,trace,key,before,after=self.values()
                if mutation=='missing':del trace.events['release']
                elif mutation=='foreign-instance':trace.events['release']['keyboard-event'][1]['keyboardObject']='9'*32
                elif mutation=='modified':trace.events['release']['keyboard-event'][1]['modifiers']=1
                elif mutation=='foreign-target':trace.events['release']['keyboard-event'][1]['requestedEntity']=str(uuid.UUID(int=78))
                else:trace.events['press']['application-target'][1]['eventType']='release'
                with self.assertRaises(NativeUIError):function(trace,key,before,after)

    def test_ignored_native_or_foreign_jni_text_does_not_borrow_actual_dom(self):
        for mutation in ('ignored','foreign-jni','foreign-key'):
            with self.subTest(mutation=mutation):
                function,trace,key,before,after=self.values()
                if mutation=='ignored':trace.events['press']['native-input'][1]['accepted']=False
                elif mutation=='foreign-key':trace.events['press']['native-input'][1]['key']=98
                else:trace.events['press']['jni-command'][1]['commandUtf16Hex']=json.dumps(dict(text='b')).encode('utf-16-be').hex()
                with self.assertRaises(NativeUIError):function(trace,key,before,after)


if __name__=='__main__':unittest.main()
