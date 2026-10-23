"""Original logical page transitions share physical weak life, not JS readiness."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_state as state
from ios.self_tests.test_ios_tablet_web_state import packet as legacy,query,trace,sources
from ios.self_tests.tablet_web_dom_fixture import shown
from ios.self_tests.test_ios_tablet_web_sources import stamp

ROOT=Path(__file__).resolve().parents[4]


def loaded(index=1):
    value,_=legacy(index,attached=True);value.update(iosTabletWebStateVersion=2,presentations=[])
    row=value['owners'][0];row['current'].update(generation=1,active=True,viewPresent=True,presentationPresent=True,
        presentationAttached=True,windowPresent=True,sourceCurrent=True,loading=True)
    value['presentations']=[dict(owner=row['id'],handle=row['handle'],source=deepcopy(row['source']),generation=1,snapshot=shown(),target=value['targets'][0]['source']['view'])]
    return value


def navigate(before):
    value=loaded(2);old=value['owners'][0];old['current']['sourceCurrent']=False
    new=deepcopy(old);new.update(id='7'*32,firstObserved=stamp(90622))
    new['source']['navigation']='6'*32;new['current']['sourceCurrent']=True
    value['owners'].append(new);value['presentations'][0].update(owner=new['id'],source=deepcopy(new['source']))
    target=deepcopy(value['targets'][0]);target['source']['view']='4'*32;target['source']['bound']=stamp(90622)
    target['source']['identity']['source']=deepcopy(new['source']);value['targets'].append(target)
    value['presentations'][0]['target']=target['source']['view']
    return value


class TabletWebStateNavigationTests(unittest.TestCase):
    def test_same_QObject_new_actual_stamp_keeps_old_original_and_real_physical_life(self):
        before=loaded();current=navigate(before);state.validate(current,query(2),31,previous=before)
        self.assertEqual(before['owners'][0]['source'],current['owners'][0]['source'])
        self.assertEqual(before['owners'][0]['firstObserved'],current['owners'][0]['firstObserved'])
        self.assertEqual(current['owners'][0]['handle'],current['owners'][1]['handle'])
        self.assertTrue(current['owners'][0]['alive']);self.assertIsNone(current['owners'][0]['expired'])
        self.assertTrue(current['owners'][0]['current']['active'])
        self.assertFalse(current['owners'][0]['current']['sourceCurrent'])
        self.assertEqual(state.current_presentation(current,current['owners'][1]['source'])['owner'],current['owners'][1]['id'])
        with self.assertRaises(NativeUIError):state.current_presentation(current,before['owners'][0]['source'])
        for fault in ('retime','rewrite','fake-zero','double-current','duplicate-source','drop-old'):
            changed=deepcopy(current)
            if fault=='retime':changed['owners'][0]['firstObserved']=stamp(90622)
            elif fault=='rewrite':changed['owners'][0]['source']['root']='5'*32
            elif fault=='fake-zero':changed['owners'][0]['current']['viewPresent']=False
            elif fault=='double-current':changed['owners'][0]['current']['sourceCurrent']=True
            elif fault=='duplicate-source':changed['owners'][1]['source']=deepcopy(changed['owners'][0]['source'])
            else:changed['owners'].pop(0)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):state.validate(changed,query(2),31,previous=before)

    def test_native_presentation_is_independent_of_ready_JS_and_cannot_borrow_old_stamp(self):
        value=loaded();selected=state.current_presentation(value,value['owners'][0]['source'])
        self.assertTrue(value['owners'][0]['current']['loading']);self.assertNotIn('dom',value)
        self.assertEqual(selected['snapshot']['top'],selected['snapshot']['presentation'])
        self.assertNotEqual(selected['target'],selected['snapshot']['view'])  # Independent actual producer IDs.
        for fault in ('source','owner','generation','detached','sheet','foreign','target','bool-version','future'):
            changed=deepcopy(value)
            if fault=='source':changed['presentations'][0]['source']['navigation']='5'*32
            elif fault=='owner':changed['presentations'][0]['owner']='5'*32
            elif fault=='generation':changed['presentations'][0]['generation']=2
            elif fault=='detached':changed['owners'][0]['current']['presentationAttached']=False
            elif fault=='sheet':changed['presentations'][0]['snapshot']['top']='5'*32
            elif fault=='foreign':changed['otherLiveTablets']=1
            elif fault=='target':changed['presentations'][0]['target']='5'*32
            elif fault=='bool-version':changed['iosTabletWebStateVersion']=True
            else:changed['iosTabletWebStateVersion']=3
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):state.current_presentation(changed,value['owners'][0]['source'])
        value['presentations']=[];state.original(value)
        with self.assertRaises(NativeUIError):state.current_presentation(value,value['owners'][0]['source'])

    def test_literal_v1_grammar_stays_readable_but_never_mints_presentation_authority(self):
        before,_=legacy();self.assertEqual(state.original(before),before)
        with self.assertRaises(NativeUIError):state.current_presentation(before,before['owners'][0]['source'])
        changed=deepcopy(before);changed['presentations']=[]
        with self.assertRaises(NativeUIError):state.original(changed)
        current=navigate(loaded());state.validate(current,query(2),31,previous=before)
        later,_=legacy(3)
        with self.assertRaises(NativeUIError):state.validate(later,query(3),31,previous=current)

    def test_live_document_joins_distinct_presentation_and_touch_object_ids_through_actual_target(self):
        from ios.adapters import tablet_web_history as history
        value=loaded();value['owners'][0]['current']['loading']=False
        _,touches=legacy();ledger=trace();document=dict(source=dict(nativeView=deepcopy(ledger['events'][0]['identity']),presentationAfter=shown()))
        frame=dict(state=value,sources=sources(),ledger=ledger,touches=touches)
        history._live(frame,document)
        for fault in ('foreign-presentation-birth','foreign-target'):
            changed=deepcopy(frame)
            if fault=='foreign-presentation-birth':changed['state']['presentations'][0]['snapshot']['view']='5'*32
            else:changed['state']['presentations'][0]['target']='5'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):history._live(changed,document)

    def test_actual_HTTP_and_AFC_v2_route_preserves_loading_source_target_and_presentation_original(self):
        import base64
        import json
        from types import SimpleNamespace
        from unittest.mock import patch
        from ios.adapters import feature_observation
        from ios.self_tests.test_ios_feature_observation import Native
        native=Native();observer=native.observer();commands=[];reads=[]
        def post(request,timeout):
            command=native.fixture.set_client_command(json.loads(request.data));commands.append(command);native.echo=json.dumps(command).encode()
            native.value=loaded(len(commands));native.value.update(commandId=command['commandId'],processId=native.pid);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+state.FILE},arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=90621))
        with patch.object(feature_observation,'post_request',side_effect=post):value=observer.tablet_web_state(clock).read(query()['runId'],query()['fixtureUrl'])
        self.assertEqual(1,len(commands));self.assertEqual(1,len(reads));self.assertEqual(native.value,value)
        shown=state.current_presentation(value,value['owners'][0]['source'])
        self.assertTrue(value['owners'][0]['current']['loading']);self.assertNotEqual(shown['target'],shown['snapshot']['view'])

    def test_actual_native_source_uses_exact_stamp_and_read_only_UIKit_snapshot_before_JS_gate(self):
        root=ROOT
        header=(root/'ios/web/IOSTabletWebState.h').read_text()
        source=(root/'ios/web/IOSWebView.mm').read_text()
        body=source.split('QVariantMap IOSWebView::featureTabletWebStateObservation(',1)[1].split('QVariantMap IOSWebView::featureTabletWebDOMObservation(',1)[0]
        self.assertIn('QJsonObject::fromVariantMap(row->source)==QJsonObject::fromVariantMap(source)',header)
        self.assertIn('QJsonObject::fromVariantMap(currentSources.value(owner->handle).toMap())==QJsonObject::fromVariantMap(owner->source)',body)
        self.assertIn('tablet_web_presentation::observe(data.view,data.window,data.presentation,data.presenter)',body)
        self.assertIn('current.isEmpty()?QVariant():QVariant(current)',body)
        for ready_gate in ('featureFinishedPage','featureVerifiedPage','evaluateJavaScript','tablet_web_dom::begin'):
            self.assertNotIn(ready_gate,body)
        for mutation in ('tearDown(', 'removeFromSuperview]', 'stopLoading]', 'dismissViewController'):
            self.assertNotIn(mutation,body)
        # A retired logical stamp keeps actual physical fields; no synthetic
        # zero-generation/zero-view map is constructed for the older row.
        self.assertIn('auto current=owner->object?currents.value(owner->handle).toMap()',body)
        self.assertIn('"source",owner->source',body)


if __name__=='__main__':unittest.main()
