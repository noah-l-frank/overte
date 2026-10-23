"""Original world geometry, existing OpenXR session and uncertain one-shot input.

Android DOM/entity observations and controller transport are explicit boundaries;
these checks grant neither a product hit nor a complete feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.browser_source import command,validate
from adapters.pico4.world_browser_ray import PicoWorldBrowserIO,PicoWorldRayClick,bind_world_click,rotate
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_openxr_adapter_session import FakeTransport

RUN='a'*32;OWNER='b'*32;URL='http://127.0.0.1/feature-fixture/v1/runs/'+RUN+'/'
ENTITY='12345678-1234-1234-1234-123456789abc'
VIEW=dict(handle='1',creation=2,grant=3,page=4,url=URL+'tickets/'+('e'*32)+'/index.html',
          sourceUrl=URL+'tickets/'+('e'*32)+'/index.html',sourceIdentity='web-entity:'+ENTITY)


class WorldBoundary:
    """Only original source responses; never consumes an expected feature state."""
    def __init__(self,lock):
        self.epoch=20000;self.elapsed=1.;self.calls=[];self.packet=None;self.under_input=False;self.events=[]
        self.rotation=[0,0,0,1];self.dimensions=[1.8,2.2,.01];self.quad=None;self.position=[0,1.4,-2.5]
        self.io=PicoWorldBrowserIO(self.send,self.read,self.clock,self.guard,123,source_lock=lock,
                                  monotonic=lambda:self.elapsed,sleep=lambda _:None)
    def clock(self):
        if self.under_input:raise AssertionError('Native clock reentered locked input session')
        return self.epoch
    def guard(self):
        if self.under_input:raise AssertionError('Native guard reentered locked input session')
        return True
    def read(self):return json.dumps(self.packet)
    def send(self,call):
        self.calls.append(deepcopy(call));self.events.append('measure')
        dpi=40;factor=39.3701*dpi;size=[int(v*factor) for v in self.dimensions[:2]]
        scale=min(1,4096/max(v*factor for v in self.dimensions[:2]));size=[int(v*factor*scale) for v in self.dimensions[:2]]
        quad=self.quad or [[0,0],[size[0],0],size,[0,size[1]]]
        geometry=dict(webGeometryVersion=1,requestId=call['commandId'],instance='c'*32,sequence=len(self.calls),
            capturedEpochMs=self.epoch,document=dict(runId=RUN,href=VIEW['url'],responseId='d'*32,readyState='complete'),
            control=call['control'],editor=dict(focused=False,text=None,cursor=None,anchor=None),
            viewport=dict(width=640,height=480,scale=1,offsetLeft=0,offsetTop=0),
            rect=dict(x=80,y=60,width=160,height=80),center=dict(x=160,y=100),hit=True,enabled=True,connected=True)
        uv=[160/640,100/480];point=[quad[0][i]+uv[0]*(quad[1][i]-quad[0][i])+uv[1]*(quad[3][i]-quad[0][i]) for i in range(2)]
        local=[point[0]/factor-self.dimensions[0]/2,self.dimensions[1]/2-point[1]/factor,0]
        offset=rotate(self.rotation,local)
        ray=dict(worldWebRayVersion=1,capturedEpochMs=self.epoch,sourceIdentity=VIEW['sourceIdentity'],entityId=ENTITY,
            entityName='OVERTE_PARITY_WEB_REFERENCE',entityType='Web',hostType='local',sourceUrl=VIEW['sourceUrl'],
            visible=True,ignorePickIntersection=False,position=self.position,rotation=self.rotation,dimensions=self.dimensions,
            registrationPoint=[.5,.5,.5],dpi=dpi,scenePoint=point,itemQuad=quad,surfaceSize=size,
            worldPoint=[self.position[i]+offset[i] for i in range(3)],
            sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],headPosition=[0,1.6,0])
        self.packet=dict(picoBrowserVersion=3,commandId=call['commandId'],runId=RUN,ownerToken=OWNER,instance='f'*32,
            sequence=len(self.calls),processId=123,capturedEpochMs=self.epoch,status='ready',
            source=dict(nativeView={k:VIEW[k] for k in ('handle','creation','grant','page','url')},
                        geometryRaw=json.dumps(json.dumps(geometry)),worldRay=ray))


class WorldBrowserRayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.lock=ScriptSourceLock(self.root/'script-sources.lock');self.b=WorldBoundary(self.lock)
        self.transport=FakeTransport();self.session=PicoOpenXrAdapterSession(self.transport,'host-boundary',self.root)
        self.session.begin('123:456');self.input_events=[];self.ack=None
    def owner(self,*,intent=None,stream_intent=None,publish=None,stage=None):
        b=self.b;original_stage=self.transport.stage
        def transport(envelope,profile,*,before_publish):
            b.under_input=True
            try:
                before_publish(deepcopy(envelope));return original_stage(envelope,profile,before_publish=before_publish)
            finally:b.under_input=False
        self.transport.stage=transport
        def durable(value):
            self.input_events.append('intent');PrivateFeatureState(self.root/'world-click-intent.json').write(value,None)
            if intent:intent(value)
        def stream(value):
            self.input_events.append('stream');PrivateFeatureState(self.root/'world-click-stream.json').write(value,None)
            if stream_intent:stream_intent(value)
        def final(value):
            self.input_events.append('publish');self.assertTrue(b.under_input)
            self.assertEqual(value,PrivateFeatureState(self.root/'world-click-stream.json').read())
            if publish:publish(value)
        if stage is None:
            stage=lambda pose,**hooks:self.session.stage('123:456','input.primary',pose,**hooks)
        return PicoWorldRayClick(b.io,stage,durable,stream,final)
    def measure(self):
        with self.lock.held():return self.b.io.measure_ray(RUN,URL,OWNER,VIEW,'bridge')
    def test_passive_world_measure_uses_actual_quad_dpi_cap_and_rotated_entity_without_input(self):
        for dimensions,angle,quad in (([1.8,2.2,.01],0,None),([8,9,.01],.7,[[10,20],[3010,20],[3010,2020],[10,2020]])):
            self.b.dimensions=dimensions;self.b.rotation=[0,math.sin(angle/2),0,math.cos(angle/2)];self.b.quad=quad
            self.measure();self.assertEqual([],self.transport.envelopes)
        self.assertEqual(2,len(self.b.calls));self.assertEqual(['measure','measure'],self.b.events)
    def test_foreign_or_malformed_actual_geometry_is_refused_before_any_gesture(self):
        packet=self.measure();call=self.b.calls[-1]
        changes=[('worldWebRayVersion',True),('entityId','0'*36),('sourceIdentity','tablet:foreign'),
            ('entityName','foreign'),('hostType','domain'),('visible',False),('ignorePickIntersection',True),
            ('sourceUrl',URL+'index.html'),('registrationPoint',[0,0,0]),('rotation',[0,0,0,2]),
            ('sensorToWorld',[0]*16),('capturedEpochMs',18499),('worldPoint',[0,0,0]),
            ('scenePoint',[1,1]),('itemQuad',[[0,0],[20,0],[50,50],[0,20]]),('dpi',True)]
        for field,value in changes:
            bad=deepcopy(packet);bad['source']['worldRay'][field]=value
            with self.subTest(field=field),self.assertRaises((ValueError,RuntimeError)):validate(bad,call,123,20000)
        self.assertEqual([],self.transport.envelopes)
    def test_normal_existing_session_preserves_exact_original_intents_and_ack_is_no_dom_effect(self):
        click=self.owner()
        with self.lock.held():ack=click.click(RUN,URL,OWNER,VIEW,'bridge')
        self.assertTrue(ack['performed']);self.assertNotIn('state',ack);self.assertNotIn('featureSucceeded',ack)
        self.assertEqual(['intent','stream','publish','publish'],self.input_events)
        self.assertEqual(1,len(self.transport.envelopes));self.assertEqual(1,len(self.b.calls))
        # This transport deliberately ignores the page. Its ACK cannot invent
        # a bridge echo or overwrite an independent DOM observation.
        with self.lock.held(),self.assertRaises(NativeUIError):click.click(RUN,URL,OWNER,VIEW,'bridge')
        self.assertEqual(1,len(self.transport.envelopes))
    def test_slow_original_intent_with_frozen_native_clock_cannot_retime_geometry(self):
        click=self.owner(intent=lambda _:setattr(self.b,'elapsed',2.6))
        with self.lock.held(),self.assertRaises(NativeUIError):click.click(RUN,URL,OWNER,VIEW,'bridge')
        self.assertTrue(click.issued and click.failed);self.assertEqual([],self.transport.envelopes)
        self.assertEqual(['intent'],self.input_events)
    def test_slow_locked_stream_or_final_cas_refuses_before_actual_writer_without_native_reentry(self):
        for phase in ('stream','publish'):
            with self.subTest(phase=phase):
                self.setUp()
                delay=lambda _:setattr(self.b,'elapsed',2.6)
                click=self.owner(stream_intent=delay if phase=='stream' else None,publish=delay if phase=='publish' else None)
                with self.lock.held(),self.assertRaises(NativeUIError):click.click(RUN,URL,OWNER,VIEW,'bridge')
                self.assertEqual([],self.transport.envelopes);self.assertTrue(click.failed)
    def test_lost_delivered_input_and_late_original_reply_never_retry_the_one_gesture(self):
        for failure in ('lost','late'):
            with self.subTest(failure=failure):
                self.setUp();base=self.session.stage
                def stage(pose,**hooks):
                    result=base('123:456','input.primary',pose,**hooks)
                    if failure=='lost':raise OSError('Lost original reply after actual publication')
                    self.b.epoch+=1501;return result
                click=self.owner(stage=stage)
                with self.lock.held(),self.assertRaises(NativeUIError):click.click(RUN,URL,OWNER,VIEW,'bridge')
                with self.lock.held(),self.assertRaises(NativeUIError):click.click(RUN,URL,OWNER,VIEW,'bridge')
                self.assertEqual(1,len(self.transport.envelopes));self.assertTrue(click.failed)
    def test_foreign_envelope_cannot_authorize_final_publication(self):
        def stage(pose,*,intent,before_publish):
            envelope=dict(schemaVersion=1,sessionNonce='1'*64,sequence=1,
                          commands=[dict(id='input-primary-1',operation='input.primary',arguments=pose)])
            intent(envelope);envelope['commands'][0]['arguments']['positionMeters'][0]+=1;before_publish(envelope)
        click=self.owner(stage=stage)
        with self.lock.held(),self.assertRaises(NativeUIError):click.click(RUN,URL,OWNER,VIEW,'bridge')
        self.assertEqual(['intent','stream'],self.input_events);self.assertEqual([],self.transport.envelopes)
    def test_world_only_closed_command_and_source_identity_reject_tablet_or_host_coordinates(self):
        self.measure();call=self.b.calls[-1]
        for change in ({'action':'pico-tablet-web'},{'x':1},{'expected':'clicked'},{'text':'injected'}):
            with self.subTest(change=change),self.assertRaises(NativeUIError):command(call|change)
        foreign=VIEW|{'sourceIdentity':'web-entity:00000000-0000-0000-0000-000000000001'}
        with self.lock.held(),self.assertRaises(NativeUIError):self.b.io.measure_ray(RUN,URL,OWNER,foreign,'bridge')
        self.assertEqual([],self.transport.envelopes)


if __name__=='__main__':unittest.main()
