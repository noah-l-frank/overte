"""Closed extra mapping delta over declared decoded inventory originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_baked_tree import deleted_mappings,fresh_baseline
from asset_backend_evidence_fixture import Fixture

RUN='a'*32


class AssetsBakedTreeFactsTests(unittest.TestCase):
    def setUp(self):
        self.digest='b'*64;self.prefix='/renamed-'+RUN+'/';self.derived='/.baked/'+self.digest+'/'
        self.qualified={self.derived+'asset.fbx':'c'*64,self.derived+'meta.json':'d'*64}
        def row(path,digest):return dict(path=path,hash=digest,status=4,bakingErrors='')
        self.before=dict(mappings=sorted([row('/foreign/keep.txt','e'*64),row(self.prefix+'stand.fbx',self.digest),
            *(row(path,digest) for path,digest in self.qualified.items())],key=lambda value:value['path'].encode('utf-16be')))
        self.after=dict(mappings=[deepcopy(row) for row in self.before['mappings'] if row['path']=='/foreign/keep.txt'])

    def proof(self,before=None,after=None,**change):
        values=dict(owned_prefix=self.prefix,derived_prefix=self.derived,original_hash=self.digest,qualified=self.qualified,baseline_blobs={'e'*64:{}});values.update(change)
        return deleted_mappings(before or self.before,after or self.after,**values)

    def test_only_exact_qualified_own_input_and_derived_paths_may_disappear(self):
        result=self.proof();self.assertEqual(self.qualified,result['derived']);self.assertEqual({self.prefix+'stand.fbx':self.digest},result['owned'])

    def test_foreign_mapping_loss_change_or_unrelated_hidden_prefix_is_not_cleanup(self):
        for after in (dict(mappings=[]),dict(mappings=[dict(self.after['mappings'][0],hash='f'*64)]),
                dict(mappings=[*self.after['mappings'],dict(path='/.baked/'+'f'*64+'/asset.fbx',hash='c'*64,status=4,bakingErrors='')])):
            with self.subTest(after=after),self.assertRaises(NativeUIError):self.proof(after=after)

    def test_same_hash_foreign_alias_and_existing_baseline_output_blob_remain_protected(self):
        before=deepcopy(self.before);before['mappings'].append(dict(path='/foreign/shared.fbx',hash=self.digest,status=4,bakingErrors=''))
        after=deepcopy(self.after);after['mappings'].append(deepcopy(before['mappings'][-1]))
        with self.assertRaises(NativeUIError):self.proof(before,after)
        for digest in self.qualified.values():
            with self.subTest(digest=digest),self.assertRaises(NativeUIError):self.proof(baseline_blobs={digest:{}})

    def test_missing_or_foreign_derived_lineage_and_duplicate_mapping_are_rejected(self):
        for change in (dict(qualified={}),dict(qualified={self.derived+'asset.fbx':'f'*64}),dict(derived_prefix='/.baked/'+'f'*64+'/'),dict(owned_prefix='/')):
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.proof(**change)
        before=deepcopy(self.before);before['mappings'].append(deepcopy(before['mappings'][0]))
        with self.assertRaises(NativeUIError):self.proof(before)

    def test_both_hidden_meta_and_output_are_required_to_disappear(self):
        for row in self.before['mappings']:
            if not row['path'].startswith(self.derived):continue
            after=deepcopy(self.after);after['mappings'].append(deepcopy(row))
            with self.subTest(path=row['path']),self.assertRaises(NativeUIError):self.proof(after=after)


class AssetsBakedBaselineTests(unittest.TestCase):
    def setUp(self):self.fixture=Fixture();self.addCleanup(self.fixture.close);self.packet=dict(source=self.fixture.snapshot());self.digest='f'*64
    def test_original_admission_preserves_independent_foreign_snapshot(self):
        before=deepcopy(self.packet);self.assertEqual('/.baked/'+self.digest+'/',fresh_baseline(self.packet,self.digest));self.assertEqual(before,self.packet)
    def test_prior_hash_alias_blob_or_hidden_ownership_is_not_fresh_admission(self):
        for mutate in (lambda packet:packet['source']['memoryMappings'].append(dict(path='/foreign/shared.fbx',hash=self.digest)),
                lambda packet:packet['source']['blobs'].append(dict(name=self.digest)),
                lambda packet:packet['source']['memoryMappings'].append(dict(path='/.baked/'+self.digest+'/meta.json',hash='e'*64))):
            packet=deepcopy(self.packet);mutate(packet)
            with self.assertRaises(NativeUIError):fresh_baseline(packet,self.digest)
    def test_missing_complete_source_or_live_work_cannot_authorize_fresh_scope(self):
        for mutate in (lambda packet:packet['source'].update(complete=False),lambda packet:packet['source']['workAfter'].update(complete=False)):
            packet=deepcopy(self.packet);mutate(packet)
            with self.assertRaises(NativeUIError):fresh_baseline(packet,self.digest)
