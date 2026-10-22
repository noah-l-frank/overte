"""Actual observer output with independent native document and HTTP originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.browser_fixture import BrowserResources
from ios.adapters import tablet_web_documents as measurements,tablet_web_dom as dom,tablet_web_source as native
from ios.self_tests.tablet_web_dom_fixture import packet as envelope
from ios.self_tests.test_ios_tablet_web_source import packet as native_packet
from ios.self_tests.test_ios_tablet_web_sources import packet as sources_packet,stamp,RUN,ROOT,TICKET

REPO=Path(__file__).resolve().parents[4]
ORIGINS={'primary':'http://127.0.0.1:18000','foreign':'http://127.0.0.1:18001'}


def originals(body,inline=False,status=200,resource='reference.html'):
    document=envelope(body,inline=inline);ledger=native_packet(inline=inline);source=sources_packet()
    identity=deepcopy(document['source']['nativeView']);ledger['events']=[];ledger['eventSequence']=0
    ledger['clockBefore']=ledger['clockAfter']=stamp(body['capturedEpochMs'])
    def event(kind,detail=None,epoch=None):
        index=len(ledger['events'])+1;ledger['events'].append(dict(sequence=index,eventId=format(index,'032x'),kind=kind,
            clock=stamp(epoch or 99000+index),identity=deepcopy(identity),detail=deepcopy(detail or {})));ledger['eventSequence']=index
    event('view-created');event('document-began',{'frame':identity['url']})
    # WK URL need not be committed when this real document begins.
    ledger['events'][0]['identity']['url']='';ledger['events'][1]['identity']['url']=''
    event('dom-observer-installed',{'sourceSha256':dom.SOURCE_SHA256,'wrapperSha256':'a'*64})
    if not inline:event('main-response',{'url':identity['url'],'status':status,'responseId':body['document']['responseId'],'mimeType':'text/html'})
    event('native-finished');event('document-verified')
    document['source']['nativeFinishedEpochMs']=ledger['events'][-2]['clock']['epochMs']
    browser={'browserFixtureVersion':1,'instance':'d'*32,'ready':status==200,'sequence':0,'responses':[]}
    if not inline:
        document['source']['http']['status']=status
        browser['sequence']=1;browser['responses']=[dict(sequence=1,responseId=body['document']['responseId'],capturedEpochMs=98000,
            ticket=TICKET,resource=resource,origin='primary',status=status,bytes=2345,sha256='c'*64)]
    return ledger,source,document,browser


class TabletWebDocumentsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        program='''const page=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page;
const root=process.argv[1];const result=[];
for(const inline of [false,true]){const p=page({inline,inlineToken:'6'.repeat(32)});
if(!inline)p.global.location.href=root+'tickets/'+'b'.repeat(32)+'/reference.html';
result.push(p.read('ios-'+(1).toString(16).padStart(32,'0')));}
process.stdout.write(JSON.stringify(result));'''
        run=subprocess.run(['node','-e',program,ROOT],cwd=REPO,capture_output=True,text=True,timeout=5)
        if run.returncode:raise AssertionError(run.stderr)
        cls.bodies=json.loads(run.stdout)
    def test_original_http_and_inline_complete_with_distinct_receipts_and_unchanged_inputs(self):
        for inline,body in enumerate(self.bodies):
            args=originals(body,bool(inline));before=deepcopy(args)
            result=measurements.current_document(*args,ORIGINS)
            self.assertEqual(1,result['documentLoads']);self.assertEqual('inline' if inline else 'http',result['documentKind'])
            self.assertEqual(bool(inline),result['response'] is None);self.assertEqual(before,args)
            if inline:self.assertEqual(args[1]['navigations'][1]['body'],result['inlineInput'])
    def test_first_finish_and_one_verified_document_survive_later_duplicate_callbacks(self):
        args=list(originals(self.bodies[0]));ledger=args[0];first=deepcopy(ledger['events'][-2]);verified=deepcopy(ledger['events'][-1])
        for event in (first,verified):
            index=len(ledger['events'])+1;event.update(sequence=index,eventId=format(index,'032x'),clock=stamp(99900+index));ledger['events'].append(event)
        ledger['eventSequence']=len(ledger['events'])
        result=measurements.current_document(*args,ORIGINS);self.assertEqual(1,result['documentLoads'])
        self.assertEqual(first['sequence']-2,result['document']['finished']['sequence'])
    def test_missing_real_observer_response_finish_verification_or_wrong_hash_cannot_complete(self):
        for fault in ('observer','response','finish','verified','observerHash'):
            args=list(originals(self.bodies[0]));ledger=args[0]
            if fault=='observerHash':ledger['events'][2]['detail']['sourceSha256']='0'*64
            else:
                names={'observer':'dom-observer-installed','response':'main-response','finish':'native-finished','verified':'document-verified'}
                ledger['events']=[row for row in ledger['events'] if row['kind']!=names[fault]]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):measurements.current_document(*args,ORIGINS)
    def test_actual_server_id_status_resource_origin_document_and_inline_binding_are_independent(self):
        for fault in ('response','status','resource','origin','finished','identity','rootRetired','inlineRetired','inlineHTTP'):
            inline=fault.startswith('inline');args=list(originals(self.bodies[int(inline)],inline));ledger,source,document,browser=args
            if fault=='response':browser['responses'][0]['responseId']='0'*32
            elif fault=='status':browser['responses'][0]['status']=404
            elif fault=='resource':browser['responses'][0]['resource']='page-b.html'
            elif fault=='origin':browser['responses'][0]['origin']='foreign'
            elif fault=='finished':document['source']['nativeFinishedEpochMs']=98999
            elif fault=='identity':document['source']['nativeView']['page']=2
            elif fault=='rootRetired':
                source['roots'][0].update(alive=False,destroyed=stamp(99900));source['clockBefore']=source['clockAfter']=stamp(100001)
            elif fault=='inlineRetired':
                carrier=source['carriers'][0];carrier['retired']=stamp(90400);carrier['bindings'][0].update(current=False,revoked=stamp(90400))
            else:
                row=deepcopy(ledger['events'][2]);row.update(sequence=4,eventId='9'*32,kind='main-response',clock=stamp(99003))
                row['detail']={'url':document['source']['nativeView']['url'],'status':200,'responseId':'b'*32,'mimeType':'text/html'}
                ledger['events'].insert(3,row)
                for index,event in enumerate(ledger['events'],1):event.update(sequence=index,eventId=format(index,'032x'))
                ledger['eventSequence']=len(ledger['events'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):measurements.current_document(*args,ORIGINS)
    def test_old_ready_dom_cannot_become_current_after_actual_close_recreation_or_navigation(self):
        for kind in ('view-teardown','owner-destroyed','view-created','document-began'):
            args=list(originals(self.bodies[0]));ledger=args[0];row=deepcopy(ledger['events'][-1]);index=len(ledger['events'])+1
            row.update(sequence=index,eventId=format(index,'032x'),kind=kind,clock=stamp(99900),detail={})
            if kind=='view-created':row['identity']['creation']+=1
            if kind=='document-began':
                row['identity'].update(page=2,nonce='22222222-2222-3333-4444-555555555555');row['detail']={'frame':row['identity']['url']}
            ledger['events'].append(row);ledger['eventSequence']=index
            native.original(ledger)
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):measurements.current_document(*args,ORIGINS)
    def test_actual_browser_404_recovery_and_foreign_response_bytes_feed_original_observer_metadata(self):
        resources=BrowserResources(clock_ms=lambda:98000);resources.open(RUN)
        program='''const p=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page();
const input=JSON.parse(process.argv[1]),original=p.doc.querySelectorAll;
const response=input.body.match(/<meta name="overte-fixture-response" content="([0-9a-f]{32})">/)[1];
p.doc.querySelectorAll=function(selector){return selector==='meta[name="overte-fixture-response"]'?[{content:response}]:original.call(this,selector);};
p.global.location.href=input.url;process.stdout.write(JSON.stringify(p.read('ios-'+(1).toString(16).padStart(32,'0'))));'''
        for resource,selected,status in (('recovery.html','primary',404),('recovery.html','primary',200),('reference.html','foreign',200)):
            if resource=='recovery.html' and status==200:resources.control(RUN,{'operation':'restore-resource'})
            actual,_,raw,_=resources.resource(RUN,TICKET,resource,origin=selected);self.assertEqual(status,actual)
            url=ORIGINS[selected]+'/feature-fixture/v1/runs/'+RUN+'/tickets/'+TICKET+'/'+resource
            run=subprocess.run(['node','-e',program,json.dumps({'body':raw.decode(),'url':url})],cwd=REPO,capture_output=True,text=True,timeout=5)
            if run.returncode:raise AssertionError(run.stderr)
            args=list(originals(json.loads(run.stdout),status=status,resource=resource));args[-1]=resources.snapshot(RUN)
            result=measurements.current_document(*args,ORIGINS)
            self.assertEqual(status,result['response']['status']);self.assertEqual(selected,result['origin'])
            self.assertEqual('foreign' if selected=='foreign' else 'recovery',result['page'])


if __name__=='__main__':unittest.main()
