"""Actual normal HTTP/AFC input paths; passive native event producer modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import snapshot_inputs as source,normal_input,feature_observation
from ios.adapters.snapshot_capture_controls import project
from ios.self_tests.test_ios_snapshot_capture_controls import CaptureBoundary
from ios.self_tests.test_ios_feature_observation import Native as FeatureNative
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Native(CaptureBoundary):
    def __init__(self):
        super().__init__();self.events=[];self.epoch=int(time.time()*1000);self.origin=self.epoch-1;self.counter=0;self.queries=[];self.lost=False
    def stamp(self):
        self.epoch=max(self.epoch,int(time.time()*1000))+1
        return dict(epochMs=self.epoch,monotonicMs=self.epoch-self.origin)
    def event(self,identifier,kind,details):
        self.events.append(dict(sequence=len(self.events)+1,eventId=str(uuid.uuid4()),inputId=identifier,kind=kind,clock=self.stamp(),details=deepcopy(details)))
    def post(self,request,timeout):
        query=json.loads(request.data);identifier=str(uuid.uuid4())
        if query['operation']=='edit':
            row=project(self.observed())['controls'][0]
            self.event(identifier,'received',dict(outerCommandId=query['commandId'],command=query['input'],controlId=self.field,
                root=dict(rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource'])))
        result=super().post(request,timeout)
        if query['operation']=='edit':
            self.receipt['status']['sampleEpochMs']=max(int(self.receipt['status']['sampleEpochMs']),self.epoch)
            self.event(identifier,'returned',self.receipt)
            if self.lost:raise NativeUIError('Synthetic lost return after actual native receipt')
        return result
    def send(self,query):
        self.queries.append(deepcopy(query));self.counter+=1;before=self.stamp()
        self.packet=dict(iosNormalInputsVersion=1,profile='snapshot',requestId=query['commandId'],runId=query['runId'],instance='b'*32,
            sequence=self.counter,processId=42,clockDomain='native-process-normal-inputs',clockBefore=before,clockAfter=self.stamp(),
            source=dict(complete=True,events=deepcopy(self.events)))
    def reader(self):
        return source.IOSSnapshotInputs(self.send,lambda:json.dumps(self.packet),lambda:self.stamp()['epochMs'],lambda:True,42,
            monotonic=lambda:self.clock,sleep=lambda _:None)


def completed(lost=False):
    native=Native();native.lost=lost
    with patch.object(normal_input,'urlopen',native.post):
        normal=native.input();reference=project(normal.capture());row=reference['controls'][0]
        if lost:
            with unittest.TestCase().assertRaises(NativeUIError):normal.snapshot_capture_input('snapshot.capture','activate',reference=reference)
        else:normal.snapshot_capture_input('snapshot.capture','activate',reference=reference)
    command=[entry['input'] for entry in native.requests if entry['operation']=='edit'][0]
    root=dict(rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource']);reader=native.reader();packet=reader.read(RUN)
    return native,reader,packet,command,root


class SnapshotInputTests(unittest.TestCase):
    def test_actual_normal_command_and_original_reception_join_without_inventing_capture_effects(self):
        native,_reader,packet,command,root=completed()
        result=source.delivered(packet,command,'snapshot.capture',root)
        self.assertEqual(command,result['command']);self.assertTrue(result['productOutcomeRequired'])
        self.assertEqual(1,len([query for query in native.requests if query['operation']=='edit']))
        self.assertNotIn('files',result);self.assertNotIn('captureHistory',result)

    def test_lost_actual_return_is_resolved_read_only_from_its_original_uuid_not_a_second_edit(self):
        native,_reader,packet,command,root=completed(lost=True);count=len(native.requests)
        restored=native.reader();later=restored.read(RUN);source.delivered(later,command,'snapshot.capture',root)
        self.assertEqual(count,len(native.requests));self.assertEqual(packet['source']['events'],later['source']['events'])
        self.assertEqual(1,len([query for query in native.requests if query['operation']=='edit']))

    def test_unreturned_rejected_wrong_token_root_or_control_cannot_resolve_retained_input(self):
        _native,_reader,packet,command,root=completed()
        for fault in ('unreturned','rejected','token','root','control','uuid','ack-only','overflow'):
            current=deepcopy(packet);expected=deepcopy(command);target=deepcopy(root);identifier='snapshot.capture'
            if fault=='unreturned':current['source']['events'].pop()
            elif fault=='rejected':current['source']['events'][-1]['details']['status']['performed']=False
            elif fault=='token':expected['fieldToken']=str(uuid.uuid4())
            elif fault=='root':target['rootId']=str(uuid.uuid4())
            elif fault=='control':identifier='snapshot.cancel'
            elif fault=='uuid':expected['commandId']=str(uuid.uuid4())
            elif fault=='ack-only':current=dict(performed=True)
            else:current['source']['complete']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.delivered(current,expected,identifier,target)

    def test_stale_foreign_reused_or_rewritten_originals_never_gain_freshness(self):
        native,reader,first,_command,_root=completed();second=reader.read(RUN)
        query=dict(schemaVersion=1,action=source.ACTION,commandId=second['requestId'],runId=RUN)
        for fault in ('pid','birth','nonce','clock','prefix','profile'):
            current=deepcopy(second)
            if fault=='pid':current['processId']=43
            elif fault=='birth':current['instance']='c'*32
            elif fault=='nonce':current['requestId']=first['requestId']
            elif fault=='clock':current['clockAfter']['epochMs']=1
            elif fault=='prefix':current['source']['events'][0]['details']['root']['rootId']=str(uuid.uuid4())
            else:current['profile']='avatar'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(current,query,42,previous=first)
        with self.assertRaises(NativeUIError):source.validate(second,query,42,epoch=second['clockAfter']['epochMs']+1600)

    def test_only_controlled_title_or_its_empty_restoration_can_enter_snapshot_text_history(self):
        _native,_reader,packet,command,_root=completed();text=dict(command,operation='replace',text='parity-'+RUN[:16]+'-animated')
        source.native_command(text,'snapshot.name');source.native_command(dict(text,text=''),'snapshot.name')
        for value,identifier in [('private foreign name','snapshot.name'),('parity-'+RUN[:16]+'-animated','snapshot.capture')]:
            with self.subTest(control=identifier),self.assertRaises(NativeUIError):source.native_command(dict(text,text=value),identifier)
        current=deepcopy(packet);current['source']['events'][0]['details']['command']=dict(text,text='private secret')
        current['source']['events'][0]['details']['controlId']='snapshot.name'
        with self.assertRaises(NativeUIError):source.original(current)

    def test_actual_fixture_and_probe_keep_closed_original_reads_once_per_nonce(self):
        _native,_reader,packet,_command,_root=completed();query=dict(schemaVersion=1,action=source.ACTION,commandId=packet['requestId'],runId=RUN)
        fixture=FixtureState();self.assertEqual(query,fixture.set_client_command(query))
        with self.assertRaises(ValueError):fixture.set_client_command(query|dict(expectedDelivered=True))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];const Test={featureIOSSnapshotInputs:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].f!=='feature-ios-snapshot-inputs.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error('original replay/rewritten');
applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32),expectedDelivered:true});if(calls!==2)throw Error('expected result accepted');
delete Test.featureIOSSnapshotInputs;applyClientCommand({...q,commandId:'ios-'+'e'.repeat(32)});if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('empty success');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_factory_acquires_exact_native_original_file_and_clock(self):
        _producer,_reader,packet,_command,_root=completed();native=FeatureNative();observer=native.observer();reads=[];sent=[]
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));sent.append(query);native.echo=json.dumps(query).encode()
            native.value=dict(packet,requestId=query['commandId']);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+source.FILE},arguments);reads.append(arguments)
            return base64.b64encode(json.dumps(native.value).encode()).decode()
        epochs=iter((packet['clockBefore']['epochMs']-1,packet['clockAfter']['epochMs']))
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=next(epochs)))
        with patch.object(feature_observation,'post_request',side_effect=post):actual=observer.snapshot_inputs(clock).read(RUN)
        self.assertEqual(packet['source'],actual['source']);self.assertEqual(1,len(reads));self.assertEqual(1,len(sent))

    def test_native_routing_preserves_default_avatar_and_exactly_one_existing_input_dispatch(self):
        root=Path(__file__).resolve().parents[4];header=(root/'tests/device/native/IOSNormalInputObservation.h').read_text()
        native=(root/'ios/ui/IOSNormalUiInput.cpp').read_text();request=native.split('QJsonObject NormalUiInput::request(',1)[1]
        self.assertIn('shared(Profile profile=Profile::Avatar)',header);self.assertIn('snapshot(Profile::Snapshot)',header)
        self.assertIn('if (profile!=_profile)',header);self.assertIn('if (root.isEmpty()',header)
        self.assertEqual(1,request.count('result["status"]=edit(input);'));self.assertIn('snapshotOriginals.returned(snapshotInputId,result)',request)
        self.assertIn('snapshotCaptureControlId(it.value().item)',request);self.assertIn('snapshotExportControlObservation(it.value().item)',request)
        self.assertNotIn('takeSnapshot(',header);self.assertNotIn('cancelSnapshotCapture(',header)


if __name__=='__main__':unittest.main()
