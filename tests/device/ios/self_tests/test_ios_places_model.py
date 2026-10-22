"""Original model/queue counterexamples; SDK/Qt sources modeled, no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import subprocess
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation,places_model as places
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_location_bookmarks import Boundary as Clocks,RUN
from ios.self_tests.test_ios_places_controls import value as controls_value
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source


def page(*,active=True):
    return dict(rootId=str(uuid.UUID(int=500)),qmlSource='qrc:/scripts/system/places/PicoPlaces.qml',windowPresent=True,
        visible=active,active=active,loading=False,currentAddress='hifi://actual/1,2,3',directoryWarning='',
        records=[dict(id='actual-id',name='actual name',address='hifi://actual',description='actual description')],
        bookmarkAddresses={'unowned':'hifi://unowned'},maturityFilter=['everyone'],pendingCommands=[],timerRunning=False,
        tab=0,search='',dialog=dict(visible=False,originalName='',address='',name=''),
        lists=dict(places=dict(visible=active,rows=[dict(placeName='actual name',placeAddress='hifi://actual',
            placeDescription='actual description',attendance=3,capacity=10,placeId='actual-id')]),
            bookmarks=dict(visible=False,rows=[dict(bookmarkName='unowned',bookmarkAddress='hifi://unowned')]),
            servers=dict(visible=False,rows=[dict(serverUrl='https://actual.invalid',serverIndex=0,serverRegion='local',
                                                 fetched=True,pinned=False,failed=False)])))


class Boundary(Clocks):
    def __init__(self):
        super().__init__(None);self.pages=[page()];self.shown=True;self.complete=True
    def original(self):
        if self.ignore:return ''
        self.clock+=.001;before=self.clocks();self.sequence+=1;self.clock+=.001
        value=dict(iosPlacesModelVersion=1,requestId=self.requests[-1]['commandId'],runId=RUN,instance='c'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-places-model',clockBefore=before,
            clockAfter=self.clocks(),complete=self.complete,tabletShown=self.shown,roots=deepcopy(self.pages))
        if self.mutate:self.mutate(value)
        self.last=deepcopy(value);return json.dumps(value)
    def reader(self):return places.IOSPlacesModel(self.send,self.original,self.native_clock,lambda:self.live,42,
        monotonic=lambda:self.clock,sleep=self.sleep)


class PlacesModelTests(unittest.TestCase):
    def test_actual_model_rows_and_raw_records_are_distinct_and_keep_order_and_duplicates(self):
        source=Boundary();rows=source.pages[0]['lists']['places']['rows'];rows.append(deepcopy(rows[0]))
        source.pages[0]['records'].append(dict(id='filtered-out',name='hidden',address='hifi://hidden'))
        value=source.reader().read(RUN)
        self.assertEqual(source.last,value);self.assertEqual(source.pages[0],places.current(value))
        self.assertEqual(2,len(places.current(value)['lists']['places']['rows']))
        self.assertEqual('filtered-out',places.current(value)['records'][1]['id'])
        self.assertEqual('actual-id',places.current(value)['lists']['places']['rows'][1]['placeId'])
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(source.requests[0]))

    def test_changed_search_text_or_loaded_bookmark_map_does_not_reconstruct_materialized_rows(self):
        source=Boundary();source.pages[0]['search']='query with no match'
        source.pages[0]['bookmarkAddresses']={'new':'hifi://new'}
        value=places.current(source.reader().read(RUN))
        self.assertEqual('actual-id',value['lists']['places']['rows'][0]['placeId'])
        self.assertEqual('unowned',value['lists']['bookmarks']['rows'][0]['bookmarkName'])
        self.assertEqual({'new':'hifi://new'},value['bookmarkAddresses'])

    def test_retained_hidden_root_pending_timer_loading_or_dialog_prevents_queue_drain(self):
        for key,value in (('pendingCommands',[dict(channel='com.overte.places',action='ADD_BOOKMARK',name='pending')]),
                          ('timerRunning',True),('loading',True),('dialog',dict(visible=True,originalName='',address='',name='draft'))):
            source=Boundary();source.shown=False;source.pages=[page(active=False)];source.pages[0][key]=value
            original=source.reader().read(RUN)
            self.assertFalse(places.drained(original));self.assertEqual(value,original['roots'][0][key])
            source.pages[0][key]=page(active=False)[key]
            self.assertTrue(places.drained(source.reader().read(RUN)))

    def test_destroyed_roots_and_incomplete_inventory_are_not_equivalent(self):
        source=Boundary();source.pages=[];source.shown=False
        reader=source.reader();original=reader.read(RUN);self.assertTrue(places.drained(original))
        source.complete=False;incomplete=reader.read(RUN);self.assertFalse(incomplete['complete'])
        with self.assertRaises(NativeUIError):places.drained(incomplete)
        with self.assertRaises(NativeUIError):places.drained(dict(complete=True,roots=[]))

    def test_current_input_root_join_requires_original_pid_source_birth_and_clock(self):
        source=Boundary();value=source.reader().read(RUN);controls=controls_value()
        controls['scope']['sampleEpochMs']=value['clockAfter']['epochMs']+1
        self.assertEqual(source.pages[0],places.join_controls(value,controls))
        for update in ('pid','root','source','old','expired'):
            changed=deepcopy(controls)
            if update=='pid':changed['scope']['processId']=43
            elif update=='root':changed['controls'][0]['rootId']=str(uuid.UUID(int=501))
            elif update=='source':changed['controls'][0]['qmlSource']='file:///app/scripts/system/places/PicoPlaces.qml'
            elif update=='old':changed['scope']['sampleEpochMs']=value['clockAfter']['epochMs']-1
            else:changed['scope']['sampleEpochMs']=value['clockAfter']['epochMs']+1500
            with self.subTest(fault=update),self.assertRaises(NativeUIError):places.join_controls(value,changed)

    def test_duplicate_or_two_active_roots_and_invalid_row_types_fail_without_resend(self):
        mutations=(lambda v:v.update(iosPlacesModelVersion=True),lambda v:v.update(processId=43),
            lambda v:v.update(complete=1),lambda v:v.update(clockDomain='controller-host'),
            lambda v:v['roots'].append(deepcopy(v['roots'][0])),
            lambda v:v['roots'].append(dict(deepcopy(v['roots'][0]),rootId=str(uuid.UUID(int=501)))),
            lambda v:v['roots'][0]['lists']['places']['rows'][0].update(attendance=True),
            lambda v:v['roots'][0]['lists']['places']['rows'][0].update(placeAddress=3),
            lambda v:v['roots'][0]['lists']['servers']['rows'][0].update(fetched=1),
            lambda v:v['roots'][0].update(pendingCommands=[dict(channel='foreign',action='READY_FOR_CONTENT')]))
        for mutate in mutations:
            source=Boundary();source.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_foreign_nonce_missing_result_and_stale_native_floor_never_reissue_query(self):
        for fault in ('nonce','missing','old','slow'):
            source=Boundary();source.ignore=fault=='missing'
            if fault=='nonce':source.mutate=lambda v:v.update(requestId='ios-'+'b'*32)
            elif fault=='old':source.mutate=lambda v:v['clockBefore'].update(epochMs=v['clockBefore']['epochMs']-100)
            elif fault=='slow':source.mutate=lambda v:v['clockAfter'].update(monotonicMs=v['clockAfter']['monotonicMs']+1500)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.requests))

    def test_new_root_birth_is_retained_but_sampler_replacement_or_counter_reuse_cannot_extend_history(self):
        source=Boundary();reader=source.reader();first=reader.read(RUN)
        source.pages[0]['rootId']=str(uuid.UUID(int=501));second=reader.read(RUN)
        self.assertNotEqual(first['roots'][0]['rootId'],second['roots'][0]['rootId'])
        for mutation in (lambda v:v.update(instance='d'*32),lambda v:v.update(sequence=second['sequence'])):
            source.mutate=mutation
            with self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(second,reader.last)
        source.clock+=999;self.assertEqual(first,places.original(first))

    def test_closed_fixture_command_cannot_carry_expected_rows_or_an_arbitrary_path(self):
        source=Boundary();source.reader().read(RUN);query=source.requests[0];fixture=FixtureState()
        self.assertEqual(query,fixture.set_client_command(query))
        for change in (dict(expectedRows=[]),dict(path='/private/foreign'),dict(schemaVersion=True),dict(runId=RUN+'\n')):
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):fixture.set_client_command(query|change)

    def transport(self,source):
        native=Native();clock=ClockBoundary();observer=native.observer()
        observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:9000
        def stamp(value):
            source.native_clock();epoch=source.epoch()
            value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data))
            native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            if query['action']=='feature-native-observe':clock.send(query)
            else:source.send(query)
            return native
        def execute(session,operation,values):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            path=values['remotePath'];native.reads.append(path)
            prefix='@org.example.client:documents/owned-results/'
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+places.FILE))
            raw=clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(raw.encode()).decode()
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute)):
            boundary.start();self.addCleanup(boundary.stop)
        return native,observer

    def test_factory_joins_original_native_clocks_and_fixed_afc_packet_with_foreign_host_utc(self):
        source=Boundary();native,observer=self.transport(source);reader=observer.places_model();value=reader.read(RUN)
        self.assertEqual(source.last,value);self.assertEqual(3,len(native.commands));self.assertEqual(3,len(native.reads))
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],value['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],value['clockAfter']['epochMs'])
        self.assertEqual(3,len({entry['commandId'] for entry in native.commands}))

    def test_factory_rejects_process_replacement_before_bookmark_model_read(self):
        source=Boundary();native,observer=self.transport(source);send=source.send
        def replaced(query):send(query);native.pid=43
        source.send=replaced
        with self.assertRaises(NativeUIError):observer.places_model().read(RUN)
        self.assertEqual(1,len(source.requests));self.assertEqual(2,len(native.commands))
        self.assertFalse(any(path.endswith('/'+places.FILE) for path in native.reads))

    def test_probe_only_calls_passive_original_hook_once_and_missing_hook_is_unavailable(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureIOSPlacesModel:c=>{calls++;return {requestId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-places-model',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||!files[0].v.original||files[0].name!=='feature-ios-places-model.json')throw Error('missing original or resent query');
for(const update of [{expectedRows:[]},{path:'/private/foreign'},{schemaVersion:true},{commandId:c.commandId+'\n'}])applyClientCommand({...c,...update});
if(calls!==1)throw Error('unsafe command');
delete Test.featureIOSPlacesModel;applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing source became empty model');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
