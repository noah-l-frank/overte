#!/usr/bin/env python3
"""Full fake-API native owner lifecycle; no hosted queries or workloads."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import hashlib
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/test-evidence'))


class NativeOwnerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse data builders only. No existing unittest method is inherited,
        # discovered or executed by this separate lifecycle command.
        path = ROOT/'tools/test-evidence/ci-integration-test.py'
        spec = importlib.util.spec_from_file_location('native_lifecycle_fixtures', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.module.CurrentOriginalOwnerTests.setUpClass()

    def setUp(self):
        fixture = self.module.CurrentOriginalOwnerTests('runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.owner = fixture
        self.case = c = fixture.case
        self.api = fixture.fixtures.A
        self.protocol = fixture.fixtures.P
        self.now = fixture.now
        caller = c.policy.caller_path
        c.generation = {**deepcopy(c.generation),
            '.github/workflows/browser-client.yml':{'mode':'100644','type':'blob','sha':'1'*40},
            self.api.METADATA_WORKFLOW:{'mode':'100644','type':'blob',
                'sha':'b76ade9fd7a76da21bf2cb2161deae7a262163e8'}}
        c.generation[caller]['sha'] = '22fe0d6d39d120f800099136d7d1ab5280d80b41'
        c.policy = replace(c.policy,
            generations={'reviewed':{p:deepcopy(c.generation[p]) for p in self.api.WORKFLOWS}},
            metadata_generations={'modern':deepcopy(c.generation)},
            metadata_sources={'modern':{self.api.METADATA_SOURCE:
                {'mode':'100644','type':'blob','sha':'6'*40}}})
        fixture.context['policy'] = c.policy
        c.runs[100]['display_title'] = self.api.ORDINARY_RUN_NAME
        c.runs[100]['referenced_workflows'].append({
            'path':self.api.REPOSITORY+'/'+self.api.METADATA_WORKFLOW+'@'+c.binding['merge_sha'],
            'sha':c.binding['merge_sha'],'ref':c.pp.workflow_ref})
        c.api = fixture.fixtures.MetadataFakeApi(c)
        c.adapter = self.api.Adapter(c.api)
        self.corrupt = lambda endpoint,value:value

        def endpoint_updates(endpoint,value):
            if endpoint.endswith('/actions/runs/100/attempts/1'):
                # Real PR1443 list/latest and attempt differ by one second.
                value['updated_at'] = '2026-10-15T10:04:31Z'
            return self.corrupt(endpoint,value)
        c.api.mutate = endpoint_updates

    def capture_authority(self):
        snapshot = self.case.capture()
        authority = self.protocol.select_authority(snapshot.observations, snapshot.binding,
            self.case.plan, self.case.pp, inventory_complete=snapshot.inventory_complete, now=self.now)
        return snapshot,authority

    def test_pending_original_retains_real_owners_without_becoming_metadata_or_completed_evidence(self):
        snapshot,authority = self.capture_authority()
        self.assertTrue(snapshot.inventory_complete)
        self.assertEqual(snapshot.metadata_nonproducers,{})
        self.assertEqual([item.run.run_id for item in snapshot.observations],[100])
        self.assertEqual((authority['state'],authority['run_id'],authority['attempt']),('pending',100,1))
        value = self.owner.verify(self.module.P.DOCUMENTATION_SUITES|self.module.P.WORKFLOW_CONTRACT_SUITES)
        self.assertEqual((value['kind'],value['run_id'],value['outer_job_id']),
                         ('current-original-pr-owners',100,140))
        self.assertTrue(value['verified']); self.assertFalse(value['qualification']); self.assertFalse(value['reusable'])
        self.assertEqual(value['source_chain']['producer_commit'],self.case.binding['merge_sha'])
        self.assertEqual((self.case.runs[100]['status'],self.case.runs[100]['conclusion']),('in_progress',None))
        self.assertEqual(self.case.runs[100]['updated_at'],'2026-10-15T10:04:30Z')
        self.assertEqual(self.case.adapter._object('actions/runs/100/attempts/1')['updated_at'],
                         '2026-10-15T10:04:31Z')

    def test_completed_original_is_not_metadata_and_keeps_completed_protocol_authority(self):
        self.case.runs[100].update(status='completed',conclusion='success')
        snapshot,authority = self.capture_authority()
        self.assertTrue(snapshot.inventory_complete)
        self.assertEqual(snapshot.metadata_nonproducers,{})
        self.assertEqual([item.run.run_id for item in snapshot.observations],[100])
        self.assertEqual((authority['state'],authority['run_id'],authority['attempt']),('proof-required',100,1))
        self.assertEqual(snapshot.observations[0].run.status,'completed')
        self.assertEqual(snapshot.observations[0].run.conclusion,'success')
        with self.assertRaises((self.module.H.Unavailable,self.protocol.ProtocolError)):
            self.owner.verify()

    def test_changed_original_provenance_never_passes_the_current_owner_lifecycle(self):
        for shape in ('foreign','unknown-recipe','alias-recipe','unreviewed-metadata-recipe',
                      'old-source','attempt2','descriptor','suite-app'):
            self.setUp(); c = self.case
            def corrupt(endpoint,value):
                if endpoint.endswith('/actions/runs/100/attempts/1'):
                    if shape == 'foreign': value['head_repository']['id'] = 42
                    elif shape == 'attempt2': value['run_attempt'] = 2
                if shape == 'unknown-recipe' and endpoint.endswith('/git/trees/'+'2'*40):
                    next(row for row in value['tree'] if row['path']=='repository-checks.yml')['sha'] = 'f'*40
                elif shape == 'alias-recipe' and endpoint.endswith('/git/trees/'+'2'*40):
                    next(row for row in value['tree'] if row['path']=='repository-checks.yml')['mode'] = '120000'
                elif shape == 'suite-app' and endpoint.endswith('/check-suites/1100'):
                    value['app']['id'] = 42
                return value
            self.corrupt = corrupt
            if shape == 'unreviewed-metadata-recipe':
                rows = deepcopy(c.policy.metadata_generations)
                rows['modern'][c.policy.caller_path]['sha'] = 'f'*40
                c.policy = replace(c.policy,metadata_generations=rows)
                self.owner.context['policy'] = c.policy
            elif shape == 'old-source':
                other = 'a1'*20
                c.originals[other] = (c.binding['merge_tree'],list(c.binding['merge_parents']))
                for edge in c.runs[100]['referenced_workflows']:
                    edge.update(sha=other,path=edge['path'].rsplit('@',1)[0]+'@'+other)
            elif shape == 'descriptor':
                c.artifacts[100] = [item for item in c.artifacts[100]
                                    if not item['name'].startswith('ci-descriptor-')]
            with self.subTest(shape=shape):
                snapshot,authority = self.capture_authority()
                self.assertEqual(snapshot.metadata_nonproducers,{})
                self.assertNotEqual(authority['state'],'proof-required')
                with self.assertRaises((self.module.H.Unavailable,self.protocol.ProtocolError)):
                    self.owner.verify()

    def test_ordinary_intent_never_excludes_failed_or_missing_completed_native_owners(self):
        for shape in ('shared-failure','publisher-missing','outer-failure','bad-native-check','missing-result'):
            self.setUp(); c = self.case
            if shape == 'shared-failure':
                next(job for job in c.jobs[100] if job['name']==c.policy.owner_jobs['shared-host'])['conclusion'] = 'failure'
            elif shape == 'publisher-missing':
                c.jobs[100] = [job for job in c.jobs[100] if not job['name'].startswith(c.policy.final_publisher_prefix)]
            elif shape == 'outer-failure':
                next(job for job in c.jobs[100] if job['name']=='repository-checks').update(status='completed',conclusion='failure')
            elif shape == 'bad-native-check':
                self.corrupt = lambda endpoint,value:({**value,'conclusion':'failure'}
                    if endpoint.endswith('/check-runs/140') else value)
            else:
                value = deepcopy(self.owner.receipt); del value['results']['documentation']
                self.owner.receipt = self.owner.fixtures.FIXTURES.signed(value,'receipt_digest')
                self.owner.run = replace(self.owner.run,final_publisher=replace(self.owner.run.final_publisher,
                    receipt_sha256=hashlib.sha256(self.protocol.canonical(self.owner.receipt)).hexdigest()))
                refs = deepcopy(c.runs[100]['referenced_workflows'])
                self.owner.refresh()
                c.runs[100].update(display_title=self.api.ORDINARY_RUN_NAME,referenced_workflows=refs)
            with self.subTest(shape=shape):
                snapshot,_ = self.capture_authority()
                self.assertEqual(snapshot.metadata_nonproducers,{})
                with self.assertRaises((self.module.H.Unavailable,self.protocol.ProtocolError)):
                    self.owner.verify()


if __name__ == '__main__': unittest.main()
