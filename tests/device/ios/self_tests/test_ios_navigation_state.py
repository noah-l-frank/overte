"""Native state/SDK modeled; actual Python transport, fixture and JS dispatcher."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.native_scene_loads import resource_hash
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation,navigation_state as state
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_location_bookmarks import Boundary as Clocks,RUN
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source
from navigation_observation import viewpoint_urls

URL=viewpoint_urls('http://controlled.invalid/scene.json')['A']


def markers():
    data=json.loads((Path(__file__).resolve().parents[2]/'fixture'/'scene.json').read_text())
    return [dict(id=row['id'].strip('{}'),name=row['name'],type=row['type'],rotation=[0,0,0,1],
        position=[row['position'][axis] for axis in ('x','y','z')],dimensions=[row['dimensions'][axis] for axis in ('x','y','z')],
        color=[row['color'][channel] for channel in ('red','green','blue')],visible=True,collisionless=row['collisionless'])
        for row in data['Entities'] if row['id'].strip('{}') in state.MARKER_IDS]


class Boundary(Clocks):
    def __init__(self):
        super().__init__(None);self.run=RUN;self.url=URL;self.history=None
        self.source=dict(foreground=True,sceneUrl=URL,domain=dict(handlerConnected=True,serverless=True,protocol='http'),
            avatar=dict(feetPosition=[0,0,4],orientation=[0,0,0,1],velocity=[0,0,0],inAir=False,flying=False,modelScale=1),
            view=dict(position=[0,1.6,4],rotation=[0,0,0,1],mode='first person',fieldOfViewDegrees=60,aspectRatio=1.5,perspective=True),
            markers=markers(),absentMarkerIds=[])
    def original(self):
        if self.ignore:return ''
        self.clock+=.001;before=self.clocks();self.sequence+=1;query=self.requests[-1]
        self.clock+=.001;scene=dict(sceneLoadVersion=1,commandId=query['commandId'],runId=self.run,instance='d'*32,
            sequence=self.sequence,processId=42,capturedEpochMs=self.epoch(),currentGeneration=1,pendingLeases=0,complete=True,
            requests=[dict(id='e'*32,kind='request',generation=1,resourceSha256=resource_hash(self.url),
                startedEpochMs=1700000000000,updatedEpochMs=1700000000001,releasedEpochMs=1700000000001,
                phase='committed',pending=False,result=0,bytes=1234)])
        self.clock+=.001
        value=dict(iosNavigationStateVersion=1,requestId=query['commandId'],runId=self.run,instance='c'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-navigation',clockBefore=before,clockAfter=self.clocks(),
            source=deepcopy(self.source)|dict(sceneLoads=scene))
        if self.mutate:self.mutate(value)
        self.last=deepcopy(value);return json.dumps(value)
    def reader(self):return state.IOSNavigationState(self.send,self.original,self.native_clock,lambda:self.live,42,
        monotonic=lambda:self.clock,sleep=self.sleep)


class NavigationStateTests(unittest.TestCase):
    def setUp(self):self.source=Boundary()
    def read(self):return self.source.reader().read(RUN)
    def test_native_clocks_scene_history_and_actual_pose_are_retained_separately(self):
        reader=self.source.reader();value=reader.read(RUN)
        self.assertEqual(self.source.last,value);self.assertEqual(1700000000000,value['source']['sceneLoads']['requests'][0]['startedEpochMs'])
        self.assertEqual(value['source']['avatar'],state.pose_ready(value,URL,'A'))
        self.assertEqual(digest(value),reader.acquisition['originalSha256'])
        self.assertNotIn('passed',value);self.assertNotIn('render',value['source'])
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(self.source.requests[0]))
        self.assertEqual(value['source']['sceneLoads']['requests'],reader.read(RUN)['source']['sceneLoads']['requests'])

    def test_requested_B_with_ignored_actual_motion_is_not_arrival(self):
        url=viewpoint_urls('http://controlled.invalid/scene.json')['B'];self.source.source['sceneUrl']=url
        with self.assertRaises(NativeUIError):state.pose_ready(self.read(),url,'B')
        self.source.source['avatar']['feetPosition']=[2,0,4]
        self.assertEqual([2,0,4],state.pose_ready(self.read(),url,'B')['feetPosition'])

    def test_wanted_label_must_match_the_actual_viewpoint_url(self):
        value=self.read()
        with self.assertRaises(NativeUIError):state.pose_ready(value,URL,'B')
        self.source.source['sceneUrl']=viewpoint_urls(URL)['B']
        with self.assertRaises(NativeUIError):state.pose_ready(self.read(),viewpoint_urls(URL)['B'],'A')

    def test_duplicate_marker_slots_and_nonfinite_physics_are_invalid_originals(self):
        for fault in ('duplicate','nan','boolean','quat','sceneOutsideBracket'):
            source=Boundary()
            def mutate(value):
                if fault=='duplicate':value['source']['markers'][1]['id']=value['source']['markers'][0]['id']
                elif fault=='nan':value['source']['avatar']['velocity'][0]=float('nan')
                elif fault=='boolean':value['source']['avatar']['feetPosition'][0]=False
                elif fault=='quat':value['source']['avatar']['orientation']=[0,0,0,0]
                else:value['source']['sceneLoads']['capturedEpochMs']+=20
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_moving_falling_flying_background_or_wrong_domain_is_not_ready(self):
        for field,new in [('velocity',[.2,0,0]),('inAir',True),('flying',True)]:
            with self.subTest(field=field):
                value=self.read();value['source']['avatar'][field]=new
                with self.assertRaises(NativeUIError):state.pose_ready(value,URL,'A')
        for field,new in [('handlerConnected',False),('serverless',False),('protocol','hifi')]:
            value=self.read();value['source']['domain'][field]=new
            with self.assertRaises(NativeUIError):state.pose_ready(value,URL,'A')
        value=self.read();value['source']['foreground']=False
        with self.assertRaises(NativeUIError):state.pose_ready(value,URL,'A')

    def test_address_and_pose_do_not_hide_missing_wrong_or_moved_scene_markers(self):
        for fault in ('missing','name','color','position','type','visible','collisionless'):
            value=self.read();rows=value['source']['markers']
            if fault=='missing':value['source']['absentMarkerIds']=[rows.pop()['id']]
            else:rows[0][fault]={'name':'foreign','color':[0,0,0],'position':[0,-1,0],'type':'Sphere','visible':False,'collisionless':True}[fault]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):state.pose_ready(value,URL,'A')

    def test_parse_ack_failed_or_pending_old_scene_lease_is_not_committed_arrival(self):
        for fault in ('pending','parsed','failed','incomplete','foreign-resource','generation'):
            value=self.read();scene=value['source']['sceneLoads'];row=scene['requests'][0]
            if fault=='pending':scene['pendingLeases']=1;row.update(pending=True,releasedEpochMs=None)
            elif fault=='parsed':scene['pendingLeases']=1;row.update(phase='parsed',pending=True,releasedEpochMs=None)
            elif fault=='failed':row['phase']='failed'
            elif fault=='incomplete':scene['complete']=False
            elif fault=='foreign-resource':row['resourceSha256']='0'*64
            else:scene['currentGeneration']=2
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):state.pose_ready(value,URL,'A')

    def test_fresh_envelope_does_not_retime_original_scene_birth_history(self):
        reader=self.source.reader();first=reader.read(RUN)
        self.source.mutate=lambda value:value['source']['sceneLoads']['requests'][0].update(startedEpochMs=1700000000001)
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(first,reader.last)

    def test_foreign_stale_or_replayed_originals_fail_before_they_replace_history(self):
        for fault in ('pid','birth','sequence','clock','scenePid','sceneNonce','sceneClock','run'):
            source=Boundary();reader=source.reader();first=reader.read(RUN)
            def mutate(value):
                if fault=='pid':value['processId']=43
                elif fault=='birth':value['instance']='f'*32
                elif fault=='sequence':value['sequence']=first['sequence']
                elif fault=='clock':value['clockAfter']['monotonicMs']+=500
                elif fault=='scenePid':value['source']['sceneLoads']['processId']=43
                elif fault=='sceneNonce':value['source']['sceneLoads']['commandId']=first['requestId']
                elif fault=='sceneClock':value['source']['sceneLoads']['capturedEpochMs']=first['clockAfter']['epochMs']
                else:value['runId']='f'*32
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_historical_reads_preserve_original_clock_and_do_not_claim_live_freshness(self):
        value=self.read();self.source.clock+=10000
        query=dict(schemaVersion=1,commandId=value['requestId'],action=state.ACTION,runId=RUN)
        self.assertIs(value,state.validate(value,query,42))
        with self.assertRaises(NativeUIError):state.validate(value,query,42,self.source.epoch())

    def test_missing_native_hook_ignored_delivery_and_process_loss_do_not_resend(self):
        self.source.ignore=True
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.source.requests))
        source=Boundary();source.live=False
        with self.assertRaises(NativeUIError):source.reader().read(RUN)
        self.assertEqual([],source.requests)

    def test_closed_fixture_and_probe_dispatch_original_once_without_expected_pose(self):
        query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=state.ACTION,runId=RUN);fixture=FixtureState()
        self.assertEqual(query,fixture.set_client_command(query))
        for extra in (dict(url=URL),dict(position=[0,0,4]),dict(schemaVersion=True),dict(commandId=query['commandId']+'\n')):
            with self.assertRaises((ValueError,RuntimeError)):fixture.set_client_command(query|extra)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const original={requestId:'ios-'+'e'.repeat(32),clockBefore:{epochMs:17000},source:{avatar:{feetPosition:[9,8,7]}}};
const Test={featureIOSNavigationState:c=>{calls++;return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-navigation-state',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||files[0].v!==original||files[0].name!=='feature-ios-navigation-state.json')throw Error('original changed or resent');
applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32),position:[0,0,4]});if(calls!==1)throw Error('wanted pose admitted');
delete Test.featureIOSNavigationState;applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing source became arrived');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_transport_factory_uses_native_clock_original_not_foreign_host_utc(self):
        native=Native();clock=ClockBoundary();source=self.source;observer=native.observer()
        observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:9000
        def stamp(value):
            source.native_clock();epoch=source.epoch()
            value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query))
            native.echo=json.dumps(query).encode()
            if query['action']=='feature-native-observe':clock.send(query)
            else:source.send(query)
            return native
        def execute(session,operation,values):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            path=values['remotePath'];native.reads.append(path);prefix='@org.example.client:documents/owned-results/'
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+state.FILE))
            return base64.b64encode((clock.original() if path.endswith('/feature-native-observation.json') else source.original()).encode()).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):
            reader=observer.navigation_state();value=reader.read(RUN)
        self.assertEqual(source.last,value);self.assertEqual(['feature-native-observe',state.ACTION,'feature-native-observe'],
            [row['action'] for row in native.commands]);self.assertEqual(3,len(native.reads))
        self.assertEqual(source.last['clockAfter']['epochMs'],value['clockAfter']['epochMs'])


if __name__=='__main__':unittest.main()
