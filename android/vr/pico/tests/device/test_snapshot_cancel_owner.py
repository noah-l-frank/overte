"""Actual Pico factory/UI publishers and file scripts, explicit VM/Qt seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
import test_snapshot_still_owner as existing
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4 import snapshot_originals, snapshot_script_originals
from adapters.pico4.snapshot_review import BOOLS,STRINGS
from adapters.pico4.snapshot_cancel import validate as validate_cancel
from adapters.script_journey.history import pack,unpack
from self_tests.test_pico_snapshot_capture_owner import Producer
from self_tests.test_pico_snapshot_cancel_owner import CancelOwnerGuardTests
from self_tests.test_pico_snapshot_script_originals import caller
from adapters.normal_feature_state import PrivateFeatureState

RUN=existing.RUN


class SnapshotCancelOwnerTests(unittest.TestCase):
    def setUp(self):
        # Existing actual SDK/factory/normal UI/session/binary shell wiring.
        # The old owner is never executed; each new owner has its own publisher.
        self.h=existing.SnapshotStillOwnerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.adb,self.adapter,self.native,self.phase=self.h.adb,self.h.adapter,self.h.native,self.h.source
        self.lock=self.h.lock;self.script_sequence=0;self.events=[];self.status={};self.fast=None;self.fast_sequence=0
        self.roots_sequence=self.execution_sequence=self.work_sequence=0;self.source_values={};self.started=[];self.lost=False;self.ignore=False;self.work_fault=None
        self.producer=Producer(self.h.h.state_root/'synthetic-native-file-registry')
        self.producer.app=self.adb.app;self.producer.directory=self.adb.files
        self.producer.body.update(rows=[],captures=[],plans=[])
        self.pin=json.loads((ROOT/'tests/device/adapters/pico4/snapshot-script-pin.v1.json').read_text())
        self.origin=caller();self.origin['compilation'].update(self.pin)
        self.origin['compilation']['resourceName']='file:///packaged/scripts/system/snapshot.js'
        self.original_write=self.adb.write_debug_app_file;self.original_read=self.adb.read_debug_app_file
        self.changes=[patch.object(self.adb,'write_debug_app_file',side_effect=self.write),
            patch.object(self.adb,'read_debug_app_file',side_effect=self.read),
            patch.object(self.adb,'take',side_effect=self.take)]
        for change in self.changes:change.start();self.addCleanup(change.stop)
        self.owner=self.make();self.h.owner=self.owner

    def make(self):
        result=self.adapter._snapshot_cancel_owner(self.adb.target,RUN,self.phase,source_lock=self.lock)
        for source in (result.native,result.script,result.cancel,result.files.source,result.roots,result.execution,result.work):
            source.monotonic=lambda:self.adb.clock;source.sleep=self.adb.sleep
        return result

    def activate(self,verb,inputs=None):self.h.activate(verb,inputs)
    def clock(self):return self.adb.epoch_milliseconds(self.adb.target)
    def take(self):self.adb.captures+=1;self.adb.capturing=True

    def script(self):
        self.script_sequence+=1
        return dict(snapshotScriptOriginalsVersion=2,commandId=uuid.uuid4().hex,runId=RUN,sequence=self.script_sequence,pid=123,
            capturedEpochMs=self.clock(),activeUploads=0,history=dict(snapshotScriptHistoryVersion=1,instance='f'*32,
            complete=True,sequence=len(self.events),events=deepcopy(self.events)))

    def event(self,kind):
        origin=deepcopy(self.origin);origin['sequence']=len(self.events)+1;origin['invokedEpochMs']=self.clock()
        work=origin['snapshotWork'];work.update(capturedEpochMs=self.clock(),signalInvocations=len(self.events)+1)
        if kind=='pending':work['timers']=[dict(handle=index,active=True,singleShot=True,intervalMs=interval,remainingMs=interval)
            for index,interval in ((1,350),(2,60000))]
        self.events.append(dict(sequence=len(self.events)+1,kind=kind,id='snap_20000_1',mode='animated',revision=1,
            capturedEpochMs=self.clock(),elapsedMs=round(self.adb.clock*1000),caller=origin))

    def current(self):
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,runId=RUN,action=snapshot_originals.ACTION,operation='read')
        self.native.send(request);native=json.loads(self.native.read())
        view={key:False for key in BOOLS};view.update({key:'' for key in STRINGS})
        view.update(componentUrl='file:///packaged/scripts/system/snapshot/NativeSnapshotReview.qml',mode=1,format='png',
            capabilities=[],images=[],captureName='parity-'+RUN[:16]+'-animated',visible=True,captureSettingsLoaded=True,
            capturing=self.adb.capturing)
        return dict(capturedEpochMs=self.clock(),native=native,script=self.script(),
            review=dict(snapshotReviewObservationVersion=2,present=True,review=view))

    def fast_packet(self,request):
        self.fast_sequence+=1
        if request['operation']=='start':
            self.started.append(deepcopy(request))
            before=self.current();capture=request['request'];self.original_write(self.adb.target,'org.overte.pico',
                'files/overte-e2e/navigation-ui-command.json',json.dumps(capture))
            capture_input=deepcopy(self.adb.status);self.event('pending');pending=self.current()
            ui=self.adb.snapshot();control=next(row for row in ui['controls'] if row['id']=='snapshot.cancel')
            cancel=dict(capture,commandId=str(uuid.uuid4()),controlId='snapshot.cancel',controlToken=control['token'],sequence=ui['lastCommandSequence']+1)
            self.adb.clock+=.002;self.original_write(self.adb.target,'org.overte.pico','files/overte-e2e/navigation-ui-command.json',json.dumps(cancel))
            cancel_input=deepcopy(self.adb.status);self.event('cancelled');cancelled=self.current()
            self.fast=dict(picoSnapshotFastCancelVersion=1,instance='9'*32,job=request['jobId'],runId=RUN,phase='complete',error='',
                startedEpochMs=before['capturedEpochMs'],completedEpochMs=self.clock(),observedEpochMs=self.clock(),timerActive=False,retired=False,
                request='snap_20000_1',captureCommand=deepcopy(capture),captureInput=capture_input,cancelCommand=cancel,cancelInput=cancel_input,
                before=before,pending=pending,cancelled=cancelled,retirement={},current=cancelled)
        if self.fast is None:raise RuntimeError('Original local job not observed')
        self.fast['observedEpochMs']=self.clock();self.fast['current']=self.current()
        if request['operation']=='retire':self.fast['retired']=True;self.fast['retirement']=deepcopy(self.fast['current'])
        packet=dict(schemaVersion=1,requestId=request['commandId'],runId=RUN,instance='8'*32,sequence=self.fast_sequence,processId=123,
            requestedEpochMs=self.clock(),capturedEpochMs=self.clock(),source=deepcopy(self.fast),
            jobs=[{key:self.fast[key] for key in ('job','runId','instance','phase','timerActive','retired')}])
        validate_cancel(packet,request,123,self.clock())
        return json.dumps(dict(commandId=request['commandId'],packet=packet))

    def write(self,target,package,path,raw):
        request=json.loads(raw);action=request.get('action')
        if action==snapshot_script_originals.ACTION:
            value=self.script();value['commandId']=request['commandId'];self.source_values[snapshot_script_originals.FILE]=json.dumps(value);return
        if action in ('pico-snapshot-files-control','pico-snapshot-files-observe'):
            self.producer.epoch=self.clock();self.producer.send(request);value=json.loads(self.producer.read());value['processId']=123
            self.source_values['feature-pico-snapshot-files.json']=json.dumps(value);return
        if action=='feature-pico-snapshot-cancel':
            if self.ignore:raise RuntimeError('Explicit lost original command before delivery')
            self.status=self.fast_packet(request)
            if self.lost and request['operation']=='start':self.lost=False;raise RuntimeError('Explicit lost reply after local input')
            return
        if action=='feature-script-roots-observe':
            self.roots_sequence+=1;self.source_values['feature-script-roots.json']=json.dumps(dict(scriptRootsVersion=1,
                commandId=request['commandId'],instance='6'*32,sequence=self.roots_sequence,processId=123,
                requestedEpochMs=self.clock(),capturedEpochMs=self.clock(),source=dict(defaultScriptsUrl='file:///packaged/scripts/')));return
        if action=='feature-script-work-observe':
            self.work_sequence+=1;origin=self.origin
            activity=dict(scriptId=origin['compilation']['scriptId'],signalCallbacks=0,timerCallbacks=0,
                signalInvocations=len(self.events),timerInvocations=0,timerRegistrations=2)
            work=dict(scriptWorkVersion=2,requestId=request['commandId'],sequence=self.work_sequence,
                requestedEpochMs=self.clock(),capturedEpochMs=self.clock(),signalCallbacks=0,timerCallbacks=0,evaluating=False,
                timers=[],activity=[activity],timerEntries=0,activityEntries=1)
            if self.work_fault=='owned-timer':
                activity['timerRegistrations']=3
                work['timers']=[dict(handle=90,active=False,singleShot=True,intervalMs=350,remainingMs=-1,functionScriptId=activity['scriptId'])];work['timerEntries']=1
            value=dict(schemaVersion=1,requestId=request['commandId'],instance='5'*32,sequence=self.work_sequence,processId=123,
                requestedEpochMs=self.clock(),capturedEpochMs=self.clock(),source=dict(complete=True,revision=1,
                manager=origin['manager'],code=origin['code'],work=work,compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[origin['compilation']]),
                workers=[dict(membership=origin['manager'],running=True,stopping=False,finished=False,done=False)]))
            self.source_values['feature-script-work.json']=json.dumps(value);return
        if action=='feature-script-observe':
            self.execution_sequence+=1;origin=self.origin
            engine=dict(url=origin['manager']['url'],running=True,stopping=False,finished=False,
                required=dict(instance=origin['manager']['instance'],sequence=0,modules=[]),code=origin['code'],
                compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[origin['compilation']]))
            self.source_values['feature-script-observation.json']=json.dumps(dict(schemaVersion=1,requestId=request['commandId'],instance='7'*32,
                sequence=self.execution_sequence,processId=123,requestedEpochMs=self.clock(),capturedEpochMs=self.clock(),
                source=dict(complete=True,engines=[engine],sourceIdentityVersion=1,compiledSourceVersion=1,membershipSourceVersion=1,
                membership=dict(complete=True,revision=1,managers=[origin['manager']]))));return
        return self.original_write(target,package,path,raw)

    def read(self,target,package,path,**options):
        if path=='files/overte-e2e/snapshot-cancel-ui-status.json':return self.status
        name=path.rsplit('/',1)[-1]
        if name in self.source_values:return self.source_values[name]
        return self.original_read(target,package,path,**options)

    def opened(self):
        self.owner.prepare();self.activate('open');return self.owner.open()
    def cancelled(self):
        self.opened();self.activate('capture-cancel',dict(mode='animated',format='png'));return self.owner.start()

    def test_normal_open_plan_name_capture_cancel_pinned_vm_and_three_second_original_quiet(self):
        result=self.cancelled();self.assertEqual('cancel-observed',result['stage'])
        self.assertTrue(self.producer.body['plans']);self.assertEqual(1,len(self.started));self.assertEqual(1,self.adb.captures)
        self.assertEqual('cancel-quiet',self.owner.quiet()['stage']);result=self.owner.retire_job();self.assertEqual('partial-ready',result['stage'])
        self.assertFalse(result['fullSnapshotRecipe']);self.assertTrue(result['journalRetained']);self.assertTrue(self.owner.store.path.exists())
        self.assertTrue(self.owner.files.store.path.exists());self.assertFalse(self.producer.body['plans'][0]['sealed'])
        self.assertEqual([],list(self.adb.files.iterdir()));before=(len(self.adb.inputs),len(self.started))
        cold=self.make();self.assertEqual(result,cold.report());self.assertEqual(before,(len(self.adb.inputs),len(self.started)))

    def test_actual_lost_reply_recovery_queries_original_job_without_second_capture_or_cancel(self):
        self.opened();self.activate('capture-cancel',dict(mode='animated',format='png'));self.lost=True
        with self.assertRaises(RuntimeError):self.owner.start()
        before=len(self.adb.inputs);cold=self.make();self.assertEqual('cancel-observed',cold.reconcile()['stage'])
        self.assertEqual(before,len(self.adb.inputs));self.assertEqual(1,len(self.started))
        with self.assertRaises((ValueError,RuntimeError)):cold.start()

    def test_uncertain_undelivered_start_never_resends_or_fabricates_an_original_job(self):
        self.opened();self.activate('capture-cancel',dict(mode='animated',format='png'));self.ignore=True
        with self.assertRaises(RuntimeError):self.owner.start()
        before=len(self.adb.inputs);self.ignore=False;cold=self.make()
        with self.assertRaises((ValueError,RuntimeError)):cold.reconcile()
        self.assertEqual(before,len(self.adb.inputs));self.assertEqual([],self.started);self.assertTrue(cold.store.path.exists())

    def test_final_parent_cas_phase_change_blocks_actual_local_capture_writer(self):
        self.opened();self.activate('capture-cancel',dict(mode='animated',format='png'));write=self.owner.store.write
        def advance(value,previous):
            write(value,previous);state=unpack(value['payload'])[0]
            if state['deliveries'] and state['deliveries'][-1]['kind']=='cancel':self.activate('close')
        with patch.object(self.owner.store,'write',side_effect=advance),self.assertRaises((ValueError,RuntimeError)):self.owner.start()
        self.assertEqual([],self.started);self.assertEqual(0,self.adb.captures);self.assertTrue(self.owner.store.path.exists())

    def test_slow_final_cas_with_frozen_device_clock_blocks_actual_local_capture(self):
        self.opened();self.activate('capture-cancel',dict(mode='animated',format='png'));write=self.owner.store.write
        def slow(value,previous):
            write(value,previous);state=unpack(value['payload'])[0]
            if state['deliveries'] and state['deliveries'][-1]['kind']=='cancel':self.adb.clock+=2
        with patch.object(self.owner.store,'write',side_effect=slow),patch.object(self.adb,'epoch_milliseconds',return_value=20000),self.assertRaises((ValueError,RuntimeError)):self.owner.start()
        self.assertEqual([],self.started);self.assertEqual(0,self.adb.captures)

    def test_late_unowned_file_prevents_quiet_and_cold_archived_clock_gap_is_rejected(self):
        self.cancelled();self.owner.quiet();disk=self.owner.store.read();state=unpack(disk['payload'])[0]
        for fault in ('clock-gap','retained-work'):
            state=unpack(disk['payload'])[0]
            if fault=='clock-gap':state['frames'][state['quiet'][0]['last']]['hostMonotonic']+=2
            else:
                row=state['frames'][state['quiet'][0]['last']]['work']['source']['work']
                row['timers']=[dict(handle=90,active=False,singleShot=True,intervalMs=350,remainingMs=-1,functionScriptId=2)];row['timerEntries']=1
            changed=deepcopy(disk);changed['payload']=pack([state]);self.owner.store.write(changed,disk)
            with self.subTest(fault=fault),self.assertRaises((ValueError,RuntimeError)):self.make()
            self.owner.store.write(disk,changed)
        late=self.adb.files/(self.owner.prefix+'-late.png');late.write_bytes(b'late original output')
        with self.assertRaises((ValueError,RuntimeError)):self.owner.files.inventory()
        self.assertEqual(b'late original output',late.read_bytes());self.assertTrue(self.owner.files.store.path.exists())

    def test_fresh_original_retained_timer_cannot_hide_behind_historical_cancelled_timer_absence(self):
        self.cancelled();self.assertEqual([],self.owner.cancel_value(self.owner.state)['source']['cancelled']['script']['history']['events'][-1]['caller']['snapshotWork']['timers'])
        self.work_fault='owned-timer'
        with self.assertRaises((ValueError,RuntimeError)):self.owner.quiet()
        self.assertEqual('quiet-issued',self.owner.state['stage']);self.assertTrue(self.owner.store.path.exists())
        self.assertTrue(self.owner.state['frames'][-1]['work']['source']['work']['timers']);self.assertEqual(1,self.adb.captures)

    def test_foreign_vm_or_reviewed_source_cannot_qualify_capture_cancel(self):
        self.opened();self.activate('capture-cancel',dict(mode='animated',format='png'));self.origin['compilation']['sha256']='e'*64
        with self.assertRaises((ValueError,RuntimeError)):self.owner.start()
        self.assertEqual(1,len(self.started));self.assertEqual('cancel-issued',self.owner.state['stage'])

    def test_orphan_original_file_journal_blocks_base_cleanup_and_public_input(self):
        self.opened();path=self.owner.files.store.path
        # Even a standalone unresolved original journal is an obligation.
        PrivateFeatureState(path).write(dict(unresolved=True),None);self.owner.store.path.unlink()
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.invoke(self.adb.target,'snapshot.open',{})
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup(self.adb.target)
        self.assertTrue(path.exists());self.assertFalse(self.adb.running)

    def test_original_armed_source_recovers_after_lost_reply_without_second_arm(self):
        capture=self.owner.native.capture
        def lost(*args,**kwargs):capture(*args,**kwargs);raise RuntimeError('Original arm reply lost')
        with patch.object(self.owner.native,'capture',side_effect=lost),self.assertRaises(RuntimeError):self.owner.prepare()
        self.assertEqual('arm-issued',self.owner.state['stage']);cold=self.make()
        self.assertEqual('prepared',cold.reconcile()['stage'])
        self.assertEqual(1,sum(row.get('operation')=='arm' for row in self.native.commands));self.assertFalse(self.adb.inputs)

    def test_original_completed_open_recovers_readonly_after_child_return_loss(self):
        self.owner.prepare();self.activate('open');opened=self.owner.snapshot.open
        def lost():opened();raise RuntimeError('Original open return lost')
        with patch.object(self.owner.snapshot,'open',side_effect=lost),self.assertRaises(RuntimeError):self.owner.open()
        before=(len(self.adb.inputs),len(self.h.transport.envelopes));cold=self.make()
        self.assertEqual('opened',cold.reconcile()['stage']);self.assertEqual(before,(len(self.adb.inputs),len(self.h.transport.envelopes)))

    def test_last_original_guard_phase_change_refuses_input_and_controller_publish_is_host_only(self):
        self.owner.prepare();guard=self.owner.native.guard
        def advance():guard();self.activate('open');return True
        with self.lock.held(),patch.object(self.owner.native,'guard',side_effect=advance),self.assertRaises((ValueError,RuntimeError)):self.owner.fence()
        self.h.transport.delay=2
        with self.assertRaises((ValueError,RuntimeError)):self.owner.open()
        self.assertFalse(self.h.transport.envelopes);self.assertFalse(self.adb.inputs);self.assertEqual('open-issued',self.owner.state['stage'])


if __name__=='__main__':unittest.main()
