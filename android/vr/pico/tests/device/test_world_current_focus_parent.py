"""Existing normal World Parent/Script/Session joined to new current sources.

Android DOM/editor and input consumer are explicit host models. HTTP bytes,
ordinary token controls, SDK compiler/consumer and actual Python owners run.
No native/Keyboard/Actor/stereo or whole recipe qualification is inferred.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.world_current_document import PicoWorldCurrentDocument
from adapters.pico4.world_current_input import PicoWorldCurrentInput
from adapters.pico4.world_current_ray import bind_current_ray
from adapters.pico4.world_current_focus_parent import FIELD
from adapters.pico4.world_browser_ray import rotate
from adapters.android.input_geometry import _axis,_multiply
from adapters.script_journey.history import unpack
from feature_journeys.phase_fixture import PhasePending
from openxr_input.controller_protocol import compile_envelope,PrototypeOpenXrInputConsumer
from self_tests import test_pico_world_web_prefix as existing
from self_tests.pico_world_web_prefix_fixture import WorldTarget


class CurrentTarget(WorldTarget):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.current_queries=[];self.doc_packets={};self.doc_raw=self.input_raw=''
        self.current_scope=uuid.uuid4().hex;self.item_instance=uuid.uuid4().hex;self.current_sequence=0
        self.pending_current=None;self.consume_current=False;self.pointer_hits=0;self.lose_current=False
        self.factory_entries=[];self.source_entry_hook=None
        self.current_originals=self.path/'current-source-originals';self.current_originals.mkdir(mode=0o700)
        original=self.transport.stage
        def stage(envelope,profile,*,before_publish=None):
            if envelope['commands'][0]['operation']!='input.primary':return original(envelope,profile,before_publish=before_publish)
            if before_publish:before_publish(deepcopy(envelope))
            self.transport.envelopes.append(deepcopy(envelope))
            self.pending_current=(deepcopy(envelope),deepcopy(profile),self.clock.now())
            if self.lose_current:raise RuntimeError('Applied current stream publication return lost')
            return dict(sequence=envelope['sequence'])
        self.transport.stage=stage
    def consume_current_stream(self):
        if not self.pending_current or self.clock.now()-self.pending_current[2]<2:return
        envelope,profile,_=self.pending_current;self.pending_current=None
        compiled=compile_envelope(envelope,profile);consumer=PrototypeOpenXrInputConsumer(compiled);previous=0.;queries=[]
        rotation=_multiply(_axis([0,0,1],math.pi/2),_axis([1,0,0],math.pi/4));inverse=[-rotation[0],-rotation[1],-rotation[2],rotation[3]]
        correction=_multiply(_axis([1,0,0],-math.pi/8),_multiply(inverse,_multiply(_axis([0,1,0],math.pi),_axis([1,0,0],math.pi/2))))
        for event in compiled['events']:
            consumer.sync_actions(event['atMs']);trigger=consumer.query('float',profile['controls']['scalars']['right.trigger'])
            grip=consumer.query('pose',profile['controls']['poses']['right.grip']);value=trigger['currentState'] if trigger and trigger['isActive'] else 0.
            queries.append(dict(atMs=event['atMs'],trigger=deepcopy(trigger),grip=deepcopy(grip)))
            if value>=.95 and previous<.95 and grip and grip['isActive']:
                pose=grip['currentState'];origin=pose['positionMeters'];direction=rotate(_multiply(pose['orientation'],correction),[0,1,0])
                distance=(-2.5-origin[2])/direction[2];point=[origin[i]+distance*direction[i] for i in range(3)]
                x=((point[0]/1.8)+.5)*int(1.8*39.3701*40);y=(.5-(point[1]-1.4)/2.2)*int(2.2*39.3701*40)
                if distance>0 and 80<=x<=240 and 60<=y<=140 and not self.ignore_ray:
                    self.pointer_hits+=1;self.current['focused']=True
            previous=value
        PrivateFeatureState(self.current_originals/('consumed-'+str(envelope['sequence'])+'.json')).write(
            dict(envelope=envelope,compiled=compiled,queries=queries),None)
    def pair(self):
        view={key:self.documents[-1][key] for key in ('handle','creation','grant','page','url')};view['sourceUrl']=self.source
        epoch=self.clock.tick();native=dict(view,itemInstance=self.item_instance,sourceIdentity='web-entity:'+self.entity_id,
            created=True,authorized=True,sessionActive=True,suspended=False,loading=False,
            capturedEpochMs=epoch,capturedMonotonicMs=round(self.clock.now()*1000))
        java=dict(view,ownerCurrent=True,active=True,foreground=True,windowFocused=True,destroyed=False,closing=False,loading=False,
            capturedEpochMs=self.clock.tick(),capturedElapsedMs=1000+round(self.clock.now()*1000))
        return dict(native=native,java=java)
    def current_send(self,call):
        self.lock.assert_held();self.consume_current_stream();self.current_queries.append(deepcopy(call));self.current_sequence+=1
        start=self.clock.tick();mono=round(self.clock.now()*1000);a=self.pair()
        if call['operation']=='observe-current-document':
            dom=self.dom_packet(call['commandId'])['source']['dom'];b=self.pair();wrapper=dict(before=a['java'],domRaw=json.dumps(json.dumps(dom)),after=b['java'])
            source=dict(authorityBefore=a,authorityAfter=b,originalFinish=deepcopy(self.documents[-1]),documents=deepcopy(self.documents),domRaw=json.dumps(wrapper),dom=dom)
            version=dict(picoWorldCurrentDocumentVersion=1)
        else:
            self.current['sequence']+=1;geometry=self.geometry(call);geometry['sequence']=self.current['sequence'];b=self.pair()
            doc=self.doc_packets[call['documentNonce']];wrapper=dict(before=a['java'],geometryRaw=json.dumps(json.dumps(geometry)),after=b['java'])
            source=dict(documentReference={key:doc[key] for key in ('commandId','instance','sequence')},originalFinish=deepcopy(self.documents[-1]),authorityBefore=a,authorityAfter=b)
            if call['operation']=='measure-current-ray':
                # Existing declared geometric producer only, no second target
                # transport read: its formula uses the actual model entity.
                legacy=dict(call,operation='measure-ray',**{key:self.documents[-1][key] for key in ('handle','creation','grant','page')})
                legacy.pop('documentNonce');WorldTarget.send(self,legacy);ray=json.loads(self.raw)['source']['worldRay']
                source.update(geometryRaw=json.dumps(wrapper),worldRay=ray)
            else:
                focused=self.current['focused'];text=self.current['text'];units=len(text.encode('utf-16-le'))//2
                source.update(focusRaw=json.dumps(wrapper),nativeEditor=dict(text=text,cursor=units,anchor=units,absoluteCursor=units,
                    kind='text' if focused else '',sensitive=False,focused=focused,enabled=focused))
            version=dict(picoWorldCurrentInputVersion=1,documentNonce=call['documentNonce'])
        packet=dict(version,commandId=call['commandId'],runId=call['runId'],ownerToken=call['ownerToken'],instance=self.current_scope,
            sequence=self.current_sequence,processId=31,requestedEpochMs=start,requestedMonotonicMs=mono,
            capturedEpochMs=self.clock.tick(),capturedMonotonicMs=round(self.clock.now()*1000),status='ready',source=source)
        PrivateFeatureState(self.current_originals/('query-'+str(self.current_sequence)+'.json')).write(dict(command=deepcopy(call),raw=json.dumps(packet)),None)
        if call['operation']=='observe-current-document':self.doc_packets[call['commandId']]=deepcopy(packet);self.doc_raw=json.dumps(packet)
        else:self.input_raw=json.dumps(packet)
    def _world_current_input_originals(self,target,*,source_lock):
        need=__import__('adapters.native_feature_observation',fromlist=['need']).need
        need(target==self.selector and source_lock is self.lock and self.lock._owner is None);self.factory_entries.append(True)
        docs=PicoWorldCurrentDocument(self.current_send,lambda:self.doc_raw,self.clock.epoch,self.guard,31,self.lock,
            monotonic=self.clock.now,sleep=self.clock.sleep)
        source=PicoWorldCurrentInput(docs,self.current_send,lambda:self.input_raw)
        if self.source_entry_hook:self.source_entry_hook(source)
        return source
    def _world_current_ray(self,target,**kwargs):
        return bind_current_ray(self,target,kwargs['source'],kwargs['intent'],kwargs['stream_intent'],kwargs['before_publish'],kwargs['admission'])


class WorldCurrentFocusParentTests(unittest.TestCase):
    run=existing.WorldWebPrefixTests.run
    stop=existing.WorldWebPrefixTests.stop;activate=existing.WorldWebPrefixTests.activate;call=existing.WorldWebPrefixTests.call
    baseline=existing.WorldWebPrefixTests.baseline;open=existing.WorldWebPrefixTests.open
    def setUp(self):
        with patch.object(existing,'WorldTarget',CurrentTarget):existing.WorldWebPrefixTests.setUp(self)
    def test_normal_open_then_current_ray_focus_keeps_same_parent_and_text_step_unfinished(self):
        self.open();opened=self.primary.store.read();call=self.call(1);result=self.primary.focus_current(call)
        self.assertEqual('focused',result['phase']);self.assertEqual('acting',self.primary.state['phase'])
        self.assertEqual(1,len(self.primary.state['completed']));self.assertEqual(call,self.primary.state['active'])
        self.assertEqual('',self.target.current['text']);self.assertTrue(self.target.current['focused']);self.assertEqual(1,self.target.pointer_hits)
        self.assertTrue(self.primary.state['inputs'][-1]['complete']);self.assertEqual([True],self.target.factory_entries)
        self.assertGreater(len(result['focusOriginals']),1);self.assertTrue(self.target.script_bytes)
        self.assertEqual(3,len(self.target.transport.envelopes));self.assertNotEqual(opened,self.primary.store.read())
        before=deepcopy(self.target.current_queries);envelopes=deepcopy(self.target.transport.envelopes)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with cold.lock.held():cold.read();self.assertEqual(self.primary.state,cold.state)
        # Join two real old originals to the wrong owning action. A valid
        # focus result cannot be re-labelled as the ordinary Script-open row.
        wrong=deepcopy(self.primary.state);opened_row=next(row for row in wrong['inputs'] if row['ticket']==wrong['completed'][0]['ticket'])
        last=wrong['inputs'][-1];last['ticket']=opened_row['ticket'];last['anchor']=deepcopy(opened_row['anchor']);last['original']['ticket']=opened_row['ticket']
        with self.assertRaises(NativeUIError):cold.validate(wrong)
        with self.assertRaises(NativeUIError):cold.focus_current(call)
        with self.assertRaises(NativeUIError):cold.act(call)
        with self.assertRaises(PhasePending):self.actor.observe()
        self.assertEqual(before,self.target.current_queries);self.assertEqual(envelopes,self.target.transport.envelopes)

    def test_actual_initial_outer_exit_native_jump_refuses_before_current_source(self):
        self.open();call=self.call(1);held=self.target.lock.held;fired=[]
        @contextmanager
        def release():
            with held():yield
            if not fired and self.primary.state['phase']=='acting':
                self.assertIsNone(self.target.lock._owner);fired.append(True);self.clock.base+=2000
        with patch.object(self.target.lock,'held',release),self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual([True],fired);self.assertEqual([],self.target.current_queries);self.assertEqual([],self.target.factory_entries)
        self.assertEqual(2,len(self.target.transport.envelopes));self.assertEqual('acting',self.primary.state['phase'])

    def test_actual_initial_outer_exit_next_phase_refuses_before_current_source(self):
        self.open();call=self.call(1);held=self.target.lock.held;fired=[]
        @contextmanager
        def release():
            with held():yield
            if not fired and self.primary.state['phase']=='acting':
                self.assertIsNone(self.target.lock._owner);fired.append(True);self.call(2)
        with patch.object(self.target.lock,'held',release),self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual([True],fired);self.assertEqual([],self.target.current_queries);self.assertEqual(2,len(self.target.transport.envelopes))

    def test_landed_parent_acting_cas_host_age_cannot_reset_at_child_intent(self):
        self.open();call=self.call(1);save=self.primary.save;fired=[];epoch=self.clock.epoch()
        def slow(value,**options):
            result=save(value,**options)
            if not fired and value['phase']=='acting':
                self.assertEqual(value,unpack(self.primary.store.read()['payload'])[0]);fired.append(True);self.clock.value+=2
            return result
        with patch.object(self.clock,'epoch',return_value=epoch),patch.object(self.server.journal,'clock',return_value=epoch), \
             patch.object(self.primary.source,'epoch_ms',return_value=epoch),patch.object(self.primary.input_fence().source,'epoch_ms',return_value=epoch), \
             patch.object(self.primary,'save',slow),self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual([True],fired);self.assertEqual([],self.target.current_queries);self.assertEqual(2,len(self.target.transport.envelopes))

    def test_lost_actual_stream_return_retains_parent_and_cold_never_replays(self):
        self.open();call=self.call(1);self.target.lose_current=True
        with self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual(3,len(self.target.transport.envelopes));self.assertFalse(self.target.current['focused'])
        self.clock.sleep(2.01);self.target.consume_current_stream();self.assertTrue(self.target.current['focused'])
        row=self.primary.state['inputs'][-1];self.assertIsNotNone(row['envelope']);self.assertFalse(row['complete'])
        self.assertEqual('calibrated',row['original']['phase']);self.assertIsNotNone(row['original']['deliveryIntent'])
        self.assertIsNone(row['original']['publication']);before=deepcopy(self.target.current_queries)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with cold.lock.held():cold.read();self.assertEqual(self.primary.state,cold.state)
        with self.assertRaises(NativeUIError):cold.focus_current(call)
        self.assertEqual(before,self.target.current_queries);self.assertEqual(3,len(self.target.transport.envelopes))

    def test_byte_equal_new_owner_inode_during_source_is_not_adopted(self):
        self.open();call=self.call(1);replaced=[]
        def hook(source):
            send=source.send
            def replace(command):
                path=self.primary.store.path;raw=path.read_bytes();old=path.lstat();path.rename(path.with_name('held-original-parent.json'))
                with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as output:
                    output.write(raw);output.flush();os.fsync(output.fileno())
                self.assertNotEqual(old.st_ino,path.lstat().st_ino);self.assertEqual(raw,path.read_bytes());replaced.append(True)
                return send(command)
            source.send=replace
        self.target.source_entry_hook=hook
        with self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual([True],replaced);self.assertEqual(2,len(self.target.current_queries));self.assertEqual(2,len(self.target.transport.envelopes))
        self.assertTrue(self.primary.store.path.with_name('held-original-parent.json').is_file())

    def test_focused_durable_result_cannot_publish_after_actual_final_outer_exit(self):
        self.open();call=self.call(1);held=self.target.lock.held;fired=[]
        @contextmanager
        def release():
            with held():yield
            if not fired and self.primary.state['inputs'][-1]['original'].get('phase')=='focused':
                self.assertIsNone(self.target.lock._owner);fired.append(True);self.clock.base+=2000
        with patch.object(self.target.lock,'held',release),self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual([True],fired);self.assertEqual(1,self.target.pointer_hits);self.assertEqual(3,len(self.target.transport.envelopes))
        row=unpack(self.primary.store.read()['payload'])[0]['inputs'][-1]
        self.assertEqual('focused',row['original']['phase']);self.assertTrue(row['complete'])
        self.assertTrue(self.primary.failed);self.assertEqual(1,len(self.primary.state['completed']))

    def test_new_dom_source_instance_cannot_resolve_original_ray_on_same_native_page(self):
        self.open();call=self.call(1);changed=[]
        def hook(source):
            send=source.documents.send
            def new_doc(command):
                if self.target.pending_current is not None and not changed:
                    # Distinct original producer generation, before either
                    # new Doc/geometry raw response exists; no HTTP load or
                    # old Native finish/accepted original is rewritten.
                    changed.append(self.target.current['instance']);self.target.current['instance']=uuid.uuid4().hex
                    self.target.current['sequence']=0
                return send(command)
            source.documents.send=new_doc
        self.target.source_entry_hook=hook
        with self.assertRaises(NativeUIError):self.primary.focus_current(call)
        self.assertEqual(1,len(changed));row=unpack(self.primary.store.read()['payload'])[0]['inputs'][-1]
        carrier=row['original'];self.assertTrue(carrier['focusOriginals'])
        old=json.loads(carrier['calibrationOriginal']['documentOriginal']['raw'])
        new=json.loads(carrier['focusOriginals'][0]['documentOriginal']['raw'])
        self.assertNotEqual(old['source']['dom']['instance'],new['source']['dom']['instance'])
        self.assertEqual(old['source']['originalFinish'],new['source']['originalFinish']);self.assertEqual(1,len(self.target.documents))
        self.assertEqual(3,len(self.target.transport.envelopes));self.assertFalse(row['complete'])


if __name__=='__main__':unittest.main()
