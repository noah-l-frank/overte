#!/usr/bin/env python3
"""Offline reuse provenance with real native context/transport/receipt validators.

Only the read-only API, downloaded archives and immutable remote-tree adapter
are fixtures. No hosted job, candidate command or network request is executed.
"""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(os.environ.get('OVERTE_REUSE_TEST_ROOT', ROOT))
sys.path.insert(0, str(TEST_ROOT / 'tools/repository-checks'))
import pr_ci as CLI
import pr_ci_reuse as REUSE
import pr_ci_run as RUNNER
T = REUSE.T
spec = importlib.util.spec_from_file_location('reuse_native_fixture', TEST_ROOT / 'tests/pr-ci-cli-test.py')
FIXTURE = importlib.util.module_from_spec(spec); spec.loader.exec_module(FIXTURE)


class ReuseProvenance(unittest.TestCase):
    def setUp(self):
        f = self.f = FIXTURE.GateTests(); f.setUp(); f.ordinary_worker()
        f.native.update(status='completed', conclusion='success',
            created_at=datetime.now(timezone.utc).isoformat())
        f.job_rows[-1].update(name='required-ci', status='completed', conclusion='success')
        f.pr.update(state='closed', merged=True, merged_at='2026-10-22T00:00:00Z', merge_commit_sha=f.regenerated)
        self.task = {'id':'suite:contract', 'kind':'host', 'command':['python','tests/contract.py'],
            'reuse_key':'sha256:'+'a'*64, 'missing_inputs':[], 'setup':[]}
        self.runtime = {'schema':1, 'digest':'b'*64}
        f.plan['tasks'] = [self.task]
        f.record.update(context=deepcopy(f.context), plan=deepcopy(f.plan))
        self.child = {**deepcopy(f.context), 'number':43, 'target':'apple-main', 'head_ref':'main',
            'head':f.regenerated, 'base':'6'*40, 'original_merge':'7'*40, 'tree':'8'*40,
            'run_id':124, 'caller_source':'7'*40}
        self.command_row = {'task':self.task['id'], 'input_key':self.task['reuse_key'],
            'result':'success', 'command':self.task['command'], 'runtime':self.runtime,
            'executed':True, 'origin':None}
        self.command_record = {'kind':'pr-ci-task-results-v1', 'context':deepcopy(f.context),
            'lane':'host', 'project':'', 'results':[self.command_row]}
        self.compare = 'compare/'+f.regenerated+'...'+self.child['head']
        f.api.objects[self.compare] = {'status':'identical', 'base_commit':{'sha':f.regenerated},
            'merge_base_commit':{'sha':f.regenerated}}
        f.api.objects['git/commits/'+f.base] = {'sha':f.base,'tree':{'sha':'e'*40}}
        f.api.objects['git/trees/'+'e'*40+'?recursive=1'] = self.tree_response(f.source_tree, 'e'*40)
        f.api.lists['commits/'+self.child['head']+'/pulls'] = [f.pr]
        self.archives = {}
        self.refresh_artifacts()

    def tree_response(self, tree, oid):
        return {'sha':oid, 'truncated':False, 'tree':[{'path':p, **v} for p,v in tree.items()]}

    def refresh_artifacts(self):
        f=self.f
        self.archives = f.install_artifacts()
        name=REUSE.artifact_name(f.context, 'host')
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('tasks.json', CLI.C.canonical(self.command_record))
        raw=stream.getvalue(); self.archives[323]=raw
        row={'id':323,'name':name,'expired':False,'size_in_bytes':len(raw),
            'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),
            'url':T.API_ROOT+'/actions/artifacts/323',
            'archive_download_url':T.API_ROOT+'/actions/artifacts/323/zip',
            'workflow_run':{'id':123,'repository_id':CLI.C.REPOSITORY_ID,
                'head_repository_id':CLI.C.REPOSITORY_ID,'head_sha':f.head}}
        f.api.objects['actions/artifacts/323']=row
        f.api.lists['actions/runs/123/artifacts'].append(row)

    def evidence(self):
        def recompute(api, source):
            return deepcopy(self.f.plan), deepcopy(self.f.actual_tree), deepcopy(self.f.source_tree)
        return REUSE.Evidence(self.f.api, self.child, recompute)

    def command(self, *, task=None, runtime=None, proof=None):
        with patch.object(T,'_download',side_effect=lambda api, artifact:self.archives[artifact]):
            return self.evidence().command(proof or {'run_id':123,'run_attempt':1},
                self.task if task is None else task, self.runtime if runtime is None else runtime, 'host')

    def test_success_requires_native_execution_and_digest_bound_command_artifact(self):
        self.assertEqual(self.command(), {'run_id':123,'run_attempt':1})
        gets=[c[1] for c in self.f.api.calls if c[0]=='get']
        self.assertIn('check-suites/789', gets)
        self.assertIn('actions/artifacts/323', gets)
        self.assertGreaterEqual(gets.count('actions/runs/123'),2)

    def test_unrelated_failed_expired_foreign_unmerged_and_nonancestor_sources_are_refused(self):
        mutations = {
            'failed':lambda:self.f.native.update(conclusion='failure'),
            'expired':lambda:self.f.native.update(created_at=(datetime.now(timezone.utc)-timedelta(days=15)).isoformat()),
            'attempt':lambda:self.f.native.update(run_attempt=2),
            'foreign':lambda:self.f.native['repository'].update(id=1),
            'source':lambda:self.f.native.update(head_sha='9'*40),
            'suite':lambda:self.f.api.objects['check-suites/789']['app'].update(id=1),
            'unmerged':lambda:self.f.pr.update(merged=False),
            'nonancestor':lambda:self.f.api.objects[self.compare].update(status='diverged'),
            'tree':lambda:self.f.api.objects['git/commits/'+self.f.regenerated]['tree'].update(sha='9'*40),
            'recipe':lambda:self.f.actual_tree[T.WORKFLOW].update(sha='9'*40),
            'job':lambda:self.f.job_rows[-1].update(conclusion='failure'),
            'host-step':lambda:next(j for j in self.f.job_rows if j['name']=='Host contracts')['steps'][0].update(conclusion='failure'),
        }
        for name in mutations:
            self.setUp(); mutation=mutations[name]
            # Lambdas resolve self dynamically, so each mutation acts on the
            # newly reset independent native fixture.
            mutation(); self.refresh_artifacts()
            with self.subTest(mutation=name), self.assertRaises((ValueError,KeyError)):
                self.command()
        self.setUp()
        with self.assertRaises(KeyError):self.command(proof={'run_id':999,'run_attempt':1})

    def test_input_command_runtime_or_origin_mismatch_cannot_skip_execution(self):
        for mutation in ('key','command','runtime','attempt','reused-origin'):
            self.setUp(); task=deepcopy(self.task); runtime=deepcopy(self.runtime); proof=None
            if mutation=='key':task['reuse_key']='different'
            elif mutation=='command':task['command']=['python','tests/different.py']
            elif mutation=='runtime':runtime['digest']='c'*64
            elif mutation=='attempt':proof={'run_id':123,'run_attempt':2}
            else:
                self.command_row.update(executed=False,origin={'run_id':122,'run_attempt':1});self.refresh_artifacts()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.command(task=task,runtime=runtime,proof=proof)

    def test_matching_absent_or_malformed_runtime_is_never_reusable_evidence(self):
        for runtime in (None, {}, {'schema':2,'digest':'b'*64}, {'schema':1,'digest':'x'*64}):
            self.setUp(); self.command_row['runtime']=runtime;self.refresh_artifacts()
            with self.subTest(runtime=runtime), patch.object(T,'_download',
                    side_effect=lambda api, artifact:self.archives[artifact]), self.assertRaises(ValueError):
                self.evidence().command({'run_id':123,'run_attempt':1},self.task,runtime,'host')

    def test_source_rerun_or_suite_mutation_during_authentication_is_refused(self):
        for endpoint, field, value in [('actions/runs/123','run_attempt',2),
                ('check-suites/789','head_sha','9'*40)]:
            self.setUp(); count=[0]
            def change(row):
                count[0]+=1
                if count[0]>1:row[field]=value
                return row
            self.f.api.hooks[endpoint]=change
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):self.command()

    def test_discovery_follows_flattened_origin_to_original_ancestor(self):
        # An apple-main receipt passed forward to apple-ios can identify the
        # actual original main execution directly, without trusting a chain of
        # copied successful strings as command evidence.
        self.child.update(target='apple-ios',head_ref='apple-main')
        self.assertEqual(self.command(),{'run_id':123,'run_attempt':1})
        with patch.object(T,'_download',side_effect=lambda api,artifact:self.archives[artifact]):
            found=self.evidence().discover([self.task], self.runtime, 'host')
        self.assertEqual(found,{})  # No owning apple-main merge fixture exists.

    def test_discovery_authenticates_the_direct_parent_before_selecting_a_command(self):
        with patch.object(T, '_download', side_effect=lambda api, artifact:self.archives[artifact]):
            found = self.evidence().discover([self.task], self.runtime, 'host')
        self.assertEqual(found, {self.task['id']:{'run_id':123,'run_attempt':1}})

    def test_final_gate_reauthenticates_flattened_original_execution(self):
        self.child.update(target='apple-ios', head_ref='apple-main')
        name=REUSE.artifact_name(self.child, 'host')
        record={'kind':'pr-ci-task-results-v1','context':self.child,'lane':'host','project':'',
            'results':[{**self.command_row,'executed':False,'origin':{'run_id':123,'run_attempt':1}}]}
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('tasks.json',CLI.C.canonical(record))
        raw=stream.getvalue();self.archives[324]=raw
        row={**self.f.api.objects['actions/artifacts/323'],'id':324,'name':name,
            'size_in_bytes':len(raw),'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),
            'url':T.API_ROOT+'/actions/artifacts/324',
            'archive_download_url':T.API_ROOT+'/actions/artifacts/324/zip',
            'workflow_run':{'id':124,'repository_id':CLI.C.REPOSITORY_ID,
                'head_repository_id':CLI.C.REPOSITORY_ID,'head_sha':self.child['head']}}
        self.f.api.objects['actions/artifacts/324']=row
        with patch.object(T,'_download',side_effect=lambda api, artifact:self.archives[artifact]):
            REUSE.verify_current(self.f.api,self.child,self.f.plan,[row],self.evidence().recompute)
        self.f.native['conclusion']='failure'
        with patch.object(T,'_download',side_effect=lambda api, artifact:self.archives[artifact]), self.assertRaises(ValueError):
            REUSE.verify_current(self.f.api,self.child,self.f.plan,[row],self.evidence().recompute)

    def test_missing_parent_discovery_is_an_optional_miss(self):
        self.child['head_ref']='fix/apple-main/unrelated'
        self.assertEqual(self.evidence().discover([self.task],self.runtime,'host'),{})
        self.assertFalse(any(c[1].startswith('commits/') for c in self.f.api.calls if c[0]=='pages'))


class ReuseExecution(unittest.TestCase):
    def test_npm_refreshes_security_data_but_skips_reused_build_and_functional_commands(self):
        f=FIXTURE.CommandTests();f.setUp()
        task={'id':'npm:example','kind':'npm','command':[['npm','ci'],['npm','audit'],
            ['npm','run','build'],['npm','test']], 'missing_inputs':[], 'reuse_key':'key','setup':[]}
        plan={**f.plan,'tasks':[task]}
        with tempfile.TemporaryDirectory(prefix='reuse-execute-') as tmp:
            candidate=f.candidate(Path(tmp)/'candidate')
            with patch.object(CLI,'selection',return_value=plan),patch.object(CLI.C,'bookend',return_value={}),\
                    patch.object(REUSE,'observed_runtime',return_value={'schema':1,'digest':'a'*64}),\
                    patch.object(REUSE.Evidence,'discover',return_value={'npm:example':{'run_id':122,'run_attempt':1}}),\
                    patch.object(RUNNER,'run',return_value=0) as run,patch.dict(os.environ,f.env):
                result=CLI.execute(candidate,plan,'npm','example',[],context=f.context)
            self.assertEqual([r.args[1][-2:] for r in run.call_args_list],[['npm','ci'],['npm','audit']])
            self.assertTrue(all(r.kwargs['network'] for r in run.call_args_list))
            self.assertFalse(result['results'][0]['executed'])

    def test_missing_parent_proof_executes_all_commands(self):
        f=FIXTURE.CommandTests();f.setUp()
        task={'id':'suite:one','kind':'host','command':['python','tests/one.py'],
            'missing_inputs':[],'reuse_key':'key','setup':[]}
        plan={**f.plan,'tasks':[task]}
        with tempfile.TemporaryDirectory(prefix='reuse-execute-') as tmp:
            candidate=f.candidate(Path(tmp)/'candidate')
            with patch.object(CLI,'selection',return_value=plan),patch.object(CLI.C,'bookend',return_value={}),\
                    patch.object(REUSE,'observed_runtime',return_value={'schema':1,'digest':'a'*64}),\
                    patch.object(REUSE.Evidence,'discover',side_effect=ValueError('missing evidence')),\
                    patch.object(RUNNER,'run',return_value=0) as run,patch.dict(os.environ,f.env):
                result=CLI.execute(candidate,plan,'host','',[],context=f.context)
            self.assertEqual(run.call_count,1)
            self.assertTrue(result['results'][0]['executed'])


class RuntimeIdentity(unittest.TestCase):
    def test_relocated_equal_tools_match_but_real_bytes_and_interpreter_inputs_do_not(self):
        with tempfile.TemporaryDirectory(prefix='reuse-runtime-') as tmp:
            left,right=[Path(tmp)/name for name in ('original','relocated')]
            for root in (left,right):
                (root/'bin').mkdir(parents=True)
                (root/'bin/tool').write_text('same tool bytes\n')
                (root/'module.py').write_text('VALUE = 1\n')
                (root/'pyvenv.cfg').write_text('home = /usr/bin\nversion = 3.12.15\n'
                    + 'command = /usr/bin/python -m venv ' + str(root) + '\n')
                (root/'tool-link').symlink_to(root/'bin/tool')
            first=REUSE.observed_runtime([str(left)])
            self.assertEqual(first, REUSE.observed_runtime([str(right)]))
            (right/'module.py').write_text('VALUE = 2\n')
            self.assertNotEqual(first, REUSE.observed_runtime([str(right)]))
            (right/'module.py').write_text('VALUE = 1\n')
            config=right/'pyvenv.cfg'
            config.write_text(config.read_text().replace('/usr/bin','/other/interpreter'))
            self.assertNotEqual(first, REUSE.observed_runtime([str(right)]))


if __name__=='__main__':unittest.main()
