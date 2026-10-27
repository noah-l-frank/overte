"""Normal Combined Upload3 source/HTTP/backend composition; no native runtime."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
import time
import hashlib
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.adapters.snapshot_frontend_consumption import joined
from ios.adapters.snapshot_capture_runtime import IOSSnapshotCaptureRuntime
from ios.adapters.snapshot_upload_packets import CombinedHttpSegments,UploadSegments,packet_types
from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests
from ios.adapters import snapshot_combined_preflight_http as http
from ios.self_tests.snapshot_combined_consumer_domain import CombinedConsumerDomain


class SnapshotCombinedConsumerContractTests(unittest.TestCase):
    def test_http_parts_keep_short_private_namespace_and_refuse_literal_upload_parts(self):
        f=SnapshotManifestTests();f.setUp();self.addCleanup(f.doCleanups);intents=[]
        with f.lock.held():
            args=(f.root,f.binding,'a'*32,'primary','upload',lambda:True,intents.append)
            own=CombinedHttpSegments(*args,monotonic=time.monotonic)
            self.assertLessEqual(len(own.store.namespace),32)
            raw=b'original Combined HTTP bytes';tag=hashlib.sha256(raw).hexdigest();parent=own.write('raw',tag,raw,1)
            self.assertEqual(raw,own.read(parent));self.assertTrue(own.store.path(parent['chunks'][0]).name.startswith('snapshot-http-upload-parts-'))
            literal=UploadSegments(f.root,f.binding,'a'*32,'primary','uploads',lambda:True,intents.append,monotonic=time.monotonic)
            with self.assertRaises((NativeUIError,OSError)):literal.read(parent)
            self.assertNotIn('http',packet_types());self.assertIn('http',packet_types(True))
    def test_http_profile_is_explicit_before_existing_source_or_session_access(self):
        for combined,frontend in ((False,True),(True,1),(1,False)):
            with self.subTest(combined=combined,frontend=frontend),self.assertRaises(NativeUIError):
                with IOSSnapshotCaptureRuntime.upload_owner(object(),'primary','a'*32,None,combined=combined,frontend_http=frontend):pass


class SnapshotCombinedConsumerTests(unittest.TestCase):
    def test_actual_response_get_and_normal_png_upload_bind_same_manager_backend_bytes_and_pure_archive(self):
        d=CombinedConsumerDomain(self);native_result=d.prepare_native()
        self.assertEqual(3,native_result['snapshotUploadResultVersion']);self.assertTrue(native_result['frontendHTTPOriginalsRetained'])
        self.assertEqual(['created','sent','callback-enter','text-read','callback-leave'],[row['kind'] for row in d.http.trace_events])
        with d.backend_owner() as owner:
            result=owner.original();fact=result['frontendConsumption'];native=owner.native
            self.assertEqual(3,result['snapshotUploadBackendResultVersion']);self.assertFalse(result['frontendResponseConsumptionRequired'])
            self.assertTrue(result['frontendBranchAcceptanceRequired']);self.assertTrue(fact['backendBytesJoined'])
            self.assertTrue(fact['sameCaptureManagerJoined']);self.assertTrue(fact['knownXHRObjectsDrained'])
            self.assertEqual(d.native_birth_preflight,[fact['backendResponseId']]);self.assertEqual(1,d.upload_count)
            self.assertLessEqual(fact['nativeRead']['epochMs'],fact['nativeUploadBornEpochMs'])
            self.assertNotEqual(owner.packet(owner.state['preflight'])['clockDomain'],native.http_original(native.state['httpAfter'])['clockDomain'])
            artifact=native.capture.history('artifact',native.capture.state['artifact']);path=artifact.path();png=(path.stat().st_ino,path.read_bytes())
            self.assertEqual(png[1],d.backend.independent_body(result['upload'])[1]);originals={p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in native.root.iterdir() if p.is_file()}
        calls,commands=deepcopy(d.private_calls),deepcopy(d.commands)
        with native.lock.held():
            archived=IOSSnapshotUploadBackendOwner.history(native,domain_policy=d.domain_policy)
            self.assertEqual(result,archived.proof());self.assertEqual(fact,joined(archived))
        self.assertEqual(calls,d.private_calls);self.assertEqual(commands,d.commands)
        self.assertEqual(originals,{p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in native.root.iterdir() if p.is_file()})
        self.assertEqual(png,(path.stat().st_ino,path.read_bytes()))

    def test_old_combined_profile_refuses_upload3_before_native_or_backend_acquisition(self):
        d=CombinedConsumerDomain(self);d.prepare_native();calls,commands=deepcopy(d.private_calls),deepcopy(d.commands)
        with self.assertRaises(NativeUIError),d.upload_owner(frontend_http=False):pass
        with self.assertRaises(NativeUIError),d.backend_owner(frontend_http=False):pass
        self.assertEqual(calls,d.private_calls);self.assertEqual(commands,d.commands);self.assertEqual(1,d.upload_count)

    def test_lost_normal_upload_return_recovers_actual_input_and_consumption_without_replay(self):
        d=CombinedConsumerDomain(self);d.prepare();d.lost_upload=True
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        self.assertEqual(1,d.upload_count);query_count=sum(row['action']==http.ACTION for row in d.commands)
        self.assertEqual(1,query_count)
        with d.upload_owner() as owner:owner.start('a'*32);owner.finish()
        with d.backend_owner() as backend:self.assertTrue(backend.original()['frontendConsumption']['originalResponseTextRead'])
        self.assertEqual(1,d.upload_count);self.assertEqual(2,sum(row['action']==http.ACTION for row in d.commands))

    def test_lost_http_send_return_adopts_same_original_nonce_without_a_second_dispatch(self):
        d=CombinedConsumerDomain(self);d.prepare();d.lose_http='after'
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        queries=[row for row in d.commands if row['action']==http.ACTION];self.assertEqual(1,len(queries));self.assertEqual(0,d.upload_count)
        with d.upload_owner() as owner:
            owner.start('a'*32);owner.finish()
            before=owner.http_original(owner.state['httpBefore']);self.assertEqual(queries[0]['commandId'],before['requestId'])
        self.assertEqual(2,sum(row['action']==http.ACTION for row in d.commands));self.assertEqual(1,d.upload_count)

    def test_unknown_http_query_without_original_blocks_before_input_and_never_resends(self):
        d=CombinedConsumerDomain(self);d.prepare();d.lose_http='before'
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        calls=deepcopy(d.commands)
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        self.assertEqual(calls,d.commands);self.assertEqual(0,d.upload_count)
        self.assertEqual(1,sum(row['action']==http.ACTION for row in calls))

    def test_foreign_capture_manager_is_retained_as_fact_and_blocks_parent_before_repeat_input(self):
        d=CombinedConsumerDomain(self);d.prepare()
        def foreign(value):
            for row in value['events']:
                if row['kind']=='created':row['details']['engine']['instance']='d'*32
        d.http.mutate=foreign
        with d.upload_owner() as owner,self.assertRaises(NativeUIError):owner.start('a'*32)
        self.assertEqual(1,d.upload_count);count=len(d.commands)
        with d.upload_owner() as owner,self.assertRaises(NativeUIError):owner.start('a'*32)
        self.assertEqual(count,len(d.commands));self.assertEqual(1,d.upload_count)

    def test_undrained_xhr_cannot_become_consumed_backend_result(self):
        d=CombinedConsumerDomain(self);d.http.hold=True;d.prepare_native()
        with d.backend_owner() as owner,self.assertRaises(NativeUIError):owner.original()
        self.assertIsNone(owner.state['result']);self.assertTrue(d.http.objects);self.assertEqual(1,d.upload_count)

    def test_changed_response_identity_or_query_bytes_cannot_match_original_backend(self):
        d=CombinedConsumerDomain(self);d.prepare_native()
        with d.backend_owner() as owner:
            owner.original();native=owner.native;read=native.http_original
            for field in ('responseId','requestUrl'):
                def foreign(index):
                    value=deepcopy(read(index))
                    for row in value['events']:
                        if field=='responseId' and row['kind']=='reply-finished':row['details']['responseId']='c'*32
                        elif field=='requestUrl' and row['kind'] in ('created','sent'):
                            key='requestUrl' if row['kind']=='created' else 'url';row['details'][key]=row['details'][key].replace('controlled.invalid','foreign.invalid')
                    return value
                with self.subTest(field=field),patch.object(native,'http_original',side_effect=foreign),self.assertRaises(NativeUIError):joined(owner)
        self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
