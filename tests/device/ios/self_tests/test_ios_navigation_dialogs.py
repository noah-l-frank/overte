"""Real loopback 404/probe/transport; native Qt callbacks and SDK modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import subprocess
import time
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY,QUERY
from ios.adapters import feature_observation,normal_input,navigation_dialogs as dialogs,navigation_dialog_controls as controls
from ios.self_tests.test_ios_location_bookmarks import Boundary as Clocks,RUN
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests import test_ios_normal_input as input_tests
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source
from self_tests import test_navigation_resources as resources_tests

ORIGIN='http://controlled.invalid:49121'
INPUTS=dict(protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==',sourceRevision='c'*40,sceneUrl=ORIGIN+'/scene.json')
TICKET='b'*32


class Boundary(Clocks):
    def __init__(self):
        super().__init__(None);self.run=RUN;self.events=[];self.rows=[];self.id=uuid.uuid4().hex
        self.native_error=None;self.foreign=0;self.complete=True;self.enums=dict(okButton=1024,criticalIcon=4)
    def event(self,kind,details=None):
        self.clock+=.001;event=dict(sequence=len(self.events)+1,eventId=uuid.uuid4().hex,dialogId=self.id,
            kind=kind,clock=self.clocks(),details=deepcopy(details or {}));self.events.append(event);return event
    def create(self,response='d'*32,*,origin=ORIGIN,dialog=True,listener=True):
        self.clock+=.001
        self.native_error=dict(sequence=1,eventId=uuid.uuid4().hex,runId=self.run,responseId=response,origin=origin,
            httpStatus=404,networkError=203,contentNotFound=True,current=True,lookupGeneration=2,callbackEpochMs=self.epoch())
        error=dict(navigationErrorContextVersion=1,instance='e'*32,processId=42,event=self.native_error)
        qml='qrc:/qml/dialogs/TabletMessageBox.qml'
        self.event('created',dict(source='AddressBarDialog.displayAddressNotFoundMessage',error=error,
            dialogCreated=dialog,listenerCreated=listener,qmlSource=qml if dialog else ''))
        root=dict(qmlSource=qml,visible=True,windowPresent=True,text=dialogs.TEXT,buttons=self.enums['okButton'],
            icon=self.enums['criticalIcon'],clickedButton=0) if dialog else None
        self.rows=[dict(dialogId=self.id,listenerAlive=listener,creatorAlive=True,creatorVisible=True,dialog=root)]
    def respond(self,value=None):
        value=self.enums['okButton'] if value is None else value
        self.event('response',dict(kind='int',value=value,valueSha256=hashlib.sha256(('Qt-int:'+str(value)).encode()).hexdigest()))
        if self.rows[0]['dialog'] is not None:self.rows[0]['dialog']['clickedButton']=value
    def destroy(self,*,dialog=True,listener=True):
        if dialog:self.event('dialog-destroyed');self.rows[0]['dialog']=None
        if listener:self.event('listener-destroyed');self.rows[0]['listenerAlive']=False
    def original(self):
        if self.ignore:return ''
        self.clock+=.001;before=self.clocks();self.sequence+=1;self.clock+=.001
        value=dict(iosNavigationDialogsVersion=1,requestId=self.requests[-1]['commandId'],runId=self.requests[-1]['runId'],
            instance='c'*32,processId=42,sequence=self.sequence,clockDomain='native-main-navigation-dialogs',
            clockBefore=before,clockAfter=self.clocks(),complete=self.complete,dialogs=deepcopy(self.rows),events=deepcopy(self.events),
            enums=deepcopy(self.enums),foreignModals=self.foreign)
        if self.mutate:self.mutate(value)
        self.last=deepcopy(value);return json.dumps(value)
    def reader(self):return dialogs.IOSNavigationDialogs(self.send,self.original,self.native_clock,lambda:self.live,42,
        monotonic=lambda:self.clock,sleep=self.sleep)
    def replies(self):
        return dict(navigationReplyVersion=1,commandId='ios-'+uuid.uuid4().hex,runId=self.run,instance='e'*32,sequence=1,
            processId=42,capturedEpochMs=self.epoch()+1,currentLookupGeneration=2,currentLookupActive=True,events=[deepcopy(self.native_error)])
    def controls(self,epoch=None):
        original=[]
        for id in ('navigation.error.page','navigation.error.ok'):
            original.append(dict(id=id,token=str(uuid.uuid5(uuid.NAMESPACE_URL,id)),enabled=True,focused=False,profile=controls.PROFILE,
                dialogId=self.id,runId=self.run,errorInstance='e'*32,errorEventId=self.native_error['eventId'],lookupGeneration=2,
                qmlSource='qrc:/qml/dialogs/TabletMessageBox.qml',inputReady=id.endswith('.ok')))
        return dict(navigationDialogControlsVersion=1,scope=dict(instance=str(uuid.UUID(int=10)),processId=42,sequence=0,
            observationSequence=1,elapsedMs=100,sampleEpochMs=self.epoch()+1 if epoch is None else epoch),controls=original)


class InputBoundary(input_tests.Boundary):
    def __init__(self,source):
        super().__init__(field='navigation.error.ok');self.source=source;self.counter=0;self.ignore=False;self.before_input=None
        self.row_source=source.controls();self.lost=False
    def observed(self):
        original=super().observed();self.counter+=1
        original.update(navigationDialogControlsVersion=1,navigationDialogSourceSequence=self.counter,
            elapsedMs=100+self.counter,controls=[dict(deepcopy(row),frame=dict(x=10,y=20,width=250,height=50)) for row in self.row_source['controls']])
        return original
    def post(self,request,timeout):
        payload=json.loads(request.data)
        if payload['operation']=='edit' and self.before_input:self.before_input()
        result=super().post(request,timeout)
        if payload['operation']=='edit':
            found=[row for row in self.row_source['controls'] if row['id']=='navigation.error.ok' and row['token']==payload['input']['fieldToken']]
            if len(found)!=1:self.receipt['status']['performed']=False
            elif not self.ignore:self.source.respond()
            if self.lost:raise OSError('Synthetic lost result after actual modeled pointer delivery')
        return result


class NavigationDialogsTests(unittest.TestCase):
    def source(self):
        source=Boundary();provider=NavigationResources(INPUTS,clock_ms=lambda:source.epoch()+86400000)
        provider.provision(RUN);provider.activate(RUN,TICKET);source.provider_floor=provider.snapshot(RUN)['capturedEpochMs'];source.native_floor=source.epoch()
        with provider.response(DIRECTORY+'/'+context(RUN)['hidden'],'') as response:
            status,raw,id=response;self.assertEqual(404,status)
        source.create(id);return source,provider
    def join(self,source,provider,*,value=None,replies=None,**changes):
        value=source.reader().read(RUN) if value is None else value
        args=dict(provider_status=provider.snapshot(RUN),provider_instance=provider.instance,inputs=INPUTS,owned_origin=ORIGIN,
            run=RUN,ticket=TICKET,native_after_epoch=source.native_floor,provider_after_epoch=source.provider_floor,after_event=0)
        args.update(changes);return dialogs.owned_missing(value,source.replies() if replies is None else replies,**args)

    def test_original_native_404_visible_modal_and_provider_join_keep_distinct_clocks_and_original_events(self):
        source,provider=self.source();result=self.join(source,provider)
        self.assertEqual(source.events[0],result['created']);self.assertEqual(source.native_error,result['nativeError'])
        self.assertEqual(provider.snapshot(RUN)['responses'][0],result['http']);self.assertEqual(source.id,result['dialogId'])
        self.assertGreater(result['http']['completedEpochMs'],result['nativeError']['callbackEpochMs']+80000000)
        self.assertEqual(dialogs.TEXT,result['dialog']['text'])

    def test_acknowledged_missing_or_hidden_modal_is_not_a_current_error_outcome(self):
        for fault in ('no-root','hidden','wrong-text','foreign-modal','incomplete','responded'):
            source,provider=self.source()
            if fault=='no-root':source.rows[0]['dialog']=None;source.events[0]['details'].update(dialogCreated=False,qmlSource='')
            elif fault=='hidden':source.rows[0]['dialog']['visible']=False
            elif fault=='wrong-text':source.rows[0]['dialog']['text']='There is another error'
            elif fault=='foreign-modal':source.foreign=1
            elif fault=='incomplete':source.complete=False
            else:source.respond()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.join(source,provider)

    def test_old_foreign_retired_or_wrong_lookup_cannot_adopt_a_same_text_modal(self):
        for fault in ('generation','retired','error-id','instance','pid','ticket','native-floor','provider-floor','event-floor'):
            source,provider=self.source();replies=source.replies();changes={}
            if fault=='generation':replies['currentLookupGeneration']=3
            elif fault=='retired':replies['currentLookupActive']=False
            elif fault=='error-id':replies['events'][0]['eventId']='f'*32
            elif fault=='instance':replies['instance']='f'*32
            elif fault=='pid':replies['processId']=43
            elif fault=='ticket':changes['ticket']='f'*32
            elif fault=='native-floor':changes['native_after_epoch']=source.epoch()+100
            elif fault=='provider-floor':changes['provider_after_epoch']=provider.snapshot(RUN)['capturedEpochMs']+1
            else:changes['after_event']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.join(source,provider,replies=replies,**changes)

    def test_response_and_scheduled_deletion_do_not_replace_actual_dialog_and_listener_destruction(self):
        source,provider=self.source();reader=source.reader();before=reader.read(RUN)
        self.assertFalse(dialogs.drained(before,[source.id]));source.respond();responded=reader.read(RUN)
        self.assertFalse(dialogs.drained(responded,[source.id],require_ok=True));source.destroy(listener=False)
        self.assertFalse(dialogs.drained(reader.read(RUN),[source.id],require_ok=True))
        source.destroy(dialog=False);after=reader.read(RUN);self.assertTrue(dialogs.drained(after,[source.id],require_ok=True))
        self.assertEqual(before['events'],after['events'][:len(before['events'])])
        with self.assertRaises(NativeUIError):dialogs.drained(after,['a'*32])
        with self.assertRaises(NativeUIError):dialogs.drained(after,[])

    def test_destroyed_without_normal_ok_can_retire_owned_resources_but_cannot_prove_dismiss_step(self):
        source,provider=self.source();source.respond(0);source.destroy();value=source.reader().read(RUN)
        self.assertTrue(dialogs.drained(value,[source.id]));self.assertFalse(dialogs.drained(value,[source.id],require_ok=True))

    def test_changed_history_duplicate_callback_or_reused_counter_cannot_extend_original_history(self):
        for fault in ('history','counter','instance','response'):
            source,provider=self.source();reader=source.reader();first=reader.read(RUN)
            if fault=='response':source.respond();source.respond()
            else:
                def mutate(value):
                    if fault=='history':value['events'][0]['details']['error']['event']['responseId']='f'*32
                    elif fault=='counter':value['sequence']=first['sequence']
                    else:value['instance']='f'*32
                source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)
        source.clock+=1000;self.assertEqual(first,dialogs.original(first))

    def test_wrong_source_version_types_epoch_or_run_are_one_send_failures(self):
        mutations=(lambda v:v.update(iosNavigationDialogsVersion=True),lambda v:v.update(processId=43),lambda v:v.update(runId='f'*32),
            lambda v:v.update(clockDomain='afc-file-mtime'),lambda v:v['clockBefore'].update(epochMs=v['clockBefore']['epochMs']-10000),
            lambda v:v['events'][0]['details']['error'].update(navigationErrorContextVersion=True),
            lambda v:v['dialogs'][0]['dialog'].update(qmlSource='https://foreign.invalid/dialogs/TabletMessageBox.qml'))
        for mutate in mutations:
            source,provider=self.source();source.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_missing_reply_or_foreign_nonce_never_becomes_empty_absence_and_never_resends(self):
        for fault in ('missing','nonce','missing-hook'):
            source=Boundary();source.ignore=fault=='missing'
            if fault=='nonce':source.mutate=lambda v:v.update(requestId='ios-'+'f'*32)
            elif fault=='missing-hook':source.mutate=lambda v:(v.clear(),v.update(requestId=source.requests[-1]['commandId'],status='unavailable'))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_actual_control_reference_joins_native_created_dialog_without_refreshing_its_identity(self):
        source,provider=self.source();value=source.reader().read(RUN);snapshot=source.controls(value['clockAfter']['epochMs']+1)
        ref=controls.join_observation(snapshot,value,source.id);self.assertEqual(source.id,ref['control']['dialogId'])
        for key,new in (('dialogId','f'*32),('errorEventId','f'*32),('lookupGeneration',3),('runId','f'*32)):
            changed=deepcopy(snapshot)
            for row in changed['controls']:row[key]=new
            with self.subTest(key=key),self.assertRaises(NativeUIError):controls.join_observation(changed,value,source.id)

    def test_actual_http_afc_pointer_ack_is_distinct_from_normal_ok_response_and_resource_absence(self):
        source,provider=self.source();target=InputBoundary(source)
        with patch.object(normal_input,'urlopen',target.post):
            native=target.input();ref=controls.reference(controls.project(native.capture()))
            self.assertEqual({'performed':True},native.navigation_error_input(reference=ref))
        after=source.reader().read(RUN);self.assertIsNotNone(dialogs.history(after)[source.id]['response'])
        self.assertFalse(dialogs.drained(after,[source.id],require_ok=True))
        edits=[row for row in target.requests if row['operation']=='edit'];self.assertEqual(1,len(edits))
        self.assertEqual(ref['control']['token'],edits[0]['input']['fieldToken']);self.assertNotIn('expected',edits[0]['input'])

    def test_ignored_pointer_ack_does_not_report_the_dialog_dismissed(self):
        source,provider=self.source();target=InputBoundary(source);target.ignore=True
        with patch.object(normal_input,'urlopen',target.post):
            native=target.input();ref=controls.reference(controls.project(native.capture()));native.navigation_error_input(reference=ref)
        self.assertFalse(dialogs.drained(source.reader().read(RUN),[source.id],require_ok=True));self.assertEqual(1,len(source.events))

    def test_replaced_dialog_before_delivery_does_not_borrow_a_fresh_reference_or_resend(self):
        source,provider=self.source();target=InputBoundary(source)
        with patch.object(normal_input,'urlopen',target.post):
            native=target.input();ref=controls.reference(controls.project(native.capture()))
            for row in target.row_source['controls']:row['dialogId']='f'*32
            with self.assertRaises(NativeUIError):native.navigation_error_input(reference=ref)
        self.assertFalse(any(row['operation']=='edit' for row in target.requests))

    def test_lost_result_after_pointer_delivery_retains_response_and_does_not_repeat_input(self):
        source,provider=self.source();target=InputBoundary(source);target.lost=True
        with patch.object(normal_input,'urlopen',target.post):
            native=target.input();ref=controls.reference(controls.project(native.capture()))
            with self.assertRaises(OSError):native.navigation_error_input(reference=ref)
        self.assertEqual(1,sum(row['operation']=='edit' for row in target.requests))
        self.assertEqual('response',source.events[-1]['kind']);self.assertFalse(dialogs.drained(source.reader().read(RUN),[source.id]))

    def test_replaced_dialog_at_native_delivery_rejects_original_token_without_another_click(self):
        source,provider=self.source();target=InputBoundary(source)
        def replace():
            for row in target.row_source['controls']:row.update(dialogId='f'*32,token=str(uuid.uuid4()))
        target.before_input=replace
        with patch.object(normal_input,'urlopen',target.post):
            native=target.input();ref=controls.reference(controls.project(native.capture()))
            with self.assertRaises(NativeUIError):native.navigation_error_input(reference=ref)
        self.assertEqual(1,sum(row['operation']=='edit' for row in target.requests));self.assertEqual(1,len(source.events))

    def test_failed_actual_modal_creation_does_not_pass_missing_outcome_but_tracks_listener_retirement(self):
        source=Boundary();source.create(dialog=False);reader=source.reader();value=reader.read(RUN)
        self.assertFalse(dialogs.drained(value,[source.id]));source.respond(0);source.destroy(dialog=False)
        after=reader.read(RUN);self.assertTrue(dialogs.drained(after,[source.id]))
        self.assertFalse(dialogs.drained(after,[source.id],require_ok=True))

    def test_native_enum_original_is_preserved_instead_of_a_guessed_python_button_number(self):
        source=Boundary();source.enums['okButton']=8192;source.create();source.respond();source.destroy()
        value=source.reader().read(RUN);self.assertTrue(dialogs.drained(value,[source.id],require_ok=True))
        self.assertEqual(8192,dialogs.history(value)[source.id]['response']['details']['value'])

    def transport(self,source):
        native=Native();clock=ClockBoundary();observer=native.observer()
        observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:1
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
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+dialogs.FILE))
            raw=clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(raw.encode()).decode()
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute)):
            boundary.start();self.addCleanup(boundary.stop)
        return native,observer

    def test_bound_factory_uses_original_native_clocks_and_fixed_modal_file(self):
        source,provider=self.source();native,observer=self.transport(source);reader=observer.navigation_dialogs();value=reader.read(RUN)
        self.assertEqual(source.last,value);self.assertEqual(3,len(native.commands));self.assertEqual(3,len(native.reads))
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],value['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],value['clockAfter']['epochMs'])
        self.assertIn('iosNavigationDialogsAcquisitionVersion',reader.acquisition)

    def test_process_replacement_after_query_cannot_adopt_native_modal_or_controls(self):
        source=Boundary();native,observer=self.transport(source);send=source.send
        def replaced(query):send(query);native.pid=43
        source.send=replaced
        with self.assertRaises(NativeUIError):observer.navigation_dialogs().read(RUN)
        self.assertEqual(1,len(source.requests));self.assertFalse(any(path.endswith('/'+dialogs.FILE) for path in native.reads))

    def test_real_loopback_missing_reply_is_the_independent_receipt_for_the_same_native_modal(self):
        harness=resources_tests.NavigationResourcesTests();harness.setUp();self.addCleanup(harness.doCleanups);run=harness.open()
        floor=harness.client.navigation_status()['capturedEpochMs'];source=Boundary();source.run=run
        source.clock=time.time();source.epoch=lambda:round(source.clock*1000);native_floor=source.epoch()
        status,raw,response=harness.fetch(DIRECTORY+'/'+context(run)['hidden']);self.assertEqual(404,status)
        source.create(response,origin=harness.origin);value=source.reader().read(run)
        result=dialogs.owned_missing(value,source.replies(),provider_status=harness.client.navigation_status(),provider_instance=harness.provider.instance,
            inputs=resources_tests.INPUTS,owned_origin=harness.origin,run=run,ticket=resources_tests.TICKET,native_after_epoch=native_floor,
            provider_after_epoch=floor,after_event=0)
        self.assertEqual(response,result['nativeError']['responseId']);harness.client.close()

    def test_closed_fixture_and_actual_probe_never_accept_wanted_dialog_state_or_reissue_query(self):
        query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=dialogs.ACTION,runId=RUN);fixture=FixtureState()
        self.assertEqual(query,fixture.set_client_command(query))
        for update in (dict(expected='not-found'),dict(path='/private/foreign'),dict(schemaVersion=True)):
            with self.assertRaises((ValueError,RuntimeError)):fixture.set_client_command(query|update)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureIOSNavigationDialogs:c=>{calls++;return {requestId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-navigation-dialogs',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||!files[0].v.original||files[0].name!=='feature-ios-navigation-dialogs.json')throw Error('missing original or resend');
applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32),expected:'not-found'});if(calls!==1)throw Error('wanted modal admitted');
delete Test.featureIOSNavigationDialogs;applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing source became absence');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
