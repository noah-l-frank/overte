"""Synthetic native/UI-fence originals; no native compilation or hardware access."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_web_runtime import NativeWebRuntime,command,active_marker,released,FILE
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import probe_source

RUN='b'*32
ROOT='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
URL=ROOT+'tickets/'+'c'*32+'/graphics-marker.v1.html'
SHA=hashlib.sha256(URL.encode()).hexdigest()
BLANK=hashlib.sha256(b'about:blank').hexdigest()


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.sequence=0;self.commands=[];self.sample=None;self.pending=None
        self.okay=True;self.ignore=False;self.edit=None;self.pending_reads=0;self.partial=0;self.revoked=False;self.frozen=False
        self.saved=None;self.clock_reads=0;self.guard_calls=0
    def now(self):self.clock_reads+=1;return self.epoch if self.frozen else self.epoch+round(self.clock*1000)
    def send(self,request):
        command(request);self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1;self.started=self.now();self.saved=deepcopy(request)
        self.pending=dict(webRuntimeVersion=1,commandId=request['commandId'],runId=request['runId'],instance='a'*32,
            sequence=self.sequence,processId=31,capturedEpochMs=self.started,status='pending',source={})
        self.sample=None
    def packet(self):
        native=dict(handle='1',surface='world',creation=1,grant=3,page=2,sourceOwned=True,documentOwned=True,creationOwned=True,
            sourceSha256=SHA,documentSha256=SHA,creationSha256=SHA,sessionActive=True,authorized=True,created=True,
            pendingCreate=False,retryPending=False,suspended=False,loading=False,callbacks=0,scriptReplies=0,domPending=False)
        java=dict(handle='1',creation=1,grant=3,page=2,active=True,destroyed=False,closing=False,ownerCurrent=True,
            foreground=True,loading=False,sourceOwned=True,documentOwned=True,sourceSha256=SHA,documentSha256=SHA)
        if self.revoked:
            native.update(grant=4,page=0,sourceOwned=False,documentOwned=False,sourceSha256=BLANK,documentSha256=BLANK,
                sessionActive=False,authorized=False,created=False)
            java.update(grant=0,page=0,sourceOwned=False,documentOwned=False,sourceSha256=BLANK,documentSha256=BLANK)
        before=dict(capturedEpochMs=self.started,complete=True,knownHandles=[dict(handle='1',firstObservedEpochMs=self.epoch,sourceSha256=SHA)],views=[native])
        after=deepcopy(before);after['capturedEpochMs']=self.now()
        original=dict(javaWebRuntimeVersion=1,commandId=self.saved['commandId'],instance='d'*32,sequence=self.sequence,
            processId=31,capturedEpochMs=self.now(),complete=True,views=[java],creations=[])
        return dict(webRuntimeVersion=1,commandId=self.saved['commandId'],runId=RUN,instance='a'*32,sequence=self.sequence,
            processId=31,capturedEpochMs=self.now(),status='ready',source=dict(nativeBefore=before,java=original,nativeAfter=after))
    def original(self):
        if self.partial:self.partial-=1;return '{'
        if self.ignore:return ''
        if self.pending_reads:self.pending_reads-=1;return json.dumps(self.pending)
        if self.sample is None:
            self.sample=self.packet()
            if self.edit:self.edit(self.sample)
        return json.dumps(self.sample)
    def guard(self):self.guard_calls+=1;return self.okay
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):return NativeWebRuntime(self.send,self.original,self.now,self.guard,31,monotonic=lambda:self.clock,sleep=self.sleep)


class WebRuntimeTests(unittest.TestCase):
    def test_original_native_java_fence_and_current_document_rows_are_returned_without_expected_outcomes(self):
        source=Boundary();value=source.reader().read(RUN,ROOT)
        self.assertEqual(source.sample,value);self.assertEqual(20000,value['capturedEpochMs'])
        rows=active_marker(value,URL);self.assertEqual('1',rows['native']['handle']);self.assertEqual('1',rows['java']['handle'])
        self.assertEqual({'schemaVersion','commandId','action','runId','fixtureUrl'},set(source.commands[0]))
        self.assertNotIn('expected',json.dumps(source.commands));self.assertNotIn('released',value)
        with self.assertRaises(NativeUIError):released(value)

    def test_revoked_neutral_native_shell_and_java_document_require_actual_independent_observations(self):
        source=Boundary();reader=source.reader();reader.read(RUN,ROOT);source.revoked=True
        value=reader.read(RUN,ROOT);self.assertEqual(value['source'],released(value))
        self.assertEqual(2,value['sequence']);self.assertEqual(20000,value['capturedEpochMs'])

    def test_entity_absence_alone_cannot_hide_a_still_owned_java_webview(self):
        source=Boundary();source.revoked=True
        def live(value):value['source']['nativeBefore']['views']=[];value['source']['nativeAfter']['views']=[];value['source']['java']['views'][0].update(sourceOwned=True,documentOwned=True,sourceSha256=SHA,documentSha256=SHA)
        source.edit=live;value=source.reader().read(RUN,ROOT)
        with self.assertRaises(NativeUIError):released(value)

    def test_unfinished_creation_and_native_result_script_or_dom_callbacks_block_release(self):
        for fault in ('creation','native-create','retry','callback','script','dom'):
            source=Boundary();source.revoked=True
            def edit(value,fault=fault):
                if fault=='creation':value['source']['java']['creations']=[dict(handle='1',creation=1,sourceOwned=True,sourceSha256=SHA)]
                else:
                    row=value['source']['nativeAfter']['views'][0]
                    row[{'native-create':'pendingCreate','retry':'retryPending','callback':'callbacks','script':'scriptReplies','dom':'domPending'}[fault]]=1 if fault in ('callback','script') else True
            source.edit=edit;value=source.reader().read(RUN,ROOT)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):released(value)

    def test_false_owned_flags_cannot_hide_the_original_source_digest_or_live_authority(self):
        for side in ('native','java'):
            source=Boundary();source.revoked=True
            def edit(value,side=side):
                row=value['source']['nativeAfter']['views'][0] if side=='native' else value['source']['java']['views'][0]
                row['sourceSha256']=SHA
                if side=='native':row['sessionActive']=True
            source.edit=edit;value=source.reader().read(RUN,ROOT)
            with self.subTest(side=side),self.assertRaises(NativeUIError):released(value)

    def test_a_never_observed_empty_scope_cannot_prove_its_own_release(self):
        source=Boundary();source.revoked=True
        def empty(value):
            for key in ('nativeBefore','nativeAfter'):value['source'][key].update(knownHandles=[],views=[])
            value['source']['java']['views']=[]
        source.edit=empty;value=source.reader().read(RUN,ROOT)
        with self.assertRaises(NativeUIError):released(value)

    def test_pending_and_partial_receipts_send_once_then_preserve_the_original_completed_epoch(self):
        source=Boundary();source.partial=1;source.pending_reads=2;value=source.reader().read(RUN,ROOT)
        self.assertEqual(1,len(source.commands));self.assertEqual(20300,value['capturedEpochMs']);self.assertEqual(20000,value['source']['nativeBefore']['capturedEpochMs'])

    def test_missing_results_or_explicit_unavailability_never_become_empty_ready_inventories(self):
        source=Boundary();source.ignore=True
        with self.assertRaises(NativeUIError):source.reader().read(RUN,ROOT)
        self.assertEqual(1,len(source.commands))
        source=Boundary();source.edit=lambda value:value.update(status='unavailable',source={})
        with self.assertRaises(NativeUIError):source.reader().read(RUN,ROOT)

    def test_wrong_pid_nonce_run_java_birth_and_native_or_java_cursor_replays_are_rejected(self):
        for fault in ('pid','run','native-birth','java-birth','native-cursor','java-cursor'):
            source=Boundary();reader=source.reader();reader.read(RUN,ROOT)
            def edit(value,fault=fault):
                if fault=='pid':value['source']['java']['processId']=32
                elif fault=='run':value['runId']='f'*32
                elif fault=='native-birth':value['instance']='f'*32
                elif fault=='java-birth':value['source']['java']['instance']='f'*32
                elif fault=='native-cursor':value['sequence']=1
                else:value['source']['java']['sequence']=1
            source.edit=edit
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN,ROOT)

    def test_dropped_or_rewritten_original_handle_history_cannot_be_adopted_on_a_later_read(self):
        for fault in ('drop','rewrite'):
            source=Boundary();reader=source.reader();reader.read(RUN,ROOT)
            def edit(value,fault=fault):
                for key in ('nativeBefore','nativeAfter'):
                    snapshot=value['source'][key]
                    if fault=='drop':snapshot.update(knownHandles=[],views=[])
                    else:snapshot['knownHandles'][0]['sourceSha256']='f'*64
                value['source']['java']['views']=[]
            source.edit=edit
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN,ROOT)

    def test_incomplete_scans_missing_fields_wrong_types_and_foreign_rows_fail_closed(self):
        for fault in ('complete','missing','bool','foreign','duplicates','hash'):
            source=Boundary()
            def edit(value,fault=fault):
                native=value['source']['nativeAfter'];java=value['source']['java']
                if fault=='complete':java['complete']=False
                elif fault=='missing':native.pop('views')
                elif fault=='bool':java['views'][0]['active']=1
                elif fault=='foreign':java['views'][0].update(handle='2',sourceOwned=False,documentOwned=False)
                elif fault=='duplicates':native['views'].append(deepcopy(native['views'][0]))
                else:native['knownHandles'][0]['sourceSha256']='not-a-digest'
            source.edit=edit
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN,ROOT)

    def test_ready_header_cannot_rescue_stale_reversed_or_wide_original_snapshot_clocks(self):
        for fault in ('stale','reverse','span'):
            source=Boundary()
            def edit(value,fault=fault):
                if fault=='stale':value['source']['nativeBefore']['capturedEpochMs']-=1501
                elif fault=='reverse':value['source']['java']['capturedEpochMs']+=1
                else:value['source']['nativeBefore']['capturedEpochMs']-=1500;value['capturedEpochMs']+=1
            source.edit=edit
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN,ROOT)

    def test_frozen_native_clock_cannot_hide_a_slow_ui_fence(self):
        source=Boundary();source.frozen=True;source.pending_reads=20
        with self.assertRaises(NativeUIError):source.reader().read(RUN,ROOT)
        self.assertEqual(1,len(source.commands))

    def test_current_header_cannot_borrow_a_native_snapshot_from_before_its_request(self):
        source=Boundary()
        def old(value):
            value['source']['nativeBefore']['capturedEpochMs']=19000
            for key in ('nativeBefore','nativeAfter'):value['source'][key]['knownHandles'][0]['firstObservedEpochMs']=18000
        source.edit=old
        with self.assertRaises(NativeUIError):source.reader().read(RUN,ROOT)

    def test_native_and_java_ready_documents_must_have_the_same_actual_creation_grant_and_page(self):
        for field in ('creation','grant','page'):
            source=Boundary();source.edit=lambda value,field=field:value['source']['java']['views'][0].update({field:99})
            value=source.reader().read(RUN,ROOT)
            with self.subTest(field=field),self.assertRaises(NativeUIError):active_marker(value,URL)

    def test_clock_rollback_or_final_guard_loss_cannot_return_a_ready_snapshot(self):
        source=Boundary();reader=source.reader();clock=source.now
        def rollback():
            value=clock();return value-1 if source.clock_reads>1 else value
        reader.clock_ms=rollback
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)
        source=Boundary();reader=source.reader();read=source.original
        def lost():value=read();source.okay=False;return value
        reader.original=lost
        with self.assertRaises(NativeUIError):reader.read(RUN,ROOT)

    def test_closed_command_rejects_wanted_counts_arbitrary_paths_credentials_and_surface_input(self):
        source=Boundary();reader=source.reader();reader.read(RUN,ROOT);good=source.commands[0]
        bad=[good|change for change in (dict(expectedReleased=True),dict(callbacks=0),dict(surface='tablet'),
            dict(schemaVersion=True),dict(fixtureUrl=ROOT.replace('controlled.invalid','user:secret@controlled.invalid')),
            dict(fixtureUrl=ROOT+'../'),dict(commandId='ios-'+'a'*32))]
        for value in bad:
            with self.subTest(fields=sorted(value)),self.assertRaises((NativeUIError,ValueError)):command(value)

    def test_active_marker_requires_both_current_native_and_java_document_observations(self):
        for fault in ('native','java','pending','wrong-document','loading'):
            source=Boundary()
            def edit(value,fault=fault):
                if fault=='native':value['source']['nativeAfter']['views'][0]['authorized']=False
                elif fault=='java':value['source']['java']['views'][0]['ownerCurrent']=False
                elif fault=='pending':value['source']['nativeAfter']['views'][0]['pendingCreate']=True
                elif fault=='wrong-document':value['source']['java']['views'][0]['documentSha256']='f'*64
                else:value['source']['java']['views'][0]['loading']=True
            source.edit=edit;value=source.reader().read(RUN,ROOT)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):active_marker(value,URL)

    def test_actual_probe_preserves_originals_and_missing_hook_or_invalid_fields_do_not_pass(self):
        source=Boundary();source.reader().read(RUN,ROOT);request=source.commands[0];original=source.sample
        javascript='const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());'+probe_source()+'''
var writes=[];var mode='ready';
var Test={featureWebRuntimeObservation:function(){return mode==='ready'?packet:{};},saveObject:function(value,name){writes.push({value:value,name:name});}};
applyClientCommand(request);mode='missing';applyClientCommand(Object.assign({},request,{commandId:'e'.repeat(32)}));
applyClientCommand(Object.assign({},request,{expectedReleased:true}));
process.stdout.write(JSON.stringify(writes));
'''
        done=subprocess.run(['node','-e','const request='+json.dumps(request)+';const packet='+json.dumps(original)+';'+javascript],capture_output=True,text=True,timeout=10)
        self.assertEqual(0,done.returncode,done.stderr)
        writes=json.loads(done.stdout);self.assertEqual(2,len(writes));self.assertEqual(dict(value=original,name=FILE),writes[0])
        self.assertEqual('unavailable',writes[1]['value']['status']);self.assertNotIn('source',writes[1]['value'])
