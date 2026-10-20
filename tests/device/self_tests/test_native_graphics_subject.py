"""Synthetic native/SDK boundaries verify reader logic, never product geometry."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_graphics_subject import NativeGraphicsSubject,command,validate,LIMIT
from adapters.normal_ui import NativeUIError
from feature_journeys.graphics_fixture import subject_ids
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN='b'*32


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.commands=[];self.sample=None
        self.okay=True;self.ignored=False;self.edit=None;self.reads=0
        self.source=dict(subjectVersion=1,sceneUrl='http://controlled.invalid/scene.json',
            view=dict(position=[0,1.6,0],rotation=[0,0,0,1],mode='first person',fieldOfViewDegrees=60,
                aspectRatio=1.6,perspective=True),entities=[],absentIds=list(subject_ids(RUN).values()),
            scan=dict(center=[0,0,0],radiusMeters=128,propertyScope='graphics-spatial-v1',scannedEntities=0,unowned=[]))

    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='a'*32,
            sequence=self.sequence,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=deepcopy(self.source))
        if self.edit:self.edit(self.sample)

    def original(self):self.reads+=1;return json.dumps(self.sample) if self.sample is not None else ''
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,**options):
        return NativeGraphicsSubject(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**options)

    def add(self,name='reflector'):
        identifier=subject_ids(RUN)[name];self.source['absentIds'].remove(identifier)
        row=dict(id=identifier,name='e2e-'+RUN+'-graphics-'+name,type='Box',hostType='domain',position=[2,1.7,-4],
            rotation=[0,0,0,1],dimensions=[2,3,.01],color=[240,240,240],visible=True,mirrorMode='mirror',hazeMode=0,
            sourceUrl='',haze=dict(range=1000,color=[128,154,179],altitudeEffect=False,glare=False,backgroundBlend=0),
            lastEditedEpochUs=20000000)
        self.source['entities'].append(row);self.source['scan']['scannedEntities']+=1
        return row


class GraphicsSubjectTests(unittest.TestCase):
    def test_original_camera_and_entity_fields_remain_independent_from_any_requested_value(self):
        source=Boundary();source.add();value=source.reader().read(RUN)
        self.assertEqual(source.sample,value);self.assertEqual(6,len(value['source']['absentIds']))
        self.assertEqual([2,1.7,-4],value['source']['entities'][0]['position'])
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(source.commands[0]))
        self.assertNotIn('expected',json.dumps(source.commands));self.assertNotIn('passed',json.dumps(value))

    def test_all_seven_absences_are_measured_facts_not_a_ready_scene(self):
        source=Boundary();value=source.reader().read(RUN)
        self.assertEqual([],value['source']['entities']);self.assertEqual(7,len(value['source']['absentIds']))
        self.assertNotIn('ready',value['source'])

    def test_renamed_moved_or_hidden_owned_entities_remain_present_by_uuid(self):
        source=Boundary();row=source.add();row.update(name='renamed',position=[500,1,2],visible=False)
        source.source['scan']['scannedEntities']=0
        value=source.reader().read(RUN)
        self.assertEqual(row,value['source']['entities'][0]);self.assertNotIn(row['id'],value['source']['absentIds'])

    def test_missing_duplicate_or_conflicting_owned_inventory_cannot_prove_absence(self):
        for fault in ('missing','duplicate','conflict','unaccounted'):
            source=Boundary();row=source.add()
            if fault=='missing':source.source['absentIds'].pop()
            elif fault=='duplicate':source.source['entities'].append(deepcopy(row))
            elif fault=='conflict':source.source['absentIds'].append(row['id'])
            else:source.source['entities']=[]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_foreign_uuid_cannot_be_adopted_by_a_matching_owned_name(self):
        source=Boundary();source.add()['id']=subject_ids('c'*32)['reflector']
        with self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_only_exact_read_only_commands_and_target_scopes_are_admitted(self):
        value=dict(schemaVersion=1,commandId='a'*32,action='feature-graphics-subject-observe',runId=RUN)
        self.assertEqual(value,command(value))
        for change in (dict(expectedVisible=True),dict(entities=[]),dict(runId=True),dict(schemaVersion=True),
                dict(action='feature-graphics-subject-create'),dict(commandId='ios-'+'a'*32)):
            with self.subTest(change=change),self.assertRaises(NativeUIError):command(value|change)

    def test_stale_native_or_unordered_timestamps_never_receive_a_new_host_time(self):
        for change in (dict(capturedEpochMs=18000,requestedEpochMs=18000),dict(requestedEpochMs=20001),
                dict(requestedEpochMs=18000),dict(capturedEpochMs=20251)):
            source=Boundary();source.edit=lambda v:v.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_pid_native_birth_or_source_cursor_replacement_is_rejected(self):
        for change in (dict(processId=32),dict(instance='f'*32),dict(sequence=1)):
            source=Boundary();reader=source.reader();first=reader.read(RUN);source.edit=lambda v:v.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_malformed_projection_position_quaternion_and_visibility_do_not_supply_defaults(self):
        for change in (dict(position=[False,1,2]),dict(rotation=[0,0,0,0]),dict(fieldOfViewDegrees=0),
                dict(aspectRatio=float('nan')),dict(perspective=1),dict(expectedView=[0,0,0])):
            source=Boundary();source.source['view'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_entity_properties_are_measured_numbers_and_booleans_with_closed_shapes(self):
        for change in (dict(visible=1),dict(dimensions=[1,-1,1]),dict(color=[256,0,0]),dict(rotation=[0,0,0,0]),
                dict(lastEditedEpochUs=True),dict(hazeMode=3),dict(sourceUrl='\0'),dict(expectedMirror=True)):
            source=Boundary();source.add().update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_haze_original_properties_cannot_be_replaced_with_setting_or_pass_flags(self):
        for change in (dict(range=True),dict(color=[1,2]),dict(glare=1),dict(backgroundBlend=2),dict(hazePass=True)):
            source=Boundary();source.add()['haze'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_scan_cannot_claim_complete_global_coverage_or_duplicate_foreign_inventory(self):
        for fault in ('global','count','owned','duplicate','digest'):
            source=Boundary();scan=source.source['scan']
            row=dict(id='11111111-1111-4111-8111-111111111111',sha256='f'*64)
            scan.update(scannedEntities=1,unowned=[row])
            if fault=='global':scan['propertyScope']='all-properties-global'
            elif fault=='count':scan['scannedEntities']=0
            elif fault=='owned':row['id']=subject_ids(RUN)['floor']
            elif fault=='duplicate':scan.update(scannedEntities=2,unowned=[row,deepcopy(row)])
            else:row['sha256']='invalid'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_foreign_replies_and_ignored_read_never_replay_a_command_or_invent_inventory(self):
        for ignored in (False,True):
            source=Boundary();source.ignored=ignored;source.edit=lambda v:v.update(requestId='f'*32)
            with self.subTest(ignored=ignored),self.assertRaises(NativeUIError):source.reader().read(RUN)
            self.assertEqual(1,len(source.commands));self.assertLessEqual(source.reads,51)

    def test_partial_original_file_retries_only_reads_and_keeps_original_native_clock(self):
        source=Boundary();reader=source.reader();original=source.original
        pending=[True]
        def partial():
            if pending:pending.pop();return '{'
            return original()
        reader.original=partial;value=reader.read(RUN)
        self.assertEqual(20000,value['capturedEpochMs']);self.assertEqual(1,len(source.commands))

    def test_oversized_originals_fail_without_attempting_unbounded_decode(self):
        source=Boundary();reader=source.reader();reader.original=lambda:'x'*(LIMIT+1)
        with self.assertRaises(NativeUIError):reader.read(RUN)

    def test_process_guard_loss_and_validation_delay_are_inside_total_budget(self):
        for fault in ('guard','budget','freshness'):
            source=Boundary();reader=source.reader();actual=validate
            def delayed(*args):
                value=actual(*args)
                if fault=='guard':source.okay=False
                elif fault=='budget':source.clock+=6
                else:source.epoch+=2000
                return value
            with self.subTest(fault=fault),patch('adapters.native_graphics_subject.validate',delayed),self.assertRaises(NativeUIError):
                reader.read(RUN)
            self.assertIsNone(reader.last)

    def test_native_clock_regression_is_not_accepted_as_permitted_future_skew(self):
        for clocks in ((20000,19999),(20000,20000,19999)):
            source=Boundary();reader=source.reader();values=iter(clocks);reader.clock_ms=lambda:next(values)
            with self.subTest(clocks=clocks),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last)

    def test_ios_nonce_and_monotonic_budget_do_not_assume_equal_wall_clocks(self):
        source=Boundary();reader=source.reader(ios=True);reader.clock_ms=lambda:999999999
        value=reader.read(RUN);self.assertTrue(value['requestId'].startswith('ios-'))
        original=reader.original
        def slow():value=original();source.clock+=1.6;return value
        reader.original=slow
        with self.assertRaises(NativeUIError):reader.read(RUN)

    def test_existing_fixture_dispatch_is_closed_and_accepts_no_expected_states(self):
        fixture=FixtureState();value=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-graphics-subject-observe',runId=RUN)
        self.assertEqual(value,fixture.set_client_command(value))
        for change in (dict(expectedMirror=True),dict(entities=[]),dict(runId='wrong')):
            with self.subTest(change=change),self.assertRaises(ValueError):fixture.set_client_command(value|change)

    def test_actual_probe_preserves_original_object_deduplicates_and_reports_missing_hooks(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let files=[],calls=[];
const original={schemaVersion:1,requestId:"a".repeat(32),capturedEpochMs:17000,source:{entities:[],absentIds:[]}};
const Test={featureGraphicsSubjectObservation:c=>{calls.push(c);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-graphics-subject-observe",runId:"b".repeat(32)};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||original.capturedEpochMs!==17000)throw Error("original retimed or replayed");
if(files[0].name!=="feature-graphics-subject.json")throw Error("wrong private original file");
applyClientCommand({...request,commandId:"c".repeat(32),expectedMirror:true});
if(calls.length!==1)throw Error("expected state reached source");
delete Test.featureGraphicsSubjectObservation;applyClientCommand({...request,commandId:"d".repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error("missing native source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
