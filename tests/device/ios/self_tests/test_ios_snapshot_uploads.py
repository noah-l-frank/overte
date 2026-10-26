"""Typed original upload facts over real weak lifetimes and body descriptors."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
import subprocess
import time
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import snapshot_uploads as source
from ios.self_tests.snapshot_upload_domain import UploadDomain,RUN
from ios.self_tests import test_ios_create_transport as transport_tests
from self_tests.test_native_feature_observation import probe_source


class SnapshotUploadsTests(unittest.TestCase):
    def test_actual_afc_factory_keeps_original_upload_file_and_query_with_independent_native_clock(self):
        domain=UploadDomain(self);domain.complete()
        class Boundary(transport_tests.StateBoundary):
            def original(inner):
                value=domain.observe();value.update(requestId=inner.requests[-1]['commandId'],runId=inner.requests[-1]['runId'])
                inner.last=deepcopy(value);return json.dumps(value)
        boundary=Boundary();harness=transport_tests.CreateTransportTests();harness.setUp()
        try:
            native,observer=harness.transport(boundary,source.FILE);observer.monotonic=time.monotonic
            clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=domain.now()))
            reader=observer.snapshot_uploads(clock_source=clock);value=reader.read(RUN)
            self.assertEqual(boundary.last,value);self.assertEqual([source.ACTION],[row['action'] for row in native.commands])
            self.assertEqual(1,reader.acquisition['iosSnapshotUploadsAcquisitionVersion'])
            self.assertTrue(native.reads[-1].endswith('/'+source.FILE));self.assertEqual('success',source.decision(value,domain.owner)['status'])
        finally:harness.doCleanups()
    def test_genuine_other_run_upload_facts_do_not_become_this_run_decision_or_closure(self):
        domain=UploadDomain(self);domain.complete();value=domain.observe();value['runId']='a'*32;source.original(value)
        for qualify in (source.decision,source.local_objects_gone):
            with self.assertRaises(NativeUIError):qualify(value,domain.owner)
    def test_actual_native_decision_and_closed_local_objects_still_require_original_backend_and_transport(self):
        domain=UploadDomain(self);domain.complete();value=domain.observe();source.original(value)
        result=source.decision(value,domain.owner);self.assertEqual('success',result['status']);self.assertTrue(result['authenticatedBackendOriginalRequired']);self.assertTrue(result['nativeSignalDeliveryRequired'])
        self.assertEqual(domain.path.read_bytes(),domain.received.getvalue());closed=source.local_objects_gone(value,domain.owner)
        self.assertTrue(closed['bodyFDAbsent']);self.assertTrue(closed['transportProcessProofRequired']);self.assertEqual(2,domain.send_count)
    def test_weak_death_cannot_hide_held_body_FD_or_reused_numeric_descriptor(self):
        domain=UploadDomain(self);domain.complete(close_fd=False);held=domain.observe();source.original(held)
        with self.assertRaises(NativeUIError):source.local_objects_gone(held,domain.owner)
        domain.close_fd(domain.fd);foreign=domain.root/'foreign';foreign.write_bytes(b'foreign original descriptor owner')
        opened=os.open(foreign,os.O_RDONLY|os.O_NOFOLLOW)
        if opened!=domain.fd:os.dup2(opened,domain.fd);os.close(opened)
        domain.open_fds.add(domain.fd);changed=domain.observe();source.validate(changed,dict(schemaVersion=1,commandId=changed['requestId'],action=source.ACTION,runId=RUN),42,previous=held)
        file=next(row for row in changed['source']['resources'] if row['kind']=='file');self.assertEqual('changed',file['fdAfter']['state'])
        with self.assertRaises(NativeUIError):source.local_objects_gone(changed,domain.owner)
    def test_expired_callback_stack_without_actual_left_observation_is_not_departure(self):
        domain=UploadDomain(self);domain.complete(leave=False);value=domain.observe();source.original(value)
        row=next(row for row in value['source']['callbacks'] if row['method']=='upload-success');self.assertFalse(row['stackAlive']);self.assertIsNone(row['leftEpochMs'])
        with self.assertRaises(NativeUIError):source.local_objects_gone(value,domain.owner)
    def test_passive_observer_failure_leaves_actual_model_send_effect_and_unqualified_diagnostics(self):
        domain=UploadDomain(self);domain.complete(observer_failure=True);value=domain.observe();source.original(value)
        self.assertEqual(2,domain.send_count);self.assertEqual(domain.path.read_bytes(),domain.received.getvalue());self.assertFalse(value['source']['complete'])
        for qualify in (source.decision,source.local_objects_gone):
            with self.assertRaises(NativeUIError):qualify(value,domain.owner)
    def test_retained_original_ticket_and_first_file_cannot_reanchor_after_actual_completion(self):
        domain=UploadDomain(self);domain.request('upload');before=domain.observe();source.original(before)
        changed=deepcopy(before);changed['requestId']='ios-'+'a'*32;changed['sequence']+=1
        changed['source']['requests'][0]['generation']='99';changed['source']['uploads'][0]['scopeGeneration']='99'
        with self.assertRaises(NativeUIError):source.validate(changed,dict(schemaVersion=1,commandId=changed['requestId'],action=source.ACTION,runId=RUN),42,previous=before)
        changed=deepcopy(before);changed['requestId']='ios-'+'b'*32;changed['sequence']+=1
        file=next(row for row in changed['source']['resources'] if row['kind']=='file');file['firstFile']['bytes']+=1
        for key in ('fdBefore','fdAfter'):file[key]['file']['bytes']+=1
        with self.assertRaises(NativeUIError):source.validate(changed,dict(schemaVersion=1,commandId=changed['requestId'],action=source.ACTION,runId=RUN),42,previous=before)
    def test_closed_fixture_action_and_actual_probe_keep_original_and_consume_failed_read_once(self):
        command=dict(schemaVersion=1,commandId='ios-'+'c'*32,action=source.ACTION,runId=RUN);state=FixtureState();self.assertEqual(command,state.set_client_command(command))
        for extra in ({'expected':{}},{'pid':42},{'schemaVersion':True}):
            with self.assertRaises((ValueError,RuntimeError)):state.set_client_command(command|extra)
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const saved=[];let calls=0;const original={iosSnapshotUploadsVersion:1,requestId:'ios-'+'c'.repeat(32),actual:'untouched'};
const Test={featureIOSSnapshotUploads:()=>{calls++;return original},saveObject:(v,name)=>saved.push({v,name})};
SOURCE
const c=QUERY;applyClientCommand(c);applyClientCommand(c);
if(calls!==1||saved[0].v!==original||saved[0].name!=='feature-ios-snapshot-uploads.json')throw Error('rewritten or resent');
applyClientCommand({...c,commandId:'ios-'+'d'.repeat(32),state:{}});if(calls!==1)throw Error('wanted state accepted');
Test.featureIOSSnapshotUploads=()=>{calls++;throw Error('lost source')};
const unknown={...c,commandId:'ios-'+'e'.repeat(32)};applyClientCommand(unknown);applyClientCommand(unknown);
if(calls!==2||saved.at(-1).v.status!=='unavailable')throw Error('failure became zero or repeated');
'''.replace('SOURCE',probe_source()).replace('QUERY',json.dumps(command))
        result=subprocess.run(['node'],input=program,capture_output=True,text=True,timeout=10);self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
