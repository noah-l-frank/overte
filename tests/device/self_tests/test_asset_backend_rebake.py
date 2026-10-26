"""Existing-map rebake originals over real files and declared work boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters import asset_backend_rebake as rebake,asset_backend_evidence as evidence
from asset_backend_evidence_fixture import Fixture
from test_asset_backend_source import NativeWorkModel


class BackendRebakeTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.addCleanup(self.f.close);self.path,self.digest,self.first=self.f.baked(holders=False)
        self.baseline,self.query=self.f.sample()

    def task(self,*,returned=True,holders=False):
        task=NativeWorkModel();task.inputs.update(hash=self.digest,path=self.path);task.events[0]['details']['inputs']=deepcopy(task.inputs);self.f.work.add(task)
        run,callback=task.enter(),task.enter(True)
        if returned:task.leave(callback,True);task.leave(run)
        if not holders:task.expire('lease','owner','object')
        return task,run,callback

    def proof(self):
        current,query=self.f.sample();return rebake.ready(self.baseline,self.query,current,query,self.f.config,self.path,self.digest)

    def test_new_actual_run_reuses_existing_original_without_changing_first_upload_rule(self):
        task,_,_=self.task();current,query=self.f.sample();proof=rebake.ready(self.baseline,self.query,current,query,self.f.config,self.path,self.digest)
        self.assertEqual(task.id,proof['jobId']);self.assertEqual(self.digest,proof['originalHash']);self.assertGreater(proof['outputBytes'],0)
        self.assertIsNone(evidence.bake_ready(self.baseline,self.query,current,query,self.f.config,self.path,self.digest))

    def test_preexisting_baked_output_and_new_metadata_do_not_replace_new_work(self):
        self.assertIsNone(self.proof());self.f.persist();self.assertIsNone(self.proof())

    def test_multiple_new_same_path_bakes_are_ambiguous_even_when_all_drained(self):
        self.task();self.task();self.assertIsNone(self.proof())

    def test_expired_weak_owners_do_not_replace_original_run_or_callback_returns(self):
        task,run,callback=self.task(returned=False);self.assertIsNone(self.proof());task.leave(callback,True);self.assertIsNone(self.proof());task.leave(run);self.assertIsNotNone(self.proof())

    def test_actual_remaining_holder_keeps_rebake_unqualified(self):
        task,_,_=self.task(holders=True);self.assertIsNone(self.proof());task.expire('lease','owner','object');self.assertIsNotNone(self.proof())

    def test_same_byte_replaced_original_inode_is_not_a_preserved_input(self):
        self.task();path=self.f.b.files/self.digest;raw=path.read_bytes();path.rename(self.f.b.root/'retained-original-input');self.f.blob(raw)
        self.assertIsNone(self.proof())

    def test_missing_output_or_failed_or_old_metadata_is_not_rebake_success(self):
        self.task();prefix='/.baked/'+self.digest+'/';del self.f.mappings[prefix+'asset.fbx'];self.f.persist();self.assertIsNone(self.proof())
        import json
        self.f.mappings[prefix+'asset.fbx']=self.f.blob(b'actual current output')
        for failed,version in ((True,1),(False,0)):
            value=dict(bake_version=version,failed_last_bake=failed,last_bake_errors='original error' if failed else '',redirect_target='')
            self.f.mappings[prefix+'meta.json']=self.f.blob(json.dumps(value).encode());self.f.persist();self.assertIsNone(self.proof())

    def test_baseline_must_already_be_quiet_before_the_new_normal_action(self):
        task,run,callback=self.task(returned=False,holders=True);self.baseline,self.query=self.f.sample();task.leave(callback,True);task.leave(run);task.expire('lease','owner','object');self.task()
        self.assertIsNone(self.proof())


if __name__=='__main__':unittest.main()
