"""Independent backend fact and quiet counterexamples; all native work modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters import asset_backend_evidence as evidence
from asset_backend_evidence_fixture import Fixture


class BackendEvidenceTests(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.addCleanup(self.f.close);self.baseline,self.baseline_query=self.f.sample()
    def bake(self,current,query,path,digest):return evidence.bake_ready(self.baseline,self.baseline_query,current,query,self.f.config,path,digest)
    def restored(self,first,q1,last,q2):return evidence.restored(self.baseline,self.baseline_query,first,q1,last,q2,self.f.config)
    def test_actual_new_run_complete_callback_weak_expiry_meta_and_readable_output_join(self):
        path,digest,_=self.f.baked(holders=False);current,query=self.f.sample();proof=self.bake(current,query,path,digest)
        self.assertEqual(digest,proof['originalHash']);self.assertGreater(proof['outputBytes'],0);self.assertNotEqual(digest,proof['outputHash'])
    def test_expired_holders_do_not_replace_pending_original_run_and_callback_bodies(self):
        path,digest,task=self.f.baked(returned=False,holders=False);current,query=self.f.sample();self.assertIsNone(self.bake(current,query,path,digest))
        callback=next(event['details']['bodyId'] for event in task.events if event['kind']=='callback-enter');run=next(event['details']['bodyId'] for event in task.events if event['kind']=='run-enter')
        task.leave(callback,True);task.leave(run);current,query=self.f.sample();self.assertIsNotNone(self.bake(current,query,path,digest))
    def test_signal_and_run_completion_do_not_replace_actual_remaining_owners(self):
        path,digest,task=self.f.baked();current,query=self.f.sample();self.assertIsNone(self.bake(current,query,path,digest));task.expire('lease','owner','object');current,query=self.f.sample();self.assertIsNotNone(self.bake(current,query,path,digest))
    def test_successful_callback_without_real_output_or_current_success_meta_is_not_ready(self):
        path,digest,_=self.f.baked(holders=False,output=False);current,query=self.f.sample();self.assertIsNone(self.bake(current,query,path,digest))
        for failed,version in ((True,1),(False,0)):
            prefix='/.baked/'+digest+'/';meta=dict(bake_version=version,failed_last_bake=failed,last_bake_errors='actual error' if failed else '',redirect_target='')
            import json
            self.f.mappings[prefix+'meta.json']=self.f.blob(json.dumps(meta).encode());self.f.mappings[prefix+'asset.fbx']=self.f.blob(b'actual output');self.f.persist();current,query=self.f.sample()
            with self.subTest(failed=failed,version=version):self.assertIsNone(self.bake(current,query,path,digest))
    def test_baseline_restoration_preserves_foreign_inodes_and_requires_both_quiet_domains(self):
        self.f.baked(holders=False);self.f.restore();first,q1=self.f.sample();self.f.advance();last,q2=self.f.sample();proof=self.restored(first,q1,last,q2)
        self.assertGreaterEqual(proof['nativeQuietMs'],3000);self.assertGreaterEqual(proof['hostQuietMs'],3000);self.assertEqual(len(self.f.initial_names),proof['blobs'])
    def test_mapping_absence_with_unshared_blob_or_hidden_meta_residue_is_not_restored(self):
        path,digest,_=self.f.baked(holders=False);self.f.mappings=dict(self.f.initial);self.f.persist();first,q1=self.f.sample();self.f.advance();last,q2=self.f.sample();self.assertIsNone(self.restored(first,q1,last,q2))
        self.f.restore();self.f.mappings['/.baked/'+digest+'/asset.fbx']=digest;self.f.persist();first,q1=self.f.sample();self.f.advance();last,q2=self.f.sample();self.assertIsNone(self.restored(first,q1,last,q2))
    def test_host_or_native_elapsed_alone_never_supplies_a_quiet_window(self):
        first,q1=self.f.sample();self.f.advance(host=3100,native=1);last,q2=self.f.sample();self.assertIsNone(self.restored(first,q1,last,q2))
        first,q1=self.f.sample();self.f.advance(host=1,native=3100);last,q2=self.f.sample();self.assertIsNone(self.restored(first,q1,last,q2))
    def test_new_worker_during_quiet_window_invalidates_even_if_it_already_died(self):
        first,q1=self.f.sample();self.f.advance();self.f.baked(holders=False);self.f.restore();last,q2=self.f.sample();self.assertIsNone(self.restored(first,q1,last,q2))
    def test_foreign_same_byte_recreation_is_not_preservation_of_the_original_blob(self):
        first,q1=self.f.sample();name=next(iter(self.f.initial_names));path=self.f.b.files/name;raw=path.read_bytes();path.rename(self.f.b.root/'retained-foreign');self.f.blob(raw)
        self.f.advance();last,q2=self.f.sample();self.assertIsNone(self.restored(first,q1,last,q2))
