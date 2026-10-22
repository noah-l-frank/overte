"""Normal wheel recipe with original measured bounds; explicit DOM/native seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
from adapters.pico4.browser_source import command,geometry_original
RUN='a'*32;OWNER='b'*32;URL='http://127.0.0.1/feature-fixture/v1/runs/'+RUN+'/'
VIEW=dict(handle='12',creation=1,grant=2,page=3,url=URL+'tickets/'+'c'*32+'/index.html')
class Reader(PicoTabletBrowserIO):
    def __init__(self):
        self.y=700;self.sequence=0;self.clock=1.;self.epoch=20000;self.calls=[];self.intents=[];self.read_only=False
        self.move=True;self.lost=False;self.hit=True;self.connected=True;self.monotonic=lambda:self.clock
        self.sleep=lambda seconds:setattr(self,'clock',self.clock+seconds)
    def request(self,run,url,owner,operation,**fields):
        self.sequence+=1;self.epoch+=1;self.clock+=.001
        call=command(dict(schemaVersion=1,commandId=format(self.sequence,'032x'),action=self.action,runId=run,fixtureUrl=url,ownerToken=owner,operation=operation,**fields))
        self.calls.append(deepcopy(call))
        if operation=='input':
            if self.lost:raise NativeUIError('lost original input return')
            if fields['control']=='scroll-down' and self.move:self.y-=400
            elif fields['control']=='scroll-up' and self.move:self.y+=400
            return dict(status='ready',source=dict(delivered=True)) # Explicit delivery seam; never the measured effect.
        geometry=dict(webGeometryVersion=1,requestId=call['commandId'],instance='d'*32,sequence=self.sequence,capturedEpochMs=self.epoch,
            document=dict(runId=RUN,href=VIEW['url'],responseId='e'*32,readyState='complete'),control=fields['control'],
            editor=dict(focused=False,text=None,cursor=None,anchor=None),viewport=dict(width=640,height=480,scale=1,offsetLeft=0,offsetTop=0),
            rect=dict(x=80,y=self.y-40,width=160,height=80),center=dict(x=160,y=self.y),hit=self.hit and 0<=self.y<480,enabled=True,connected=self.connected)
        return dict(commandId=call['commandId'],capturedEpochMs=self.epoch,source=dict(nativeView=deepcopy(VIEW),geometryRaw=json.dumps(json.dumps(geometry))))
    def intent(self,row):self.intents.append(deepcopy(row))
    def reveal_control(self):return self.reveal(RUN,URL,OWNER,VIEW,'bridge',intent=self.intent)
class PicoBrowserRevealTests(unittest.TestCase):
    def test_original_full_dom_view_matches_exact_measurement_identity_and_foreign_document_refuses(self):
        source=Reader();view=dict(VIEW,nativeFinished=True,httpErrorStatus=0,inlineLease=False,sourceUrl=VIEW['url'],sourceIdentity='tablet:original')
        packet=source.measure(RUN,URL,OWNER,view,'bridge');self.assertEqual(VIEW,packet['source']['nativeView'])
        with self.assertRaises(NativeUIError):source.measure(RUN,URL,OWNER,view|{'url':VIEW['url']+'?foreign'},'bridge')
        self.assertEqual([],source.intents);self.assertFalse(any(row['operation']=='input' for row in source.calls))
    def test_normal_wheel_then_independent_actual_bounds_before_single_pointer(self):
        source=Reader();source.input_visible(RUN,URL,OWNER,VIEW,'bridge',intent=source.intent)
        self.assertEqual(['scroll-down','bridge'],[row['control'] for row in source.calls if row['operation']=='input'])
        self.assertEqual(['wheel','input'],[row['operation'] for row in source.intents]);self.assertEqual(300,source.y)
        self.assertEqual(300,source.geometry(source.intents[-1]['reference'],RUN,'bridge')['center']['y'])
    def test_upward_original_bounds_select_normal_positive_wheel(self):
        source=Reader();source.y=-100;source.reveal_control()
        self.assertEqual(['scroll-up'],[row['control'] for row in source.calls if row['operation']=='input'])
    def test_wheel_ack_without_actual_movement_fails_without_resending(self):
        source=Reader();source.move=False
        with self.assertRaises(NativeUIError):source.reveal_control()
        self.assertEqual(1,len([r for r in source.calls if r['operation']=='input']))
        self.assertEqual(700,source.y)
    def test_lost_input_return_is_never_resent(self):
        source=Reader();source.lost=True
        with self.assertRaises(NativeUIError):source.reveal_control()
        self.assertEqual(1,len([r for r in source.calls if r['operation']=='input']))
    def test_occluded_disconnected_or_read_only_source_never_gets_an_input(self):
        for mode in ('occluded','disconnected','read_only'):
            with self.subTest(mode=mode):
                source=Reader()
                if mode=='occluded':source.y=300;source.hit=False
                if mode=='disconnected':source.connected=False
                if mode=='read_only':source.read_only=True
                with self.assertRaises(NativeUIError):source.reveal_control()
                self.assertEqual([],source.intents);self.assertFalse(any(r['operation']=='input' for r in source.calls))
    def test_offscreen_measure_is_valid_original_but_cannot_be_used_for_pointer(self):
        source=Reader();packet=source.measure(RUN,URL,OWNER,VIEW,'bridge');request=source.calls[-1]
        actual=source.geometry(packet,RUN,'bridge');self.assertEqual(700,actual['center']['y'])
        with self.assertRaises(NativeUIError):geometry_original(packet['source']['geometryRaw'],request,VIEW['url'],packet['capturedEpochMs'])
if __name__=='__main__':unittest.main()
