"""Strict native UIKit surface/document/source joins using actual JS originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_dom as dom,tablet_web_presentation as presentation
from ios.self_tests.tablet_web_dom_fixture import original_bodies,packet,query,shown,sources,RUN,ROOT


class TabletNativeDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bodies=original_bodies()

    def test_actual_script_originals_join_genuine_http_and_inline_carrier_descriptors(self):
        for inline,rows in enumerate(self.bodies):
            value=packet(rows[0],inline=bool(inline));dom.original(value);self.assertEqual(value,dom.join_sources(value,sources()))
            next_=packet(rows[1],inline=bool(inline),index=2);dom.validate(next_,query(2),31,previous=value)
            self.assertEqual(value['source']['presentationAfter']['view'],next_['source']['presentationAfter']['view'])
            self.assertEqual(value['source']['dom'],rows[0]);self.assertNotIn('iosWorldWebDOMNativeVersion',value)

    def test_other_sheet_wrong_window_recycled_native_view_and_mid_read_geometry_change_fail(self):
        before=packet(self.bodies[0][0]);current=packet(self.bodies[0][1],index=2)
        for fault in ('otherSheet','wrongWindow','recycled','changedFrame','inactive','pendingPresentation','source','nonce','observer','http','bodyClock','bool'):
            value=deepcopy(current);source=value['source'];after=source['presentationAfter']
            if fault=='otherSheet':after['top']='a'*32
            elif fault=='wrongWindow':after['viewWindowMatches']=False
            elif fault=='recycled':
                for key in ('presentationBefore','presentationAfter'):source[key]['view']='a'*32
            elif fault=='changedFrame':after['screenFrame'][0]=10
            elif fault=='inactive':after['applicationState']=2
            elif fault=='pendingPresentation':after['beingPresented']=True
            elif fault=='source':source['nativeView']['source']['fixtureUrl']=ROOT.replace(RUN,'9'*32)
            elif fault=='nonce':source['nativeView']['nonce']='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
            elif fault=='observer':source['observerSha256']='0'*64
            elif fault=='http':source['http']['responseId']='0'*32
            elif fault=='bodyClock':value['clockBefore']['epochMs']+=1
            else:after['keyWindow']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):dom.validate(value,query(2),31,previous=before)

    def test_inline_can_not_use_foreign_transport_or_http_metadata_as_its_original_doc(self):
        before=packet(self.bodies[1][0],inline=True)
        for fault in ('transport','http','lease','carrier','returned'):
            value=deepcopy(before);originals=sources()
            if fault=='transport':value['source']['nativeView']['sourceUrl']='http://'+'9'*32+'.overte-inline.invalid/index.html'
            elif fault=='http':value['source']['http']=dict(status=200,responseId='a'*32,url=value['source']['nativeView']['url'])
            elif fault=='lease':value['source']['inlineLease']=False
            elif fault=='carrier':value['source']['nativeView']['source']['carrier']='9'*32
            else:originals['carriers'][0]['bindings'][0].pop('returned')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):dom.join_sources(value,originals)

    def test_native_projection_uses_actual_visual_viewport_and_screen_frame_not_qt_size(self):
        value=packet(self.bodies[0][0]);view=value['source']['presentationAfter'];body=value['source']['dom']
        element=next(row for row in body['elements'] if row['id']=='text')
        self.assertEqual([120.,84.],presentation.point(view,body['document'],element))
        self.assertEqual(view,presentation.inactive_gestures(view))
        active=deepcopy(view);active['recognizers'][0]['state']=1
        with self.assertRaises(NativeUIError):presentation.inactive_gestures(active)
        self.assertNotIn('touches',view)  # recognizers are not a UITouch death receipt

    def test_valid_pending_original_is_a_floor_for_same_nonce_native_birth_and_counter(self):
        ready=packet(self.bodies[0][0]);pending=deepcopy(ready);pending.update(status='pending',source={})
        for fault in ('birth','counter','before','terminalRetime'):
            reader=dom.IOSTabletWebDOM(lambda _:None,lambda:'',lambda:ready['clockAfter']['epochMs'],lambda:True,31,monotonic=lambda:0)
            previous=deepcopy(pending);changed=deepcopy(ready)
            if fault=='counter':previous['sequence']=5
            if fault=='terminalRetime':previous=deepcopy(ready)
            reader._validate(previous,query(),31)
            if fault=='birth':changed['instance']='9'*32
            elif fault=='before':
                changed['clockBefore']['epochMs']-=1;changed['clockBefore']['monotonicMs']-=1
            elif fault=='terminalRetime':
                changed['clockAfter']['epochMs']+=1;changed['clockAfter']['monotonicMs']+=1
            dom.original(changed)  # individually valid, original stream invalid
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader._validate(changed,query(),31)

    def test_original_query_transport_once_and_lost_return_retains_uncertainty(self):
        value=packet(self.bodies[0][0]);epoch=value['clockAfter']['epochMs'];calls=[];raw={}
        def send(request):calls.append(deepcopy(request));current=deepcopy(value);current['commandId']=request['commandId'];current['source']['dom']['requestId']=request['commandId'];raw['value']=json.dumps(current)
        reader=dom.IOSTabletWebDOM(send,lambda:raw['value'],lambda:epoch,lambda:True,31,monotonic=lambda:0)
        actual=reader.read(RUN,ROOT);self.assertEqual(dom.ACTION,calls[0]['action']);self.assertEqual(self.bodies[0][0]['document'],actual['source']['dom']['document'])
        def lost(request):calls.append(deepcopy(request));raise OSError('Lost actual native source-query return')
        reader.send=lost
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
        self.assertEqual(2,len(calls))


if __name__=='__main__':unittest.main()
