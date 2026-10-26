"""Actual option WAL/HTTP/probe paths; Qt popup/native sources modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from fixture.serve import FixtureState
from ios.adapters import normal_input,feature_observation,snapshot_pending_choices as choices,snapshot_pending_inputs as source,snapshot_inputs
from ios.adapters.snapshot_pending_packets import PendingChoices,PendingInputs,PendingManifest,PendingSegments,PendingWorkPacket
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters.snapshot_input_owner import SnapshotInputPending,SnapshotInputOwner
from ios.adapters.snapshot_source_packet import SnapshotSourceSegments,SnapshotWorkPacket
from ios.adapters.snapshot_photos_packets import PhotosSaveSegments,PhotosSaveInputs
from ios.adapters.snapshot_share_packets import ShareNativeSegments,SnapshotShareInputs
from ios.self_tests.test_ios_normal_input import Boundary
from ios.self_tests.test_ios_feature_observation import Native as FeatureNative
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class Native(Boundary):
    def __init__(self):
        super().__init__(field='snapshot.mode.animated');self.metadata=dict(snapshotPendingChoiceVersion=1,rootId=str(uuid.uuid4()),
            qmlSource='qrc:/scripts/system/snapshot/NativeSnapshotReview.qml',comboId=str(uuid.uuid4()),option='animated',selectedMode=0,
            format='png',checked=False,popupOpen=True,inputReady=True)
        self.epoch=int(time.time()*1000);self.origin=self.epoch-1;self.events=[];self.counter=0;self.lost=False
    def stamp(self):self.epoch=max(self.epoch,int(time.time()*1000))+1;return dict(epochMs=self.epoch,monotonicMs=self.epoch-self.origin)
    def observed(self):
        value=super().observed();value.update(sampleEpochMs=int(time.time()*1000),tabletShown=True,snapshotPendingControlsVersion=1)
        row=value['controls'][0];row.update(checked=self.metadata['checked'],snapshotPendingChoice=deepcopy(self.metadata));return value
    def event(self,key,kind,details):
        self.events.append(dict(sequence=len(self.events)+1,eventId=str(uuid.uuid4()),inputId=key,kind=kind,clock=self.stamp(),details=deepcopy(details)))
    def post(self,request,timeout):
        query=json.loads(request.data);key=str(uuid.uuid4())
        if query['operation']=='edit':self.event(key,'received',dict(outerCommandId=query['commandId'],command=query['input'],controlId=self.field,root=deepcopy(self.metadata)))
        result=super().post(request,timeout)
        if query['operation']=='edit':
            self.receipt['status']['sampleEpochMs']=max(int(self.receipt['status']['sampleEpochMs']),self.epoch);self.event(key,'returned',self.receipt)
            if self.lost:raise OSError('Declared lost actual popup input return')
        return result
    def packet(self):
        self.counter+=1;before=self.stamp()
        return dict(iosNormalInputsVersion=1,profile='snapshot-pending',requestId='ios-'+uuid.uuid4().hex,runId=RUN,instance='b'*32,
            sequence=self.counter,processId=42,clockDomain='native-process-normal-inputs',clockBefore=before,clockAfter=self.stamp(),source=dict(complete=True,events=deepcopy(self.events)))


class SnapshotPendingInputTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.enterContext(self.lock.held())
        self.native=Native();self.enterContext(patch.object(normal_input,'urlopen',self.native.post));self.normal=self.native.input()
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned',generation=1,targetFingerprint='c'*64)
        self.store=PrivateFeatureState(self.root/PendingChoices.store_name('primary'));self.owner=self.open()
    def open(self):return PendingChoices(self.store,self.lock,self.binding,RUN,'primary',self.normal,lambda:True)
    def reserve(self):return self.owner.reserve(self.native.field,choices.project(self.normal.capture(),self.native.field))
    def edits(self):return [row for row in self.native.requests if row['operation']=='edit']

    def test_actual_popup_delivery_proves_only_input_and_preserves_the_observed_mode(self):
        self.reserve();self.owner.send();self.assertEqual(1,len(self.edits()));self.assertEqual(0,self.native.metadata['selectedMode'])
        self.assertTrue(self.owner.validate_original(1)['productOutcomeRequired'])

    def test_lost_actual_return_recovers_exact_original_without_repeat_or_new_clocks(self):
        self.reserve();self.native.lost=True
        with self.assertRaises(OSError):self.owner.send()
        packet=self.native.packet();original=deepcopy(packet);owner=self.open();owner.recover(packet)
        self.assertEqual(original,packet);self.assertEqual(1,len(self.edits()))
        with self.assertRaises(SnapshotInputPending):owner.send()
        history=PendingChoices.history(self.store,self.lock,self.binding,RUN,'primary');self.assertTrue(history.validate_original(1)['productOutcomeRequired'])

    def test_changed_popup_root_combo_state_or_visibility_refuses_before_dispatch(self):
        self.reserve();before=deepcopy(self.native.metadata)
        for key,value in (('rootId',str(uuid.uuid4())),('comboId',str(uuid.uuid4())),('popupOpen',False),('inputReady',False),('format','jpg')):
            self.native.metadata=dict(before,**{key:value})
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.owner.send()
            self.assertEqual([],self.edits());self.assertEqual('reserved',self.owner.current()['phase'])

    def test_foreign_source_profile_run_PID_or_positive_inner_root_cannot_supply_recovery(self):
        self.reserve();self.native.lost=True
        with self.assertRaises(OSError):self.owner.send()
        actual=self.native.packet();before=self.store.path.read_bytes()
        for fault in ('profile','run','pid','combo','control','unreturned'):
            bad=deepcopy(actual)
            if fault=='profile':bad['profile']='snapshot'
            elif fault=='run':bad['runId']='c'*32
            elif fault=='pid':bad['processId']=True
            elif fault=='combo':bad['source']['events'][0]['details']['root']['comboId']=str(uuid.uuid4())
            elif fault=='control':bad['source']['events'][0]['details']['controlId']='snapshot.capture'
            else:bad['source']['events'].pop()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner.recover(bad)
            self.assertEqual(before,self.store.path.read_bytes())
        with self.assertRaises(NativeUIError):snapshot_inputs.original(actual)
        self.owner.recover(actual)

    def test_fixture_probe_and_native_profile_are_closed_and_do_not_repeat_the_original_dispatch(self):
        self.reserve();self.owner.send();packet=self.native.packet();query=dict(schemaVersion=1,action=source.ACTION,commandId=packet['requestId'],runId=RUN)
        fixture=FixtureState();self.assertEqual(query,fixture.set_client_command(query))
        with self.assertRaises(ValueError):fixture.set_client_command(dict(query,expectedMode=1))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];const Test={featureIOSSnapshotPendingInputs:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);if(calls!==1||files.length!==1||files[0].f!=='feature-ios-snapshot-pending-inputs.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error('replayed or rewritten');
applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32),expectedMode:1});if(calls!==1)throw Error('expected result accepted');
delete Test.featureIOSSnapshotPendingInputs;applyClientCommand({...q,commandId:'ios-'+'e'.repeat(32)});if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('unavailable became success');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node'],input=program,capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)
        root=Path(__file__).resolve().parents[4];native=(root/'ios/ui/IOSNormalUiInput.cpp').read_text().split('QJsonObject NormalUiInput::request(',1)[1]
        self.assertEqual(1,native.count('result["status"]=edit(input);'));self.assertIn('pendingOriginals.returned(pendingInputId,result)',native)
        self.assertEqual('ios-snapshot',SnapshotManifest._store_prefix);self.assertEqual('pending-snapshot',PendingManifest._store_prefix)
        self.assertEqual('snapshot-pending-sources',PendingSegments.PROFILE)

    def test_actual_factory_reads_the_closed_original_AFC_path_with_independent_native_brackets(self):
        self.reserve();self.owner.send();packet=self.native.packet();native=FeatureNative();observer=native.observer();pulls=[];sent=[]
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));sent.append(query);native.echo=json.dumps(query).encode();native.value=dict(packet,requestId=query['commandId']);return native
        def execute(session,operation,arguments):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation))
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+source.FILE},arguments);pulls.append(arguments)
            return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;epochs=iter((packet['clockBefore']['epochMs']-1,packet['clockAfter']['epochMs']))
        clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=next(epochs)))
        with patch.object(feature_observation,'post_request',side_effect=post):actual=observer.snapshot_pending_inputs(clock).read(RUN)
        self.assertEqual(packet['source'],actual['source']);self.assertEqual((1,1),(len(pulls),len(sent)))


class SnapshotPendingProfileTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='42',sessionId='owned',generation=1,targetFingerprint='c'*64)

    def test_original_pending_parts_cannot_be_substituted_for_Capture_Photos_or_Share(self):
        raw=b'Original unchanged native input whitespace\n';tag=hashlib.sha256(raw).hexdigest();others=[]
        for cls in (SnapshotSourceSegments,PhotosSaveSegments,ShareNativeSegments):
            source=cls(self.root,self.binding,RUN,'primary','inputs',lambda:True,lambda _:True,monotonic=lambda:1)
            others.append((source,source.write('raw',tag,raw,1)))
        pending=PendingSegments(self.root,self.binding,RUN,'primary','inputs',lambda:True,lambda _:True,monotonic=lambda:1)
        parent=pending.write('raw',tag,raw,1);self.assertEqual(raw,pending.read(parent));self.assertEqual('pending-snapshot-inputs-parts',pending.store.namespace)
        for reader,value in others:
            with self.assertRaises(NativeUIError):reader.read(parent)
            with self.assertRaises(NativeUIError):pending.read(value)
        for subject in ('owned','primary','actor'):
            with self.assertRaises(NativeUIError):PendingSegments(self.root,self.binding,RUN,'primary',subject,lambda:True,lambda _:True,monotonic=lambda:1)

    def test_literal_pending_owner_packet_and_manifest_paths_cannot_adopt_legacy_ownership(self):
        with self.lock.held():
            store=PrivateFeatureState(self.root/PendingInputs.store_name('primary'));owner=PendingInputs(store,self.lock,self.binding,RUN,'primary',Native().input(),lambda:True);owner.save()
            PendingInputs.history(store,self.lock,self.binding,RUN,'primary')
            for cls in (SnapshotInputOwner,PhotosSaveInputs,SnapshotShareInputs):
                foreign=PrivateFeatureState(self.root/cls.store_name('primary'));foreign.write(store.read(),None)
                with self.assertRaises(NativeUIError):cls.history(foreign,self.lock,self.binding,RUN,'primary')
            with self.assertRaises(NativeUIError):owner.reserve('snapshot.save.0',{})
            for cls,path in ((PendingWorkPacket,'ios-snapshot-primary-native-work-0001.json'),(SnapshotWorkPacket,'pending-snapshot-primary-native-work-0001.json'),
                (PendingManifest,'ios-snapshot-primary-manifest-0001.json'),(SnapshotManifest,'pending-snapshot-primary-manifest-0001.json')):
                with self.assertRaises(NativeUIError):cls.history(PrivateFeatureState(self.root/path),self.lock,self.binding,RUN,'primary',1)


if __name__=='__main__':unittest.main()
