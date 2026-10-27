"""Normal Upload4 originals and parent recovery, with declared native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_causal_dispatch as source
from ios.adapters.snapshot_capture_runtime import IOSSnapshotCaptureRuntime
from ios.adapters.snapshot_frontend_branch import PINS,joined
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.adapters.snapshot_upload_packets import CausalDispatchSegments,CombinedHttpSegments,packet_types
from ios.self_tests.snapshot_causal_parent_domain import CausalParentDomain
from ios.self_tests.test_ios_snapshot_manifest import SnapshotManifestTests


class SnapshotCausalParentContractTests(unittest.TestCase):
    def test_causal_profile_is_explicit_before_source_session_or_backend_access(self):
        for combined,http,caller in ((False,True,True),(True,False,True),(True,True,1)):
            with self.subTest(combined=combined,http=http,caller=caller),self.assertRaises(NativeUIError):
                with IOSSnapshotCaptureRuntime.upload_owner(object(),'primary','a'*32,None,combined=combined,frontend_http=http,frontend_caller=caller):pass
        self.assertNotIn('causal',packet_types());self.assertNotIn('causal',packet_types(True));self.assertIn('causal',packet_types(True,True))
    def test_causal_parts_use_their_own_closed_short_namespace(self):
        f=SnapshotManifestTests();f.setUp();self.addCleanup(f.doCleanups);intents=[]
        with f.lock.held():
            args=(f.root,f.binding,'a'*32,'primary','upload',lambda:True,intents.append)
            own=CausalDispatchSegments(*args,monotonic=time.monotonic);self.assertLessEqual(len(own.store.namespace),32)
            raw=b'original causal dispatch bytes';parent=own.write('raw',hashlib.sha256(raw).hexdigest(),raw,1)
            self.assertEqual(raw,own.read(parent));self.assertTrue(own.store.path(parent['chunks'][0]).name.startswith('snapshot-causal-upload-parts-'))
            with self.assertRaises((NativeUIError,OSError)):CombinedHttpSegments(*args,monotonic=time.monotonic).read(parent)
    def test_reviewed_full_stack_positions_and_tokens_equal_repository_originals(self):
        pins=json.loads(PINS.read_text());root=Path(__file__).resolve().parents[4]/'scripts'
        for name,expected in pins['sources'].items():
            data=(root/name).read_text().encode('utf-16-le');self.assertEqual(expected,dict(codeUnits=len(data)//2,sha256=hashlib.sha256(data).hexdigest()))
        for frame in pins['frames']:
            line=(root/frame['source']).read_text().splitlines()[frame['line']-1]
            self.assertTrue(line[frame['column']-1:].startswith(frame['token']))
        self.assertEqual([175,611,635,59,43],[frame['line'] for frame in pins['frames']])


class SnapshotCausalParentTests(unittest.TestCase):
    def test_normal_input_actual_callback_queue_upload_and_backend_have_one_pure_original_lineage(self):
        d=CausalParentDomain(self);native_result=d.prepare_native();self.assertEqual(4,native_result['snapshotUploadResultVersion'])
        self.assertTrue(native_result['diagnosticQueueScopesDrained']);self.assertEqual(1,d.upload_count)
        with d.backend_owner() as backend:
            result=backend.original();fact=result['frontendBranch'];native=backend.native
            self.assertEqual(4,result['snapshotUploadBackendResultVersion']);self.assertFalse(result['frontendBranchAcceptanceRequired'])
            self.assertTrue(fact['sameCompiledV8HistoryJoined']);self.assertTrue(fact['originalNativeUploadIDJoined']);self.assertTrue(fact['wholeFeatureRequired'])
            self.assertEqual(d.native_birth_preflight,[fact['backendResponseId']]);self.assertEqual(d.calls[0]['instance'],fact['call'])
            self.assertEqual([175,611,635,59,43],[frame['line'] for frame in d.calls[0]['caller']['snapshotCombinedStack']['frames']])
            originals={p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in native.root.iterdir() if p.is_file()}
        calls,commands=deepcopy(d.private_calls),deepcopy(d.commands)
        with native.lock.held():
            archived=IOSSnapshotUploadBackendOwner.history(native,domain_policy=d.domain_policy)
            self.assertEqual(result,archived.proof());self.assertEqual(fact,joined(archived,result['frontendConsumption']))
        self.assertEqual(calls,d.private_calls);self.assertEqual(commands,d.commands);self.assertEqual(1,d.upload_count)
        self.assertEqual(originals,{p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in native.root.iterdir() if p.is_file()})
    def test_old_upload3_cannot_reopen_explicit_upload4_or_backend4(self):
        d=CausalParentDomain(self);d.prepare_native();commands=deepcopy(d.commands);calls=deepcopy(d.private_calls)
        with self.assertRaises(NativeUIError),d.upload_owner(frontend_caller=False):pass
        with self.assertRaises(NativeUIError),d.backend_owner(frontend_caller=False):pass
        self.assertEqual(commands,d.commands);self.assertEqual(calls,d.private_calls);self.assertEqual(1,d.upload_count)
    def test_lost_normal_input_return_recovers_causal_lineage_without_input_replay(self):
        d=CausalParentDomain(self);d.prepare();d.lost_upload=True
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        self.assertEqual(1,d.upload_count)
        with d.upload_owner() as owner:owner.start('a'*32);owner.finish()
        with d.backend_owner() as owner:self.assertFalse(owner.original()['frontendBranchAcceptanceRequired'])
        self.assertEqual(1,d.upload_count)
    def test_lost_causal_dispatch_adopts_exact_first_original_and_never_dispatches_twice(self):
        d=CausalParentDomain(self);d.prepare();d.lose_causal='after'
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        queries=[row for row in d.commands if row['action']==source.ACTION];self.assertEqual(1,len(queries));self.assertEqual(0,d.upload_count)
        with d.upload_owner() as owner:
            owner.start('a'*32);owner.finish();self.assertEqual(queries[0]['commandId'],owner.causal_original(owner.state['causalBefore'])['requestId'])
        self.assertEqual(5,sum(row['action']==source.ACTION for row in d.commands));self.assertEqual(1,d.upload_count)
    def test_unknown_causal_original_stays_owned_and_blocks_before_input_without_query_reissue(self):
        d=CausalParentDomain(self);d.prepare();d.lose_causal='before'
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        commands=deepcopy(d.commands)
        with d.upload_owner() as owner,self.assertRaises((OSError,NativeUIError)):owner.start('a'*32)
        self.assertEqual(commands,d.commands);self.assertEqual(0,d.upload_count)
    def test_original_pending_constructor_association_is_followed_without_input_or_original_rewrite(self):
        d=CausalParentDomain(self);d.delay_association=True;d.prepare()
        with d.upload_owner() as owner,self.assertRaises(NativeUIError):owner.start('a'*32)
        self.assertEqual(1,d.upload_count);self.assertIsNone(d.pending_dispatch)
        # The first original was acquired while real modeled scopes/lease were
        # still held; the modeled constructor returned only after that copy.
        with d.upload_owner() as owner:
            pending=deepcopy(owner.packet('causal',owner.state['causalAfter']))
            self.assertIsNone(pending['source']['calls'][0]['upload']);self.assertTrue(pending['source']['calls'][0]['leaseAlive'])
            self.assertTrue(any(hop['leftEpochMs'] is None for hop in pending['source']['calls'][0]['hops']))
            old_index=owner.state['causalAfter'];owner.start('a'*32);owner.finish()
            self.assertEqual(pending,owner.packet('causal',old_index));self.assertGreater(owner.state['causalAfter'],old_index)
        with d.backend_owner() as owner:self.assertFalse(owner.original()['frontendBranchAcceptanceRequired'])
        self.assertEqual(1,d.upload_count)
    def test_held_real_diagnostic_lease_blocks_parent_quiet_without_replaying_successful_upload(self):
        d=CausalParentDomain(self);d.hold_dispatch=True;d.prepare()
        with d.upload_owner() as owner:
            owner.start('a'*32)
            with self.assertRaises(NativeUIError):owner.finish()
            self.assertIsNone(owner.state['result'])
        self.assertTrue(d.held);self.assertEqual(1,d.upload_count)
        d.held.clear()
        with d.upload_owner() as owner:owner.finish()
        with d.backend_owner() as owner:self.assertTrue(owner.original()['frontendBranch']['diagnosticQueueScopesDrained'])
        self.assertEqual(1,d.upload_count)


class SnapshotCausalParentPureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=unittest.TestCase();cls.addClassCleanup(cls.fixture.doCleanups)
        cls.domain=CausalParentDomain(cls.fixture);cls.domain.prepare_native()
        with cls.domain.backend_owner() as backend:
            cls.result=backend.original();cls.native=backend.native
    def rejects(self,mutate):
        native=self.native;packet=native.packet
        def changed(kind,index):
            value=deepcopy(packet(kind,index))
            if kind=='causal' and index==native.state['causalAfter']:mutate(value['source']['calls'][0])
            return value
        with native.lock.held(),patch.object(native,'packet',side_effect=changed),self.assertRaises(NativeUIError):
            native.causal_call(changed('causal',native.state['causalAfter']))
        self.assertEqual(1,self.domain.upload_count)
    def test_same_compiled_module_cannot_admit_deferred_login_or_extra_caller_frames(self):
        self.rejects(lambda row:row['caller']['snapshotCombinedStack']['frames'][0].update(line=788))
        self.rejects(lambda row:row['caller']['snapshotCombinedStack']['frames'].append(deepcopy(row['caller']['snapshotCombinedStack']['frames'][-1])))
    def test_foreign_v8_birth_or_script_identity_cannot_replace_capture_history(self):
        self.rejects(lambda row:row['caller']['snapshotCombinedStack'].update(instance='7'*32))
        self.rejects(lambda row:row['caller']['snapshotCombinedStack']['frames'][0]['compiled'].update(firstObservedEpochMs=row['caller']['snapshotCombinedStack']['frames'][0]['compiled']['firstObservedEpochMs']+1))
    def test_unrelated_native_upload_or_different_original_callback_cannot_be_rebound(self):
        self.rejects(lambda row:row.update(upload='7'*32))
        self.rejects(lambda row:row['http'].update(httpInstance='7'*32))
        self.rejects(lambda row:row['http']['read']['clock'].update(epochMs=row['http']['read']['clock']['epochMs']+1))
    def test_three_upload_samples_cannot_reuse_one_causal_original_for_quiet(self):
        native=self.native;old=deepcopy(native.state['quiet'])
        with native.lock.held():
            try:
                for group in native.state['quiet']:group['causal']=old[-1]['causal']
                with self.assertRaises(NativeUIError):native.proof()
            finally:native.state['quiet']=old
        self.assertEqual(1,self.domain.upload_count)
    def test_foreign_http_v8_birth_cannot_join_same_manager_and_event_bytes(self):
        native=self.native;read=native.http_original
        def foreign(index):
            value=deepcopy(read(index))
            for entry in value['callerStacks']:entry['callerStack']['instance']='7'*32
            return value
        with native.lock.held(),patch.object(native,'http_original',side_effect=foreign),self.assertRaises(NativeUIError):
            native.causal_call(native.packet('causal',native.state['causalAfter']))
        self.assertEqual(1,self.domain.upload_count)


if __name__=='__main__':unittest.main()
