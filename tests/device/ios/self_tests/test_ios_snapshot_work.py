"""No-build SNAP pending-work, original-history and transport checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import snapshot_work as work, snapshot_exports
from ios.self_tests import test_ios_create_transport as transport_tests
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32
EPOCH=1700000000000
ROOT='qrc:/scripts/'


def packet():
    pins=json.loads(work.PIN_FILE.read_text());member=dict(instance='b'*32,assigned=True,url=ROOT+work.MAIN,loadGeneration=1,assignedEpochMs=EPOCH-100)
    code=dict(submitted=True,encoding=pins['encoding'],submittedEpochMs=EPOCH-90,**pins['sources'][work.MAIN])
    evaluations=[dict(sequence=i+1,url=ROOT+path,submittedEpochMs=EPOCH-50,encoding=pins['encoding'],**pin)
                 for i,(path,pin) in enumerate(pins['sources'].items())]
    codes=dict(snapshotSourcesVersion=1,complete=True,evaluations=evaluations)
    state=dict(nativeReview=True,revision=0,captureId='',captureCounter=0,mode='still',timerHandles=[],pendingUploads=0,overlaysHidden=False,open=True)
    event=dict(sequence=1,capturedEpochMs=EPOCH,callerSequence=1,invokedEpochMs=EPOCH,event='snapshot',closure='',call=0,state=state)
    row=dict(sourceUrl=ROOT+work.MAIN,manager=member,code=code,codeSources=codes,calls=[],events=[deepcopy(event)],ended=False,state=deepcopy(state),latest=deepcopy(event))
    native=dict(membership=deepcopy(member),code=deepcopy(code),running=True,stopping=False,finished=False,done=False,
                codeSources=deepcopy(codes),timerWork=dict(snapshotTimerWorkVersion=1,instance='e'*32,complete=True,timers=[]))
    return dict(iosSnapshotWorkVersion=1,requestId='ios-'+'c'*32,runId=RUN,instance='d'*32,sequence=1,processId=42,
        clockDomain='native-main-snapshot-work',clockBefore=dict(epochMs=EPOCH,monotonicMs=1),clockAfter=dict(epochMs=EPOCH+1,monotonicMs=2),
        source=dict(complete=True,eventSequence=1,workers=[row],timerSources=dict(complete=True,revision=1,workers=[native])))


def timer():
    return dict(timerId='f'*32,handle=1,callerChain=[ROOT+work.MAIN],createdEpochMs=EPOCH-30,singleShot=True,
                intervalMs=350,activeAtBirth=True,remainingAtBirthMs=350,fired=1,entered=0,left=0,
                depth=0,pendingDispatch=1,destroyedEpochMs=EPOCH-10,lastFiredEpochMs=EPOCH-10,
                lastCallbackEpochMs=None,lastDispatchEpochMs=None)


def query(value):return dict(schemaVersion=1,action=work.ACTION,commandId=value['requestId'],runId=RUN)


def advance(value):
    value=deepcopy(value);value.update(sequence=value['sequence']+1,requestId='ios-'+'f'*32)
    for clock in ('clockBefore','clockAfter'):
        value[clock]['epochMs']+=10;value[clock]['monotonicMs']+=10
    return value


class Boundary(transport_tests.StateBoundary):
    def original(self):
        self.clock+=.001;before=self.clocks();self.sequence+=1;self.clock+=.001
        value=packet();value.update(requestId=self.requests[-1]['commandId'],sequence=self.sequence,clockBefore=before,clockAfter=self.clocks())
        self.last=deepcopy(value);return json.dumps(value)


class SnapshotWorkTests(unittest.TestCase):
    def test_exact_submitted_utf16_source_pins_and_current_live_admission(self):
        root=Path(__file__).resolve().parents[4]/'scripts';pins=json.loads(work.PIN_FILE.read_text())
        for path,pin in pins['sources'].items():
            raw=(root/path).read_bytes().decode().encode('utf-16le')
            self.assertEqual(dict(codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()),pin)
        self.assertEqual('',work.admit(packet(),ROOT,quiet=True)['state']['captureId'])

    def test_quiet_requires_actual_timer_dispatch_return_after_single_shot_death(self):
        value=packet();native=value['source']['timerSources']['workers'][0];native['timerWork']['timers']=[timer()]
        work.admit(value,ROOT)
        with self.assertRaises(NativeUIError):work.admit(value,ROOT,quiet=True)
        native['timerWork']['timers'][0].update(entered=1,left=1,pendingDispatch=0,lastCallbackEpochMs=EPOCH-9,lastDispatchEpochMs=EPOCH-8)
        work.admit(value,ROOT,quiet=True)
        native['timerWork']['timers'][0]['destroyedEpochMs']=None
        with self.assertRaises(NativeUIError):work.admit(value,ROOT,quiet=True)

    def test_pending_closed_stale_foreign_or_incomplete_sources_cannot_qualify(self):
        for fault in ('capture','timer','upload','overlays','call','stale','hash','root','native','script','code-prefix','ended'):
            value=packet();row=value['source']['workers'][0];native=value['source']['timerSources']['workers'][0]
            if fault=='capture':row['state']['captureId']='snap_1700000000000_1'
            elif fault=='timer':row['state']['timerHandles']=[1]
            elif fault=='upload':row['state']['pendingUploads']=1
            elif fault=='overlays':row['state']['overlaysHidden']=True
            elif fault=='call':row['calls']=[dict(call=1,closure='takeSnapshot',returned=False)]
            elif fault=='stale':
                for entry in (row['events'][0],row['latest']):entry['capturedEpochMs']=entry['invokedEpochMs']=EPOCH-5000
            elif fault=='hash':row['code']['sha256']='0'*64
            elif fault=='root':row['sourceUrl']='qrc:/foreign/system/snapshot.js'
            elif fault=='native':native['timerWork']['complete']=False
            elif fault=='script':native['running']=False
            elif fault=='code-prefix':native['codeSources']['evaluations']=[]
            else:row['ended']=True;row['events'][0]['event']=row['latest']['event']='ending'
            if fault not in ('stale','ended'):
                row['events'][0]['state']=deepcopy(row['state']);row['latest']['state']=deepcopy(row['state'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):work.admit(value,ROOT,quiet=True)

    def test_prefix_cannot_reuse_nonce_borrow_clock_erase_original_or_revive_dead_timer(self):
        before=packet();after=advance(before);work.validate(after,query(after),42,previous=before)
        for fault in ('nonce','pid','birth','clock','erase','timer-birth','code'):
            old=deepcopy(before);new=deepcopy(after)
            if fault=='nonce':new['requestId']=old['requestId']
            elif fault=='pid':new['processId']=43
            elif fault=='birth':new['instance']='0'*32
            elif fault=='clock':new['clockBefore']['monotonicMs']=0
            elif fault=='erase':new['source']['workers']=[]
            elif fault=='code':new['source']['workers'][0]['codeSources']['evaluations']=[]
            else:
                t=timer();t.update(entered=1,left=1,pendingDispatch=0,lastCallbackEpochMs=EPOCH-9,lastDispatchEpochMs=EPOCH-8)
                old['source']['timerSources']['workers'][0]['timerWork']['timers']=[deepcopy(t)]
                t['destroyedEpochMs']=None;new['source']['timerSources']['workers'][0]['timerWork']['timers']=[t]
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):work.validate(new,query(new),42,previous=old)

    def test_old_unretained_heartbeat_cannot_be_rewritten_into_later_history(self):
        old=packet();row=old['source']['workers'][0];row['latest']['sequence']=3;row['latest']['callerSequence']=3
        old['source']['eventSequence']=3;work.original(old)
        new=advance(old);row=new['source']['workers'][0];forged=deepcopy(row['latest'])
        forged.update(event='entry',closure='takeSnapshot',call=1);row['events'].append(forged)
        row['latest']=deepcopy(forged);row['calls']=[dict(call=1,closure='takeSnapshot',returned=False)]
        work.original(new)
        with self.assertRaises(NativeUIError):work.validate(new,query(new),42,previous=old)

    def test_fixture_closed_requests_and_afc_factory_preserve_actual_native_clock(self):
        fixture=FixtureState();q=query(packet());self.assertEqual(q,fixture.set_client_command(q))
        self.assertEqual(q|{'action':snapshot_exports.ACTION},fixture.set_client_command(q|{'action':snapshot_exports.ACTION}))
        for extra in ({'expected':{}},{'state':{}},{'schemaVersion':True}):
            with self.assertRaises((ValueError,RuntimeError)):fixture.set_client_command(q|extra)
        seam=Boundary();harness=transport_tests.CreateTransportTests();harness.setUp()
        try:
            native,observer=harness.transport(seam,work.FILE);value=observer.snapshot_work().read(RUN)
            self.assertEqual(seam.last,value)
            self.assertEqual(['feature-native-observe',work.ACTION,'feature-native-observe'],[row['action'] for row in native.commands])
        finally:harness.doCleanups()

    def test_actual_probe_keeps_original_object_and_consumes_uncertain_read_once(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const saved=[];let calls=0;const original={iosSnapshotWorkVersion:1,requestId:'ios-'+'c'.repeat(32),actual:'untouched'};
const Test={featureIOSSnapshotWork:()=>{calls++;return original},saveObject:(v,name)=>saved.push({v,name})};
SOURCE
const c=QUERY;applyClientCommand(c);applyClientCommand(c);
if(calls!==1||saved[0].v!==original||saved[0].name!=='feature-ios-snapshot-work.json')throw Error('rewritten or resent');
applyClientCommand({...c,commandId:'ios-'+'d'.repeat(32),state:{}});if(calls!==1)throw Error('expected state accepted');
Test.featureIOSSnapshotWork=()=>{calls++;throw Error('lost read')};
const unknown={...c,commandId:'ios-'+'e'.repeat(32)};applyClientCommand(unknown);applyClientCommand(unknown);
if(calls!==2||saved.at(-1).v.status!=='unavailable')throw Error('uncertain read resent or fabricated');
'''.replace('SOURCE',probe_source()).replace('QUERY',json.dumps(query(packet())))
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_native_observation_keeps_separate_sources_and_private_compact_original_writer(self):
        root=Path(__file__).resolve().parents[4]
        manager=(root/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        native=(root/'tests/device/native/IOSSnapshotWorkObservation.h').read_text()
        writer=(root/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        save=writer[writer.index('void TestScriptingInterface::saveObject'):]
        self.assertIn('manager->featureSnapshotSources()',manager)
        self.assertIn('_featureSnapshotTimerWork->dispatchReturned(snapshotTimer)',manager)
        self.assertIn('_featureSnapshotTimerWork->callback(snapshotTimer,false)',manager)
        self.assertIn('observer->destroyed(snapshotTimer)',manager)
        self.assertIn('defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)',native)
        self.assertNotIn('Snapshot::',native);self.assertNotIn('setTimeout',native)
        compact=save.split('#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)',1)[1].split('#endif',1)[0]
        condition,body=compact.split('{',1)
        # The bounded source family shares one closed compact writer. Its
        # first filename is not an ordering or ownership requirement.
        for name in ('work','exports','captures'):
            self.assertIn('filename=="feature-ios-snapshot-'+name+'.json"',condition)
        self.assertIn('jsonData=jsonDocument.toJson(QJsonDocument::Compact)',body)
        allow=save[save.index('QString filepath = QDir::cleanPath'):save.index('QSaveFile output(filepath)')]
        self.assertIn('#if defined(OVERTE_E2E_FEATURE_TESTS)',allow)
        self.assertIn('filename == "feature-ios-snapshot-work.json"',allow)
        self.assertIn('filename == "feature-ios-snapshot-exports.json"',allow)
        self.assertIn('QFileInfo(filepath).isSymLink()',allow)


if __name__=='__main__':unittest.main()
