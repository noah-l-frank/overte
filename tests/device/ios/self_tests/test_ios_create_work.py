"""Actual JS instrumentation plus strict synthetic native originals; no build."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import create_work as source
from fixture.serve import FixtureState
from ios.self_tests import test_ios_create_transport as transport_tests
from self_tests.test_native_feature_observation import probe_source

RUN, EPOCH, ROOT = 'a'*32, 1700000000000, 'qrc:/scripts/'
ID = '11111111-1111-4111-8111-111111111111'
STATES = dict(edit=dict(browseCallback=False,numericEditing=False,numericDirty=False,active=False),
              bridge=dict(browsing=False,browseGeneration=0),**{'entity-list':dict(exportCallback=False)},
              voxels=dict(strokeIds=[],strokeTimer=False,strokePolls=0,editing=False,updateConnected=False,sphereId='',triggeredHand=-1,pressedHand=-1))


def packet():
    pins = json.loads(source.PIN_FILE.read_text()); roles = []
    evaluations = [dict(sequence=index+1,url=ROOT+path,submittedEpochMs=EPOCH-50,encoding=pins['encoding'],**row)
                   for index,(path,row) in enumerate(pins['sources'].items())]
    for index,(role,path) in enumerate(source.PATHS.items()):
        event = dict(sequence=index+1,capturedEpochMs=EPOCH,callerSequence=index+1,invokedEpochMs=EPOCH,
                     event='snapshot',closure='',call=0,state=deepcopy(STATES[role]))
        roles.append(dict(role=role,sourceUrl=ROOT+path,manager=dict(instance='b'*32,assigned=True,url=ROOT+source.PATHS['edit'],loadGeneration=1,assignedEpochMs=EPOCH-100),
            code=dict(submitted=True,encoding=pins['encoding'],submittedEpochMs=EPOCH-90,**pins['sources'][source.PATHS['edit']]),
            codeSources=dict(createSourcesVersion=1,complete=True,evaluations=deepcopy(evaluations)),calls=[],events=[event],ended=False,state=deepcopy(event['state']),latest=deepcopy(event)))
    return dict(iosCreateWorkVersion=1,requestId='ios-'+'c'*32,runId=RUN,instance='d'*32,sequence=1,processId=42,
        clockDomain='native-main-create-work',clockBefore=dict(epochMs=EPOCH,monotonicMs=1),clockAfter=dict(epochMs=EPOCH+1,monotonicMs=2),
        source=dict(complete=True,eventSequence=4,roles=roles,entityLifetimes=dict(createLifetimesVersion=1,complete=True,entities=[])))


class WorkBoundary(transport_tests.StateBoundary):
    def original(self):
        self.clock += .001; before = self.clocks(); self.sequence += 1; self.clock += .001
        value = packet(); value.update(requestId=self.requests[-1]['commandId'], sequence=self.sequence,
                                       clockBefore=before, clockAfter=self.clocks())
        self.last = deepcopy(value); return json.dumps(value)


class CreateWorkTests(unittest.TestCase):
    def test_pins_match_exact_utf16_units_of_all_instrumented_sources(self):
        root = Path(__file__).resolve().parents[4]/'scripts'; pins = json.loads(source.PIN_FILE.read_text())
        self.assertEqual(set(source.PATHS.values())|{source.HELPER},set(pins['sources']))
        for path,row in pins['sources'].items():
            raw = (root/path).read_bytes().decode('utf-8').encode('utf-16le')
            self.assertEqual(dict(codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()),row)

    def test_complete_live_original_can_be_quiet_but_not_an_entity_retirement_without_original_birth(self):
        value = packet(); self.assertEqual(4,source.admit(value,ROOT,quiet=True)['eventSequence'])
        with self.assertRaises(NativeUIError): source.retired(value,ROOT,[ID])
        life = dict(id=ID,bornEpochMs=EPOCH-100,destroyed=False,destructionObservedEpochMs=0,models=[dict(instance='e'*32,bornEpochMs=EPOCH-99,destroyed=False,destructionObservedEpochMs=0)])
        value['source']['entityLifetimes']['entities'] = [life]
        with self.assertRaises(NativeUIError): source.retired(value,ROOT,[ID])
        life.update(destroyed=True,destructionObservedEpochMs=EPOCH); life['models'][0].update(destroyed=True,destructionObservedEpochMs=EPOCH)
        self.assertEqual([life],source.retired(value,ROOT,[ID])['entityLifetimes']['entities'])

    def test_latest_snapshot_cannot_claim_an_event_beyond_the_actual_native_ledger(self):
        value=packet();latest=value['source']['roles'][0]['latest']
        latest.update(event='snapshot',sequence=value['source']['eventSequence']+1)
        with self.assertRaises(NativeUIError):source.admit(value,ROOT,quiet=True)

    def test_actual_closure_stack_callback_timer_source_and_old_sample_cannot_be_retired(self):
        for fault in ('browse','export','timer','editing','ended','stale','source','root','hash','partial'):
            value = packet(); row = value['source']['roles'][0]
            if fault == 'browse': row['state']['browseCallback'] = True
            elif fault == 'export': row = next(row for row in value['source']['roles'] if row['role']=='entity-list'); row['state']['exportCallback'] = True
            elif fault in ('timer','editing'): row = next(row for row in value['source']['roles'] if row['role']=='voxels'); row['state']['strokeTimer' if fault=='timer' else 'editing'] = True
            elif fault == 'ended': row.update(ended=True); row['latest']['event'] = row['events'][0]['event'] = 'ending'
            elif fault == 'stale': row['latest']['capturedEpochMs'] = row['latest']['invokedEpochMs'] = row['events'][0]['capturedEpochMs'] = row['events'][0]['invokedEpochMs'] = EPOCH-5000
            elif fault == 'source': row['sourceUrl'] = 'qrc:/scripts/system/create/forged.js'
            elif fault == 'root': row['manager']['url'] = 'qrc:/other/scripts/system/create/edit.js'
            elif fault == 'hash': row['codeSources']['evaluations'][0]['sha256'] = 'f'*64
            else: value['source']['entityLifetimes']['complete'] = False
            row['latest']['state'] = deepcopy(row['state']); row['events'][0]['state'] = deepcopy(row['state'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError): source.admit(value,ROOT,quiet=True)

    def test_prefix_rollover_and_destroyed_resource_revival_are_rejected(self):
        before = packet(); after = deepcopy(before); after.update(sequence=2,requestId='ios-'+'f'*32)
        after['clockBefore']['epochMs'] += 10; after['clockAfter']['epochMs'] += 10
        after['clockBefore']['monotonicMs'] += 10; after['clockAfter']['monotonicMs'] += 10
        query = dict(schemaVersion=1,action=source.ACTION,commandId=after['requestId'],runId=RUN)
        source.validate(after,query,42,previous=before)
        for fault in ('birth','event','code','resource'):
            altered = deepcopy(after)
            if fault=='birth': altered['instance'] = 'e'*32
            elif fault=='event': altered['source']['roles'][0]['events'] = []
            elif fault=='code': altered['source']['roles'][0]['codeSources']['evaluations'] = []
            else:
                before['source']['entityLifetimes']['entities']=[dict(id=ID,bornEpochMs=EPOCH-100,destroyed=True,destructionObservedEpochMs=EPOCH,models=[])]
                altered['source']['entityLifetimes']['entities']=[dict(id=ID,bornEpochMs=EPOCH-100,destroyed=False,destructionObservedEpochMs=0,models=[])]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError): source.validate(altered,query,42,previous=before)

    def test_actual_js_gate_entry_return_and_exception_finally_keep_original_values(self):
        root = Path(__file__).resolve().parents[4]
        program = r'''
const assert=require('node:assert/strict');
const {observer}=require('./scripts/system/create/modules/featureCreateWork.js');
global.Script={};
let untouched=0;let disabled=observer('edit','qrc:/scripts/system/create/edit.js',()=>{throw Error('read outside test')});
assert.equal(disabled.enabled,false);assert.equal(disabled.call('normal',()=>++untouched),1);
global.Test={featureIOSCreateEvent:undefined};disabled=observer('edit','url',()=>{});assert.equal(disabled.enabled,false);
const events=[];let sample,end;global.Test={featureIOSCreateEvent:v=>events.push(structuredClone(v))};
global.Script={update:{connect:f=>sample=f,disconnect:f=>assert.equal(f,sample)},scriptEnding:{connect:f=>end=f}};
let pending=false;const enabled=observer('edit','qrc:/scripts/system/create/edit.js',()=>({pending}));
const value={actual:true};assert.equal(enabled.call('browse',()=>{pending=true;return value}),value);
assert.deepEqual(events.map(v=>v.event),['snapshot','entry','returned','finally']);
assert.deepEqual(events.slice(1).map(v=>v.call),[1,1,1]);assert.equal(events.at(-1).state.pending,true);
const thrown={error:true};assert.throws(()=>enabled.call('save',()=>{throw thrown}),e=>e===thrown);
assert.deepEqual(events.slice(-2).map(v=>v.event),['entry','finally']);assert.equal(events.at(-1).call,2);
pending=false;sample();assert.equal(events.at(-1).state.pending,false);end();assert.equal(events.at(-1).event,'ending');
'''
        result = subprocess.run(['node','-e',program],cwd=root,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_fixture_probe_and_afc_factory_preserve_original_work_and_native_clock(self):
        query = dict(schemaVersion=1,commandId='ios-'+'c'*32,action=source.ACTION,runId=RUN)
        fixture = FixtureState(); self.assertEqual(query,fixture.set_client_command(query))
        for extra in ({'expected':{}},{'ids':[]},{'role':'edit'},{'schemaVersion':True}):
            with self.assertRaises((ValueError,RuntimeError)): fixture.set_client_command(query|extra)
        seam = WorkBoundary(); harness = transport_tests.CreateTransportTests(); harness.setUp()
        try:
            native,observer = harness.transport(seam,source.FILE); value = observer.create_work().read(RUN)
            self.assertEqual(seam.last,value)
            self.assertEqual(['feature-native-observe',source.ACTION,'feature-native-observe'],[row['action'] for row in native.commands])
            self.assertGreater(value['clockBefore']['epochMs'],9000)
        finally: harness.doCleanups()
        program = r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let saved=[],calls=0;const original={iosCreateWorkVersion:1,requestId:'ios-'+'c'.repeat(32),source:{complete:false,roles:[]}};
const Test={featureIOSCreateWork:c=>{calls++;return original},saveObject:(v,name)=>saved.push({v,name})};
SOURCE
const c=QUERY;
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||saved.length!==1||saved[0].v!==original||saved[0].name!=='feature-ios-create-work.json')throw Error('original replaced/replayed');
applyClientCommand({...c,commandId:'ios-'+'d'.repeat(32),expected:{}});if(calls!==1)throw Error('outcome accepted');
delete Test.featureIOSCreateWork;applyClientCommand({...c,commandId:'ios-'+'e'.repeat(32)});
if(saved.at(-1).v.status!=='unavailable')throw Error('missing observer became success');
'''.replace('SOURCE',probe_source()).replace('QUERY',json.dumps(query))
        result = subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__ == '__main__': unittest.main()
