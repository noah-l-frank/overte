"""Whole-scope SDK originals; real Python transport/JS, no native compilation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import subprocess
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation,scene_inventory as inventory
from ios.self_tests.test_ios_navigation_state import Boundary as State,RUN
from ios.self_tests.test_ios_feature_observation import Native
from self_tests.test_native_feature_observation import Boundary as ClockBoundary,probe_source

IDS=['00000000-0000-4000-8000-'+str(index).zfill(12) for index in (1,2)]


class Boundary(State):
    def __init__(self):
        super().__init__();self.raw={IDS[0]:b'synthetic editable properties',IDS[1]:b'faraway unowned entity properties'}
        self.revision=2;self.after_revision=2;self.complete=True;self.total=None
        self.created='1700000000000000';self.edited='1700000000000001'
    def original(self):
        if self.ignore:return ''
        mutate=self.mutate;self.mutate=None
        try:clock=json.loads(super().original())
        finally:self.mutate=mutate
        rows=[dict(id=id_,hostType='domain',ready=True,createdEpochUs=self.created,lastEditedEpochUs=self.edited,
            lastEditedAfterEpochUs=self.edited,semanticBytes=len(raw),semanticSha256=hashlib.sha256(raw).hexdigest())
            for id_,raw in sorted(self.raw.items())]
        value={key:deepcopy(clock[key]) for key in ('requestId','runId','instance','sequence','processId','clockBefore','clockAfter')}
        value.update(iosSceneInventoryVersion=1,clockDomain='native-main-scene-inventory',source=dict(
            sceneLoads=clock['source']['sceneLoads'],tree=dict(entityInventoryVersion=1,profile=inventory.PROFILE,
                treeInstance='e'*32,revisionBefore=self.revision,revisionAfter=self.after_revision,
                totalEntities=len(rows) if self.total is None else self.total,complete=self.complete,entities=rows)))
        if mutate:mutate(value)
        self.last=deepcopy(value);return json.dumps(value)
    def reader(self):return inventory.IOSSceneInventory(self.send,self.original,self.native_clock,lambda:self.live,42,
        monotonic=lambda:self.clock,sleep=self.sleep)


class SceneInventoryTests(unittest.TestCase):
    def setUp(self):self.source=Boundary()
    def read(self):return self.source.reader().read(RUN)

    def test_complete_global_ids_include_unowned_objects_outside_any_view_or_radius(self):
        value=self.read();self.assertEqual(self.source.last,value)
        self.assertEqual(set(IDS),set(inventory.semantics(value)));self.assertFalse(inventory.absent(value,[IDS[1]]))
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(self.source.requests[0]))
        self.assertNotIn('radius',self.source.requests[0]);self.assertNotIn('expected',self.source.requests[0])

    def test_semantic_restore_keeps_actual_old_and_new_creation_edit_clocks_unmodified(self):
        reader=self.source.reader();before=reader.read(RUN)
        self.source.created='18446744073709551615';self.source.edited='1700000000999000';self.source.revision=self.source.after_revision=10
        after=reader.read(RUN);self.assertTrue(inventory.same_entities(before,after))
        self.assertEqual('1700000000000000',before['source']['tree']['entities'][0]['createdEpochUs'])
        self.assertEqual('18446744073709551615',after['source']['tree']['entities'][0]['createdEpochUs'])
        self.assertNotEqual(before['source']['tree']['revisionBefore'],after['source']['tree']['revisionBefore'])

    def test_changed_hidden_editable_state_or_missing_unowned_entity_is_not_restored(self):
        reader=self.source.reader();before=reader.read(RUN)
        self.source.raw[IDS[1]]=b'changed script or user data';self.source.revision=self.source.after_revision=3
        self.assertFalse(inventory.same_entities(before,reader.read(RUN)))
        del self.source.raw[IDS[1]];self.source.revision=self.source.after_revision=4
        after=reader.read(RUN);self.assertFalse(inventory.same_entities(before,after));self.assertTrue(inventory.absent(after,[IDS[1]]))

    def test_partial_over_budget_changed_during_read_or_unencoded_tree_cannot_prove_absence(self):
        for fault in ('partial','overbudget','changed','unencoded'):
            source=Boundary();source.complete=False
            if fault=='overbudget':source.raw={};source.total=513
            elif fault=='changed':source.after_revision=3
            elif fault=='unencoded':
                def mutate(value):value['source']['tree']['entities'][0].update(ready=False,semanticBytes=None,semanticSha256=None)
                source.mutate=mutate
            value=source.reader().read(RUN)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):inventory.absent(value,[IDS[1]])
            with self.assertRaises(NativeUIError):inventory.semantics(value)

    def test_duplicate_ids_count_mismatch_unsafe_uint64_or_invented_complete_flag_fail(self):
        for fault in ('duplicate','count','leadingZero','overflow','boolean','digest','falseComplete'):
            source=Boundary()
            def mutate(value):
                tree=value['source']['tree'];row=tree['entities'][0]
                if fault=='duplicate':tree['entities'][1]['id']=row['id']
                elif fault=='count':tree['totalEntities']=3
                elif fault=='leadingZero':row['createdEpochUs']='001'
                elif fault=='overflow':row['createdEpochUs']=str(2**64)
                elif fault=='boolean':row['createdEpochUs']=True
                elif fault=='digest':row['semanticSha256']='f'*63
                else:tree['revisionAfter']=tree['revisionBefore']+1
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_foreign_tree_birth_pid_counter_or_old_nested_scene_cannot_replace_history(self):
        for fault in ('birth','pid','revision','sceneBirth','sequence','clock'):
            source=Boundary();reader=source.reader();before=reader.read(RUN)
            def mutate(value):
                if fault=='birth':value['source']['tree']['treeInstance']='f'*32
                elif fault=='pid':value['processId']=43
                elif fault=='revision':value['source']['tree'].update(revisionBefore=1,revisionAfter=1)
                elif fault=='sceneBirth':value['source']['sceneLoads']['instance']='f'*32
                elif fault=='sequence':value['sequence']=before['sequence']
                else:value['source']['sceneLoads']['capturedEpochMs']=before['clockAfter']['epochMs']
            source.mutate=mutate
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(before,reader.last)

    def test_historical_native_data_stays_old_and_cross_stage_semantics_need_separate_binding(self):
        value=self.read();query=self.source.requests[-1];self.source.clock+=10000
        self.assertIs(value,inventory.validate(value,query,42))
        with self.assertRaises(NativeUIError):inventory.validate(value,query,42,self.source.epoch())
        other=Boundary();other.mutate=lambda packet:(packet.update(processId=43),packet['source']['sceneLoads'].update(processId=43))
        # Historical validation of a separately admitted process is explicit.
        other.send(dict(query,commandId='ios-'+'f'*32));new=json.loads(other.original());inventory.validate(new,other.requests[-1],43)
        self.assertTrue(inventory.same_entities(value,new))
        new['runId']='f'*32;new['source']['sceneLoads']['runId']='f'*32
        with self.assertRaises(NativeUIError):inventory.same_entities(value,new)

    def test_missing_hook_and_ignored_original_read_never_create_empty_tree_success_or_resend(self):
        self.source.ignore=True
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.source.requests))

    def test_closed_fixture_and_actual_probe_preserve_native_original_once(self):
        query=dict(schemaVersion=1,commandId='ios-'+'e'*32,action=inventory.ACTION,runId=RUN);fixture=FixtureState()
        self.assertEqual(query,fixture.set_client_command(query))
        for update in (dict(ids=IDS),dict(radius=128),dict(expectedEmpty=True),dict(schemaVersion=True)):
            with self.assertRaises((RuntimeError,ValueError)):fixture.set_client_command(query|update)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const original={requestId:'ios-'+'e'.repeat(32),source:{tree:{complete:false,totalEntities:513}}};
const Test={featureIOSSceneInventory:c=>{calls++;return original},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-scene-inventory',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);if(calls!==1||files[0].v!==original||files[0].name!=='feature-ios-scene-inventory.json')throw Error('original replaced');
applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32),radius:128});if(calls!==1)throw Error('partial scope admitted');
delete Test.featureIOSSceneInventory;applyClientCommand({...c,commandId:'ios-'+'f'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing source became empty inventory');
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_factory_uses_fixed_afc_original_and_distinct_native_clocks_not_host_utc(self):
        native=Native();clock=ClockBoundary();source=self.source;observer=native.observer()
        observer.monotonic=lambda:source.clock;observer.sleep=source.sleep;observer.epoch_ms=lambda:9000
        def stamp(value):
            source.native_clock();epoch=source.epoch();value.update(processId=42,capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        clock.mutate=stamp
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            if query['action']=='feature-native-observe':clock.send(query)
            else:source.send(query)
            return native
        def execute(session,operation,values):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            path=values['remotePath'];prefix='@org.example.client:documents/owned-results/';native.reads.append(path)
            self.assertIn(path,(prefix+'feature-native-observation.json',prefix+inventory.FILE))
            raw=clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(raw.encode()).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):
            value=observer.scene_inventory().read(RUN)
        self.assertEqual(source.last,value);self.assertEqual(['feature-native-observe',inventory.ACTION,'feature-native-observe'],[row['action'] for row in native.commands])
        self.assertEqual(3,len(native.reads));self.assertGreater(value['clockAfter']['epochMs'],9000)


if __name__=='__main__':unittest.main()
