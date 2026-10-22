"""Actual loopback HTTP/product JS, with native XHR/Qt/SDK boundaries modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY,QUERY
from feature_journeys.fixtures import context
from ios.adapters import feature_observation,places_http as http
from ios.self_tests.test_ios_location_bookmarks import Boundary as Clocks,RUN
from ios.self_tests.test_ios_places_model import page
from ios.self_tests.test_ios_feature_observation import Native
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source
from self_tests import test_navigation_resources as resources_tests

ROOT=Path(__file__).resolve().parents[4]
ORIGIN='http://controlled.invalid:49121'
TICKET='b'*32
INPUTS=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision='c'*40,sceneUrl=ORIGIN+'/scene.json')


class Boundary(Clocks):
    def __init__(self):
        super().__init__(None);self.events=[];self.run=RUN;self.xhr=uuid.uuid4().hex;self.reply=uuid.uuid4().hex
    def event(self,kind,details=None):
        self.clock+=.001
        value=dict(sequence=len(self.events)+1,eventId=uuid.uuid4().hex,xhrId=self.xhr,kind=kind,clock=self.clocks(),details=deepcopy(details or {}))
        self.events.append(value);return value
    def begin(self,origin=ORIGIN):
        self.event('created',dict(scriptSource='qrc:/scripts/system/places/places.js',
            engine=dict(instance='d'*32,assigned=True,url='qrc:/scripts/+android_phoneInterface/defaultScripts.js',
                loadGeneration=1,assignedEpochMs=self.epoch()-100),
            submitted=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=500,sha256='e'*64,submittedEpochMs=self.epoch()-99),
            requestUrl=origin+DIRECTORY+'?'+QUERY,protocolSignature=INPUTS['protocolSignature']))
        self.event('callback-enter',dict(callback='readystatechange',readyState=1))
        self.event('callback-leave',dict(callback='readystatechange',readyState=1))
        self.event('sent',dict(replyId=self.reply,url=origin+DIRECTORY+'?'+QUERY))
        self.event('timer-state',dict(active=True))
    def response(self,raw,response_id,*,read=True):
        body=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())
        self.event('reply-finished',dict(replyId=self.reply,httpStatus=200,networkError=0,responseId=response_id,body=body))
        self.event('callback-enter',dict(callback='readystatechange',readyState=4))
        if read:self.event('text-read',dict(replyId=self.reply,scriptSource='qrc:/scripts/system/places/places.js',sha256=body['sha256']))
        self.event('callback-leave',dict(callback='readystatechange',readyState=4))
    def retire(self):
        self.event('reply-destroyed',dict(replyId=self.reply));self.event('callbacks-released')
        self.event('timer-destroyed');self.event('xhr-destroyed')
    def original(self):
        if self.ignore:return ''
        self.clock+=.001;before=self.clocks();self.sequence+=1;self.clock+=.001
        value=dict(iosPlacesHttpVersion=1,requestId=self.requests[-1]['commandId'],runId=self.requests[-1]['runId'],instance='c'*32,
            sequence=self.sequence,processId=42,clockDomain='native-process-places-http',clockBefore=before,
            clockAfter=self.clocks(),events=deepcopy(self.events))
        if self.mutate:self.mutate(value)
        self.last=deepcopy(value);return json.dumps(value)
    def reader(self):return http.IOSPlacesHttp(self.send,self.original,self.native_clock,lambda:self.live,42,
        monotonic=lambda:self.clock,sleep=self.sleep)
    def model(self,raw,*,origin=ORIGIN,run=RUN,query=''):
        # Execute untouched original JS filtering and QML materialization.
        script=ROOT/'scripts/system/places/places.js';qml=ROOT/'scripts/system/places/PicoPlaces.qml'
        program=r'''
const fs=require('node:fs'),vm=require('node:vm');
function section(source,a,b){let start=source.indexOf(a),end=source.indexOf(b,start+a.length);if(start<0||end<=start)throw Error('original source moved');return source.slice(start,end);}
const input=JSON.parse(process.argv[3]);let rows=[];
const p={Window:{protocolSignature:()=>process.argv[5]},placesData:input,portalList:[],placesOfTheCurrentDomain:[],
 nbrPlaceProtocolKnown:0,nbrPlacesNoProtocolMatch:0,location:{domainID:'other'},getSeededRandomForString:()=>.5,
 getListFromArray:a=>a.join(','),zeroPad:n=>String(n),aplphabetize:n=>n};
vm.createContext(p);vm.runInContext(section(fs.readFileSync(process.argv[1],'utf8'),'    function processData(', '    function getPositionFromPath('),p);
p.processData({order:0,url:process.argv[4],region:'owned'});
const q={records:p.portalList,search:{text:process.argv[6]},maturityFilter:['everyone'],qsTr:s=>s,
 placesModel:{clear:()=>rows=[],append:r=>rows.push(r)}};
vm.createContext(q);vm.runInContext(section(fs.readFileSync(process.argv[2],'utf8'),'    function rebuildPlaces(', '    function toggleMaturity('),q);q.rebuildPlaces();
process.stdout.write(JSON.stringify({records:p.portalList,rows}));
'''
        result=subprocess.run(['node','-e',program,str(script),str(qml),raw.decode(),origin,INPUTS['protocolSignature'],query],capture_output=True,text=True,timeout=5)
        if result.returncode:raise AssertionError(result.stderr)
        materialized=json.loads(result.stdout);root=page();root['records']=materialized['records'];root['lists']['places']['rows']=materialized['rows']
        self.clock+=.001;before=self.clocks();self.clock+=.001
        return dict(iosPlacesModelVersion=1,requestId='ios-'+uuid.uuid4().hex,runId=run,instance='f'*32,sequence=1,
            processId=42,clockDomain='native-main-places-model',clockBefore=before,clockAfter=self.clocks(),complete=True,tabletShown=True,roots=[root])


class PlacesHttpTests(unittest.TestCase):
    def source(self,*,read=True):
        source=Boundary();provider=NavigationResources(INPUTS,clock_ms=source.epoch)
        provider.provision(RUN);provider.activate(RUN,TICKET);source.provider_floor=provider.snapshot(RUN)['capturedEpochMs'];source.begin()
        with provider.response(DIRECTORY,QUERY) as response:
            code,raw,response_id=response;self.assertEqual(200,code)
        source.response(raw,response_id,read=read)
        return source,provider,raw
    def join(self,source,provider,model,**change):
        args=dict(provider_status=provider.snapshot(RUN),provider_instance=provider.instance,inputs=INPUTS,
            owned_origin=ORIGIN,run=RUN,ticket=TICKET,after_epoch=source.events[0]['clock']['epochMs'],after_event=0)
        args['provider_after_epoch']=source.provider_floor
        args.update(change);return http.consumed(source.reader().read(RUN),model,**args)

    def test_original_bytes_actual_processor_and_materialized_row_join_without_retiming(self):
        source,provider,raw=self.source();model=source.model(raw);result=self.join(source,provider,model)
        self.assertEqual(source.events[0],result['nativeCreated']);self.assertEqual(source.events[5],result['nativeReply'])
        self.assertEqual(provider.snapshot(RUN)['responses'][0],result['http'])
        self.assertEqual(json.loads(raw)['data']['places'][0]['description'],result['row']['placeDescription'])
        self.assertEqual(source.xhr,result['xhrId']);self.assertEqual(context(RUN)['destination'],result['row']['placeId'])
        self.assertFalse(http.drained(source.last,[source.xhr]))

    def test_server_delivery_or_text_read_without_materialized_effect_cannot_pass(self):
        for fault in ('no-read','empty','wrong-protocol','wrong-row','old-raw-record'):
            source,provider,raw=self.source(read=fault!='no-read');model=source.model(raw)
            if fault=='empty':model['roots'][0]['lists']['places']['rows']=[]
            elif fault=='wrong-protocol':source.events[0]['details']['protocolSignature']='AQEBAQEBAQEBAQEBAQEBAQ=='
            elif fault=='wrong-row':model['roots'][0]['lists']['places']['rows'][0]['placeAddress']='hifi://foreign'
            elif fault=='old-raw-record':model['roots'][0]['records'][0]['description']='old response'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.join(source,provider,model)

    def test_new_native_envelope_and_text_read_cannot_refresh_a_previous_responses_model(self):
        source,provider,first=self.source();old=source.model(first)
        with provider.response(DIRECTORY,QUERY) as response:_,fresh,response_id=response
        self.assertNotEqual(json.loads(first)['data']['places'][0]['description'],json.loads(fresh)['data']['places'][0]['description'])
        floor=len(source.events);source.xhr=uuid.uuid4().hex;source.reply=uuid.uuid4().hex;source.begin();source.response(fresh,response_id)
        # Retiming the old materialized rows into a fresh native wrapper still
        # cannot supply the fresh per-response field in the actual row/record.
        model=source.model(first);self.assertEqual(old['roots'][0]['records'],model['roots'][0]['records'])
        with self.assertRaises(NativeUIError):self.join(source,provider,model,after_event=floor)
        result=self.join(source,provider,source.model(fresh),after_event=floor)
        self.assertEqual(response_id,result['http']['responseId'])

    def test_foreign_receipt_ticket_pid_clock_barrier_and_missing_origin_fail(self):
        for fault in ('receipt','ticket','pid','old','event-floor','origin'):
            source,provider,raw=self.source();model=source.model(raw);change={}
            if fault=='receipt':
                status=provider.snapshot(RUN);status['responses'][0]['sha256']='f'*64;change['provider_status']=status
            elif fault=='ticket':change['ticket']='d'*32
            elif fault=='pid':model['processId']=43
            elif fault=='old':change['after_epoch']=source.epoch()+1
            elif fault=='event-floor':change['after_event']=len(source.events)
            else:change['owned_origin']='http://foreign.invalid'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.join(source,provider,model,**change)

    def test_actual_reply_timer_callback_and_xhr_destruction_all_required_for_owned_drain(self):
        source,provider,raw=self.source();reader=source.reader();before=reader.read(RUN)
        self.assertFalse(http.drained(before,[source.xhr]));source.retire();complete=reader.read(RUN)
        self.assertTrue(http.drained(complete,[source.xhr]));self.assertEqual(before['events'],complete['events'][:len(before['events'])])
        for omit in ('reply-destroyed','callbacks-released','timer-destroyed','xhr-destroyed'):
            changed=deepcopy(complete);changed['events']=[e for e in changed['events'] if e['kind']!=omit]
            for n,event in enumerate(changed['events'],1):event['sequence']=n
            with self.subTest(omit=omit):
                try:result=http.drained(changed,[source.xhr])
                except NativeUIError:continue
                self.assertFalse(result)
        with self.assertRaises(NativeUIError):http.drained(complete,['a'*32])
        with self.assertRaises(NativeUIError):http.drained(complete,[])

    def test_active_callback_cannot_be_erased_by_a_callback_release_or_idle_ack(self):
        source,provider,raw=self.source();source.event('callback-enter',dict(callback='readystatechange',readyState=4))
        source.event('callbacks-released')
        with self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_changed_history_reused_counter_or_sampler_birth_never_extends_original_history(self):
        for fault in ('history','counter','birth'):
            source,provider,raw=self.source();reader=source.reader();first=reader.read(RUN)
            def mutate(v):
                if fault=='history':v['events'][0]['details']['submitted']['sha256']='f'*64
                elif fault=='counter':v['sequence']=first['sequence']
                else:v['instance']='d'*32
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)
        source.clock+=999;self.assertEqual(first,http.original(first))

    def test_malformed_native_sources_typed_values_clocks_and_foreign_response_body_fail(self):
        mutations=(lambda v:v.update(iosPlacesHttpVersion=True),lambda v:v.update(processId=43),
            lambda v:v.update(clockDomain='host'),lambda v:v['events'][0]['details'].update(scriptSource='https://foreign.invalid/system/places/places.js'),
            lambda v:v['events'][0]['details']['engine'].update(url='qrc:/scripts/other.js'),
            lambda v:v['events'][5]['details'].update(httpStatus=True),
            lambda v:v['events'][5]['details']['body'].update(sha256='f'*64),
            lambda v:v['clockBefore'].update(epochMs=v['clockBefore']['epochMs']-10000))
        for mutate in mutations:
            source,provider,raw=self.source();source.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_missing_reply_or_foreign_nonce_is_one_send_and_not_empty_history(self):
        for fault in ('missing','foreign','missing-hook'):
            source=Boundary();source.ignore=fault=='missing'
            if fault=='foreign':source.mutate=lambda v:v.update(requestId='ios-'+'d'*32)
            elif fault=='missing-hook':source.mutate=lambda v:(v.clear(),v.update(requestId=source.requests[-1]['commandId'],status='unavailable'))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_closed_fixture_command_and_probe_only_accept_original_passive_query(self):
        query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=http.ACTION,runId=RUN)
        fixture=FixtureState();self.assertEqual(query,fixture.set_client_command(query))
        for change in (dict(expected=True),dict(path='/private/foreign'),dict(schemaVersion=True)):
            with self.assertRaises((ValueError,RuntimeError)):fixture.set_client_command(query|change)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureIOSPlacesHttp:c=>{calls++;return {requestId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-places-http',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||!files[0].v.original||files[0].name!=='feature-ios-places-http.json')throw Error('missing original or resend');
applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32),expected:true});if(calls!==1)throw Error('wanted outcome admitted');
delete Test.featureIOSPlacesHttp;applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing source became idle');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_loopback_response_and_receipt_join_actual_product_functions(self):
        harness=resources_tests.NavigationResourcesTests();harness.setUp();self.addCleanup(harness.doCleanups)
        run=harness.open();provider_floor=harness.client.navigation_status()['capturedEpochMs']
        source=Boundary();source.clock=time.time();source.epoch=lambda:round(source.clock*1000)
        native_floor=source.native_clock();source.begin(harness.origin)
        status,raw,response=harness.fetch(DIRECTORY+'?'+QUERY);self.assertEqual(200,status);source.response(raw,response)
        model=source.model(raw,origin=harness.origin,run=run)
        value=source.reader().read(run)
        result=http.consumed(value,model,provider_status=harness.client.navigation_status(),provider_instance=harness.provider.instance,
            inputs=resources_tests.INPUTS,owned_origin=harness.origin,run=run,ticket=resources_tests.TICKET,
            after_epoch=native_floor,provider_after_epoch=provider_floor,after_event=0)
        self.assertEqual(response,result['http']['responseId']);harness.client.close()

    def test_provider_clock_offset_is_not_relabelled_as_native_time(self):
        source=Boundary();provider=NavigationResources(INPUTS,clock_ms=lambda:source.epoch()+86400000)
        provider.provision(RUN);provider.activate(RUN,TICKET);source.provider_floor=provider.snapshot(RUN)['capturedEpochMs']
        source.begin()
        with provider.response(DIRECTORY,QUERY) as response:_,raw,response_id=response
        source.response(raw,response_id);model=source.model(raw);result=self.join(source,provider,model)
        self.assertGreater(result['http']['completedEpochMs'],result['nativeRead']['clock']['epochMs']+80000000)
        self.assertEqual(provider.snapshot(RUN)['responses'][0],result['http'])
        with self.assertRaises(NativeUIError):self.join(source,provider,model,provider_after_epoch=provider.snapshot(RUN)['capturedEpochMs']+1)

    def transport(self,source):
        native=Native();clock=ClockBoundary();observer=native.observer()
        observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:9000
        def stamp(value):
            source.native_clock();epoch=source.epoch();value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(query);native.echo=json.dumps(query).encode()
            if query['action']=='feature-native-observe':clock.send(query)
            else:source.send(query)
            return native
        def execute(session,operation,values):
            self.assertEqual('mobile: pullFile',operation);path=values['remotePath'];native.reads.append(path)
            prefix='@org.example.client:documents/owned-results/'
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+http.FILE))
            raw=clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(raw.encode()).decode()
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute)):
            boundary.start();self.addCleanup(boundary.stop)
        return native,observer

    def test_http_afc_factory_uses_distinct_native_clocks_and_process_bound_original(self):
        source=Boundary();native,observer=self.transport(source);reader=observer.places_http();value=reader.read(RUN)
        self.assertEqual(source.last,value);self.assertEqual(3,len(native.commands));self.assertEqual(3,len(native.reads))
        self.assertIn('iosPlacesHttpAcquisitionVersion',reader.acquisition)
        self.assertNotIn('iosPlacesModelAcquisitionVersion',reader.acquisition)
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],value['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],value['clockAfter']['epochMs'])

    def test_process_replaced_after_query_cannot_adopt_afc_history(self):
        source=Boundary();native,observer=self.transport(source);send=source.send
        def replaced(query):send(query);native.pid=43
        source.send=replaced
        with self.assertRaises(NativeUIError):observer.places_http().read(RUN)
        self.assertEqual(1,len(source.requests));self.assertFalse(any(path.endswith('/'+http.FILE) for path in native.reads))


if __name__=='__main__':unittest.main()
