"""Actual E2E marker-header refresh with explicit tree endpoints and Qt math.

This is a prepared host compiler/source contract, not an Android client build
or renderer/device acceptance. Original resource and input DTOs are unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

import test_create_native_fixture as native
import test_create_marker as marker
import test_snapshots_feature as feature_tests
from adapters.normal_ui import NativeUIError
from overte_phone_create_marker import current_input, input_command, ready


MAIN = r'''#include "tests/device/native/PhoneCreateFixture.h"
#include <iostream>
#include <thread>
int main(int argc,char**argv){QCoreApplication app(argc,argv);overte::e2e::PhoneCreateFixture fixture;ViewFrustum view;
 QString run(32,'a');QVariantList rejected;
 QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'b')},{"action","phone-create-fixture-input"},{"operation","prepare"},
 {"runId",run},{"ticket",QString(32,'c')},{"fixtureUrl","http://controlled.invalid/feature-fixture/v1/runs/"+run+"/"},
 {"imageExtent",QVariantList{1000,750}},{"markerRoi",QVariantList{20,20,180,60}}};
 auto send=[&](const QVariantMap& c){return fixture.input(c,view,"first person look at",{0,0,0},1,0);};
 send(command);auto before=fixture.observe(run);auto tree=DependencyManager::get<EntityScriptingInterface>()->tree;
 QUuid marker,other;for(auto it=tree->objects.begin();it!=tree->objects.end();++it){if(it.value()->properties.type==EntityTypes::Web)marker=it.key();else other=it.key();}
 auto original=tree->objects[marker];const auto originalUrl=original->properties.url;
 QVariantMap refresh{{"schemaVersion",1},{"commandId",QString(32,'d')},{"action","phone-create-fixture-input"},{"operation","refresh"},
 {"runId",run},{"fixtureInstance",before.value("fixtureInstance")},{"ticket",QString(32,'e')}};
 auto reject=[&](QVariantMap c){const auto updates=tree->updates;auto answer=send(c);rejected.append(answer.isEmpty()&&updates==tree->updates&&original->properties.url==originalUrl);};
 auto c=refresh;c["fixtureInstance"]=QString(32,'f');reject(c);c=refresh;c["runId"]=QString(32,'f');reject(c);
 c=refresh;c["ticket"]=QString(32,'c');reject(c);c=refresh;c["commandId"]=QString(32,'b');reject(c);
 c=refresh;c["fixtureUrl"]="http://foreign.invalid/";reject(c);
 original->properties.locked=true;reject(refresh);original->properties.locked=false;
 original->child=true;reject(refresh);original->child=false;
 original->local=false;reject(refresh);original->local=true;
 original->clone=QUuid::createUuid();reject(refresh);original->clone={};
 auto replacement=std::make_shared<EntityItem>();replacement->properties=original->properties;tree->objects[marker]=replacement;reject(refresh);tree->objects[marker]=original;
 auto prior=tree->objects.take(other);reject(refresh);tree->objects[other]=prior;
 original->properties.url="http://foreign.invalid/";const auto changed=send(refresh);rejected.append(changed.isEmpty()&&tree->updates==0);original->properties.url=originalUrl;
 tree->refuseUpdate=true;reject(refresh);tree->refuseUpdate=false;
 QVariantMap offThread;std::thread worker([&]{offThread=send(refresh);});worker.join();rejected.append(offThread.isEmpty());
 auto firstReceipt=send(refresh);auto first=fixture.observe(run);auto repeated=send(refresh);const int firstUpdates=tree->updates;
 c=refresh;c["ticket"]=QString(32,'f');const auto changedRepeat=send(c);
 c=refresh;c["commandId"]=QString(32,'1');c["ticket"]=QString(32,'2');auto secondReceipt=send(c);auto second=fixture.observe(run);
 auto replay=send(refresh);const int secondUpdates=tree->updates;
 QVariantMap release{{"schemaVersion",1},{"commandId",QString(32,'3')},{"action","phone-create-fixture-input"},{"operation","release"},
 {"runId",run},{"fixtureInstance",before.value("fixtureInstance")}};
 send(release);original.reset();replacement.reset();prior.reset();auto drained=fixture.observe(run);
 c=refresh;c["commandId"]=QString(32,'4');auto afterRelease=send(c);
 command["commandId"]=QString(32,'5');auto oldRun=send(command);
 command["runId"]=QString(32,'6');command["fixtureUrl"]="http://controlled.invalid/feature-fixture/v1/runs/"+QString(32,'6')+"/";send(command);auto next=fixture.observe(QString(32,'6'));
 std::cout<<QJsonDocument::fromVariant(QVariantMap{{"rejected",rejected},{"before",before},{"first",first},{"second",second},
 {"firstReceipt",firstReceipt},{"repeated",repeated},{"firstUpdates",firstUpdates},{"changedRepeat",changedRepeat},
 {"secondReceipt",secondReceipt},{"replay",replay},{"secondUpdates",secondUpdates},{"drained",drained},{"afterRelease",afterRelease},{"oldRun",oldRun},{"next",next}}).toJson().toStdString();}
'''


class NativeMarkerRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build = native.ROOT / 'build/create-marker-refresh-contract'
        build.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='check-', dir=build) as temporary:
            stage = Path(temporary)
            (stage / 'synthetic.h').write_text(native.STUB)
            for name in ('EntityScriptingInterface','EntityTree','EntityItem','EntityItemProperties','ViewFrustum'):
                (stage / (name + '.h')).write_text('#include "synthetic.h"\n')
            (stage / 'main.cpp').write_text(MAIN)
            flags = subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui'],text=True).split()
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
                '-I'+str(stage),'-I'+str(native.ROOT),str(stage/'main.cpp'),'-o',str(stage/'check'),*flags],check=True,timeout=60)
            cls.actual = json.loads(subprocess.check_output([str(stage/'check')],text=True,timeout=5))

    def test_actual_refresh_preserves_original_birth_view_ids_and_changes_only_owned_url(self):
        value = self.actual
        self.assertEqual(2, value['before']['phoneCreateFixtureVersion'])
        for field in ('fixtureInstance','runId','createdEpochMs','originalInput','originalView','objects'):
            self.assertEqual(value['before'][field], value['second'][field])
        for before, after in zip(value['before']['entities'], value['second']['entities']):
            delta = {key for key in before if before[key] != after[key]}
            self.assertEqual({'sourceUrl','lastEditedEpochUs'} if before['role']=='marker' else set(), delta)
        self.assertEqual(3, value['second']['phoneCreateFixtureVersion'])
        self.assertEqual(2, len(value['second']['refreshes']))
        self.assertEqual(value['first']['refreshes'], value['second']['refreshes'][:1])
        self.assertEqual(value['second']['refreshes'][-1]['input'], value['second']['lastRefreshInput'])
        self.assertEqual(value['firstReceipt'], value['repeated'])
        self.assertEqual((1,2), (value['firstUpdates'],value['secondUpdates']))

    def test_actual_foreign_replaced_missing_locked_child_wrong_thread_and_replays_are_refused(self):
        value = self.actual
        self.assertEqual(14, len(value['rejected']))
        self.assertTrue(all(value['rejected']))
        for key in ('changedRepeat','replay','afterRelease','oldRun'):
            self.assertEqual({}, value[key])
        self.assertEqual('drained', value['drained']['phase'])
        self.assertEqual(value['second']['refreshes'], value['drained']['refreshes'])
        self.assertEqual(2, value['next']['phoneCreateFixtureVersion'])
        self.assertNotIn('refreshes', value['next'])


def refreshed(boundary, command_id='1'*32, ticket='2'*32):
    source = boundary.fixture
    request = dict(schemaVersion=1,commandId=command_id,action='phone-create-fixture-input',operation='refresh',
        runId=source['runId'],fixtureInstance=source['fixtureInstance'],ticket=ticket)
    source['phoneCreateFixtureVersion']=3
    source.setdefault('refreshes',[]).append(dict(input=request,editedEpochMs=boundary.epoch))
    source['lastRefreshInput']=deepcopy(request)
    row=source['entities'][-1]
    row['sourceUrl']=source['originalInput']['fixtureUrl']+'tickets/'+ticket+'/graphics-marker.v1.html'
    row['lastEditedEpochUs']=boundary.epoch*1000
    return request


class MarkerRefreshReaderTests(unittest.TestCase):
    def test_v2_to_original_v3_refresh_requires_unchanged_creation_and_actual_new_url(self):
        b=marker.Boundary();reader=b.reader();old=reader.read(marker.RUN)
        request=refreshed(b);new=reader.read(marker.RUN);avatar=marker.AvatarBoundary.reader(b).read()
        self.assertEqual(request,current_input(new['source']))
        self.assertEqual(old['source']['originalInput'],new['source']['originalInput'])
        self.assertEqual(new['source']['entities'],ready(new,avatar))
        b.fixture['entities'][-1]['sourceUrl']=old['source']['entities'][-1]['sourceUrl']
        with self.assertRaises(NativeUIError):ready(reader.read(marker.RUN),avatar)

    def test_historical_refresh_prefix_birth_and_input_bindings_cannot_roll_back(self):
        for fault in ('drop','mutate','birth','instance','run','duplicate-ticket','last','early','command-extra'):
            with self.subTest(fault=fault):
                b=marker.Boundary();reader=b.reader();reader.read(marker.RUN);refreshed(b)
                first=reader.read(marker.RUN);refreshed(b,'3'*32,'4'*32);second=reader.read(marker.RUN)
                if fault=='drop':b.fixture['refreshes'].pop(0)
                elif fault=='mutate':b.fixture['refreshes'][0]['editedEpochMs']-=1
                elif fault=='birth':b.fixture['originalInput']['ticket']='5'*32
                elif fault=='instance':b.fixture['refreshes'][-1]['input']['fixtureInstance']='5'*32
                elif fault=='run':b.fixture['refreshes'][-1]['input']['runId']='5'*32
                elif fault=='duplicate-ticket':b.fixture['refreshes'][-1]['input']['ticket']='2'*32
                elif fault=='last':b.fixture['lastRefreshInput']=deepcopy(first['source']['lastRefreshInput'])
                elif fault=='early':b.fixture['refreshes'][-1]['editedEpochMs']=1
                else:b.fixture['refreshes'][-1]['input']['expectedReady']=True
                with self.assertRaises(NativeUIError):reader.read(marker.RUN)
                self.assertEqual(second,reader.last)

    def test_refresh_closed_command_rejects_external_root_geometry_and_non_owner_fields(self):
        request=refreshed(marker.Boundary())
        self.assertEqual(request,input_command(request))
        for extra in ({'fixtureUrl':marker.ROOT},{'imageExtent':[1000,750]},{'expectedReady':True},{'fixtureInstance':'bad'},{'ticket':True}):
            with self.subTest(extra=extra),self.assertRaises((NativeUIError,ValueError)):
                input_command(request|extra)

    def test_original_refresh_can_precede_release_between_reads_but_cannot_follow_observed_drain(self):
        b=marker.Boundary();reader=b.reader();reader.read(marker.RUN)
        refreshed(b);b.drain();last=reader.read(marker.RUN)
        self.assertEqual('drained',last['source']['phase']);self.assertEqual(1,len(last['source']['refreshes']))
        b.fixture['refreshes'].append(dict(input=dict(b.fixture['lastRefreshInput'],commandId='5'*32,ticket='6'*32),editedEpochMs=b.epoch))
        b.fixture['lastRefreshInput']=deepcopy(b.fixture['refreshes'][-1]['input'])
        with self.assertRaises(NativeUIError):reader.read(marker.RUN)
        self.assertEqual(last,reader.last)

    def test_actual_probe_admits_only_closed_refresh_and_preserves_original_receipt(self):
        from self_tests.test_native_feature_observation import probe_source
        request=refreshed(marker.Boundary())
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=[],files=[];const receipt={phoneCreateFixtureInputVersion:1,recorded:true};
const Test={phoneCreateFixtureInput:c=>{calls.push(c);receipt.commandId=c.commandId;return receipt;},saveObject:(v,n)=>files.push({v,n})};
SOURCE
const request=REQUEST;
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files[0].v!==receipt||files[0].n!=="phone-create-fixture-input.json")throw Error("refresh receipt replaced/repeated");
for(const extra of [{expectedReady:true},{fixtureUrl:"http://foreign.invalid/"},{imageExtent:[1000,750]},{fixtureInstance:"bad"},{ticket:true}]) {
 applyAndroidControlCommand({...request,commandId:"f".repeat(32),...extra});
}
if(calls.length!==1)throw Error("open/foreign refresh admitted");
'''.replace('SOURCE',probe_source()).replace('REQUEST',json.dumps(request))
        answer=subprocess.run(['node','-e',program],text=True,capture_output=True,timeout=5)
        self.assertEqual(0,answer.returncode,answer.stderr)


class SnapshotRefreshRecoveryTests(unittest.TestCase):
    setUp=feature_tests.SnapshotsFeatureTests.setUp
    feature=feature_tests.SnapshotsFeatureTests.feature
    failed_preflight=feature_tests.SnapshotsFeatureTests.failed_preflight

    def owner(self):
        self.failed_preflight();self.adapter=feature_tests.NoExportAdapter(self.root)
        self.marker=marker.Boundary();f=self.feature()
        self.marker.fixture=json.loads(json.dumps(self.marker.fixture).replace(marker.RUN,self.run))
        self.marker.fixture['originalInput']['fixtureUrl']=f.fixture_url
        self.marker.fixture['entities'][-1]['sourceUrl']=f.fixture_url+'tickets/'+'c'*32+'/graphics-marker.v1.html'
        self.writes=[];self.lost=False;self.ignored=False
        def write(_selector,request,**kwargs):
            f.lock.assert_held();self.assertTrue(kwargs['intent'](request,f.binding));self.writes.append(deepcopy(request))
            if not self.ignored:
                actual=refreshed(self.marker,request['commandId'],request['ticket']);self.assertEqual(request,actual)
            if self.lost:raise NativeUIError('Explicit lost original refresh return')
            return {'performed':True}
        self.adapter._create_fixture_input=write
        self.adapter._create_fixture_observer=lambda *args,**kwargs:self.marker.reader()
        with f.lock.held():
            f.load();group,_=self.adapter._snapshot_measurements(None).read(self.run)
            native_packet=self.adapter._native_feature_observer(None,read_only=True).read(0,require_account=True)
            avatar=self.adapter._avatar_render_observer(None,read_only=True).read()
            f.state['original']=dict(avatar=dict(source=dict(cameraMode=avatar['source']['cameraMode'])));f.save()
            f.archive_input(dict(snapshotsBaseline=dict(group=group,native=native_packet,avatar=avatar,documentResolution=None)))
            source=self.marker.reader().read(self.run)
            call=dict(contractVersion=feature_tests.VERSION,runId=self.run,fixtureUrl=f.fixture_url,ticket=uuid.uuid4().hex,verb='background-resume',inputs={})
            f.state.update(partial=False,phase='acting',marker=deepcopy(source['source']['originalInput']),markerSource=source,
                current=dict(call=call,phase='issuing',pending=None));f.save()
        return f

    def test_snapshot_refresh_preserves_creation_and_archives_actual_input_effect(self):
        f=self.owner();creation=deepcopy(f.state['marker'])
        with f.lock.held():
            f.load();f.refresh_marker();self.assertIsNone(f.state['current']['pending'])
            self.assertEqual(creation,f.state['marker'])
            self.assertEqual(creation,f.state['markerSource']['source']['originalInput'])
            originals=f.input_originals();last=originals[-1]
            self.assertEqual(self.writes[0],last['markerRefreshOriginal']['source']['lastRefreshInput'])
            self.assertEqual(f.state['current']['call']['ticket'],current_input(f.state['markerSource']['source'])['ticket'])
        self.assertEqual(['refresh'],[row['operation'] for row in self.writes])

    def test_lost_refresh_return_reconstructs_original_effect_without_another_write(self):
        f=self.owner();self.lost=True
        with f.lock.held(),self.assertRaises(NativeUIError):f.load();f.refresh_marker()
        pending=deepcopy(f.state['current']['pending']);self.assertEqual('marker-refresh',pending['kind'])
        another=self.feature()
        with another.lock.held():
            another.load();another.recover_handoff_input();self.assertIsNone(another.state['current']['pending'])
            self.assertEqual(pending['request'],another.state['markerSource']['source']['lastRefreshInput'])
        self.assertEqual([pending['request']],self.writes)

    def test_missing_actual_refresh_effect_preserves_pending_and_cannot_retry_or_prepare(self):
        f=self.owner();self.lost=True;self.ignored=True
        with f.lock.held(),self.assertRaises(NativeUIError):f.load();f.refresh_marker()
        header=f.store.read();another=self.feature()
        with another.lock.held():
            another.load()
            with self.assertRaises(NativeUIError):another.recover_handoff_input()
        self.assertEqual(header,f.store.read());self.assertEqual(1,len(self.writes))

    def test_changed_durable_refresh_request_is_refused_before_source_or_write(self):
        f=self.owner();self.lost=True
        with f.lock.held(),self.assertRaises(NativeUIError):f.load();f.refresh_marker()
        header=f.store.read();changed=deepcopy(header);rows=feature_tests.unpack(changed['payload'])
        rows[0]['current']['pending']['request']['commandId']='5'*32;changed['payload']=feature_tests.pack(rows)
        f.store.write(changed,header);another=self.feature()
        with another.lock.held(),self.assertRaises(NativeUIError):another.load()
        self.assertEqual(changed,f.store.read());self.assertEqual(1,len(self.writes))

    def test_native_refresh_history_without_matching_current_object_url_remains_red(self):
        f=self.owner();self.lost=True
        with f.lock.held(),self.assertRaises(NativeUIError):f.load();f.refresh_marker()
        self.marker.fixture['entities'][-1]['sourceUrl']=self.marker.fixture['originalInput']['fixtureUrl']+'tickets/'+'c'*32+'/graphics-marker.v1.html'
        header=f.store.read();another=self.feature()
        with another.lock.held():
            another.load()
            with self.assertRaises(NativeUIError):another.recover_handoff_input()
        self.assertEqual(header,f.store.read());self.assertEqual(1,len(self.writes))

    def test_archived_refresh_original_before_pending_clear_is_rechecked_without_rewrite(self):
        f=self.owner();save=f.save;issued=[False]
        def lost_clear():
            if f.state['current']['pending'] is not None:issued[0]=True
            elif issued[0]:raise NativeUIError('Explicit interrupted durable pending clear')
            save()
        f.save=lost_clear
        with f.lock.held(),self.assertRaises(NativeUIError):f.load();f.refresh_marker()
        self.assertEqual('marker-refresh',feature_tests.unpack(f.store.read()['payload'])[0]['current']['pending']['kind'])
        another=self.feature()
        with another.lock.held():
            another.load();another.recover_handoff_input();self.assertIsNone(another.state['current']['pending'])
            self.assertGreaterEqual(len([row for row in another.input_originals() if 'markerRefreshOriginal' in row]),2)
        self.assertEqual(1,len(self.writes))


if __name__=='__main__':unittest.main()
