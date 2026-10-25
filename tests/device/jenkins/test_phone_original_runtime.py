"""Run the actual worker, runner and original modules against a no-DUT adapter.

Admission and Tutorial observations are explicit host fixtures. Execution is
the unmodified run.py main, its real subprocess protocol and original module
scripts. No Jenkins, Appium, ADB, network or product application is involved.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[2]
sys.path.insert(0, str(HERE))
import phone_worker as worker


FAKE_ADAPTER = r'''import argparse,json,os,pathlib
p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('--trace',required=True);p.add_argument('--artifact-sha',required=True);p.add_argument('--source',required=True);p.add_argument('--sealed',required=True);p.add_argument('action');p.add_argument('--target');p.add_argument('--operation');p.add_argument('--arguments',default='{}');a=p.parse_args()
assert a.sealed=='original-prefix-preserved'
with open(a.trace,'a')as f:f.write(json.dumps({'action':a.action,'operation':a.operation,'module':os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''),'sealed':a.sealed})+'\n')
path=pathlib.Path(a.state);state=json.loads(path.read_text())if path.exists()else{'running':False,'launches':0}
caps=sorted(set(['app.foreground','app.launch','app.process','app.stop']+json.loads(os.environ.get('PHONE_FAKE_EXTRA_CAPABILITIES_JSON','[]'))))
if a.action=='discover':result=[{'selector':'host-contract','displayName':'No-DUT contract','platform':'android','physical':True,'capabilities':caps}]
elif a.action=='describe':result={'model':'No-DUT transport','executionIdentity':{'schemaVersion':1,'sourceRevision':a.source,'artifactSha256':('f'*64 if os.environ.get('PHONE_FAKE_BAD_IDENTITY')=='1'else a.artifact_sha),'installedCandidateVerified':True}}
elif a.action=='cleanup':state['running']=False;result={'performed':True}
elif a.action=='invoke':
 if a.operation=='app.launch':
  if not state['running']:state['launches']+=1
  state['running']=True;result={'launched':True}
 elif a.operation=='app.stop':state['running']=False;result={'stopped':True}
 elif a.operation=='app.process':result={'running':state['running'],'identity':('process-'+str(state['launches']))if state['running']else None}
 elif a.operation=='app.foreground':result={'foreground':state['running']}
 else:raise AssertionError('unexpected fake operation')
else:raise AssertionError('unexpected fake action')
path.write_text(json.dumps(state));print(json.dumps(result))
'''

FIXTURE = '''import json
def prepare(context):
 context.fixture_prepare_seen=True
 return {}
def finish(context):
 (context.run_root/'fixture-finished.json').write_text(json.dumps({'finished':True}))
'''

TUTORIAL = '''import json,time
def prepare_tutorial(context):
 assert context.fixture_prepare_seen
 path=context.run_root/'tutorial-count.json'
 assert not path.exists(),'preparation replayed between dependent modules'
 path.write_text(json.dumps({'calls':1}))
 rows=[]
 for n in range(3):
  if n:time.sleep(.26)
  rows.append({'runNonce':context.nonce,'observedEpochMs':time.time_ns()//1000000,
   'processIdentity':'host-tutorial-process','sceneUrl':'file:///~/serverless/tutorial.json',
   'protocol':'file','serverless':True,'connected':False,'entityCount':39,
   'feet':[1985.26,1994.1357422,1994.25],'inAir':False,'flying':False,'velocity':[0,.003,0]})
 return rows
'''


class OriginalRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.deployment = self.root / 'deployment'; self.deployment.mkdir()
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.run_root = self.root / 'overte-pixel6a-41'
        self.trace = self.root / 'adapter-trace.jsonl'
        self.write('fake_adapter.py', FAKE_ADAPTER)
        self.write('fixture.py', FIXTURE)
        self.write('tutorial.py', TUTORIAL)
        candidate = self.write('candidate.bin', b'host-contract-bytes-never-installed')
        candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
        catalog = json.loads((SOURCE / 'tests/device/catalog.json').read_bytes())
        by_id = {row['id']: row for row in catalog['modules']}
        self.ids = ['launch-smoke', 'app-restart', 'idle-soak']
        self.plan = {'moduleIds': self.ids, 'setupModuleIds': ['launch-smoke'],
                     'requiredCapabilities': sorted({cap for identifier in self.ids for cap in by_id[identifier]['requires']})}
        inventory = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in (
            'tests/device/run.py', 'tests/device/modules/launch_smoke.py',
            'tests/device/modules/app_restart.py', 'tests/device/modules/idle_soak.py')}
        self.write('source-inventory.json', inventory)
        publication = {'schemaVersion': 1, 'literalFiles': {name: {'required': True, 'maxBytes': limit}
            for name, limit in [('summary.json', 262144), ('junit.xml', 262144), ('diagnostic-events.safe.jsonl', 16777216)]},
            'logDirectories': [], 'maxFiles': 64, 'maxTotalBytes': 268435456}
        # export_public validates the sealed directory as well as payloads.
        # This is the deployed standard-job export policy, not the historical
        # publication_watcher consumer policy, which reserves these names.
        for name in ('artifact-index.json', 'debug-state.json'):
            publication['literalFiles'][name] = {'required': False, 'maxBytes': 1048576}
        policy = self.write('publication.json', publication)
        config = {'domainRequiredModules': [], 'privateValues': [],
                  'publicationPolicy': {'path': str(policy), 'sha256': hashlib.sha256(policy.read_bytes()).hexdigest()}}
        refs = {'candidate': candidate, 'originalRun': SOURCE / 'tests/device/run.py',
                'adapterManifest': self.write('adapter.json', {'schemaVersion': 1, 'id': 'host-fake', 'command': [
                    str(self.deployment / 'fake_adapter.py'), '--state', str(self.root / 'state.json'),
                    '--trace', str(self.trace), '--artifact-sha', candidate_sha, '--source', 'a' * 40,
                    '--sealed', 'original-prefix-preserved']}),
                'environment': self.write('environment.json', {'schemaVersion': 1, 'environment': {
                    'OVERTE_DEVICE_LAUNCH_SETTLE_SECONDS': '0', 'OVERTE_DEVICE_IDLE_SECONDS': '1',
                    'OVERTE_DEVICE_SAMPLE_SECONDS': '1', 'OVERTE_DEVICE_LOCK_ROOT': str(self.root / 'locks')}}),
                'targets': self.write('targets.json', {'targets': [{'selector': 'host-contract', 'platform': 'android',
                    'physical': True, 'enabled': True, 'capabilities': {'appium:noReset': True,
                    'appium:autoLaunch': False, 'appium:adbPort': 5037}}]}),
                'debugTemplate': self.write('debug.json', config), 'fixtureHelper': self.deployment / 'fixture.py',
                'fixtureConfig': self.write('fixture.json', {}), 'tutorialHelper': self.deployment / 'tutorial.py',
                'tabletPolicy': SOURCE / 'tests/device/policies/android-phone-flat-touch.json'}
        self.admission = SimpleNamespace(run_root=self.run_root, source=SOURCE, deployment=self.deployment,
            references=refs, catalog=catalog, plan=self.plan,
            manifest={'client': {'revision': 'a' * 40}, 'candidate': {'sha256': candidate_sha},
                      'source': {'inventory': {'path': 'source-inventory.json',
                        'sha256': hashlib.sha256((self.deployment / 'source-inventory.json').read_bytes()).hexdigest()}}},
            revalidate=lambda: None)
        self.environment = {'WORKSPACE': str(self.workspace), 'BUILD_NUMBER': '41',
            'OVT_PHONE_PUBLIC_ROOT': str(self.workspace / 'pixel-job-public/41')}
        self.holds = []
        self.old_umask = os.umask(0o077)
        self.addCleanup(os.umask, self.old_umask)

    def write(self, name, value):
        path = self.deployment / name
        raw = value if isinstance(value, bytes) else value.encode() if isinstance(value, str) else json.dumps(value).encode()
        path.write_bytes(raw); path.chmod(0o600)
        return path

    def run_worker(self):
        actual_load = worker.load
        def loaded(path, name):
            module = actual_load(path, name)
            if name == '_phone_run_debug':
                # Replace only the endless live hold wait with an explicit
                # host-fixture disposition. Original run.py main is untouched.
                def hold(policy, reason, **kwargs):
                    self.holds.append(reason)
                    policy.cleanup_authorized = True
                    policy.record_exception(RuntimeError(reason), reason)
                    raise module.DebugCleanupRequested()
                module.Policy.hold = hold
            return module
        with patch.dict(os.environ, self.environment), patch.object(worker, 'load', loaded), \
                patch.object(socket, 'socket', side_effect=AssertionError('no network')):
            return worker.run(self.admission)

    def trace_rows(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def test_actual_runner_original_modules_adapter_arguments_identity_and_mapping(self):
        result = self.run_worker()
        if result != 0:
            module_log = self.run_root / 'debug-private/module-launch-smoke.stdout-stderr.private.log'
            exceptions = [json.loads(path.read_text())['traceback'] for path in
                          (self.run_root / 'debug-private').glob('exception-*.private.json')]
            self.fail('Worker failed before completing actual original modules: ' + str(self.holds)
                      + '\n' + (self.run_root / 'runtime.private.log').read_text()[-10000:]
                      + '\n' + (module_log.read_text() if module_log.exists() else '')
                      + '\n' + '\n'.join(exceptions))
        self.assertEqual(self.holds, [])
        summary = json.loads((self.run_root / 'actual/summary.json').read_bytes())
        self.assertEqual([row['id'] for row in summary['results']], self.ids)
        self.assertTrue(all(row['status'] == 'passed' for row in summary['results']))
        self.assertTrue((self.run_root / 'actual/result-identity.json').is_file())
        self.assertEqual(json.loads((self.run_root / 'tutorial-count.json').read_text()), {'calls': 1})
        selected = json.loads((self.run_root / 'catalog.private.json').read_text())
        for row in selected['modules']:
            self.assertTrue(Path(row['command'][0]).is_relative_to(SOURCE / 'tests/device/modules'))
        trace = self.trace_rows()
        self.assertTrue(all(row['sealed'] == 'original-prefix-preserved' for row in trace))
        self.assertGreaterEqual(sum(row['action'] == 'describe' for row in trace), 2)
        self.assertEqual(sum(row['operation'] == 'app.stop' for row in trace), 1)
        self.assertTrue((self.run_root / 'fixture-finished.json').is_file())
        self.assertTrue((self.workspace / 'pixel-job-public/41/EXPORT_READY').is_file())

    def test_original_runner_rejects_invalid_setup_prefix_before_adapter_input(self):
        self.plan['setupModuleIds'] = ['app-restart']
        self.assertEqual(self.run_worker(), worker.RELEASED)
        self.assertTrue(self.holds)
        self.assertFalse(self.trace_rows())
        errors = [json.loads(path.read_text())['traceback'] for path in (self.run_root / 'debug-private').glob('exception-*.private.json')]
        self.assertTrue(any('required setup ids must form the selected catalog prefix' in error for error in errors))

    def test_original_identity_gate_prevents_modules_and_tutorial_when_claim_differs(self):
        environment = self.admission.references['environment']
        value = json.loads(environment.read_bytes()); value['environment']['PHONE_FAKE_BAD_IDENTITY'] = '1'
        environment.write_text(json.dumps(value))
        self.assertEqual(self.run_worker(), worker.RELEASED)
        self.assertFalse((self.run_root / 'tutorial-count.json').exists())
        self.assertFalse(any(row['action'] == 'invoke' for row in self.trace_rows()))
        self.assertIn('RUNNER_FAILURE_BEFORE_CLEANUP', self.holds)

    def test_actual_tablet_parser_receives_policy_before_unsupported_fake_transport(self):
        by_id = {row['id']: row for row in self.admission.catalog['modules']}
        self.plan['moduleIds'] = ['launch-smoke', 'tablet-e2e']
        required = sorted({cap for identifier in self.plan['moduleIds'] for cap in by_id[identifier]['requires']})
        self.plan['requiredCapabilities'] = required
        environment = self.admission.references['environment']
        value = json.loads(environment.read_bytes())
        value['environment']['PHONE_FAKE_EXTRA_CAPABILITIES_JSON'] = json.dumps(required)
        environment.write_text(json.dumps(value))
        # The original Tablet module intentionally reaches an unsupported
        # fake-only operation. Its product assertions are never called PASS.
        self.assertEqual(self.run_worker(), worker.RELEASED)
        self.assertIn('MODULE_NONPASS', self.holds)
        self.assertTrue((self.run_root / 'actual/modules/launch-smoke/metrics.json').is_file())
        self.assertEqual(json.loads((self.run_root / 'tutorial-count.json').read_text()), {'calls': 1})
        self.assertTrue(any(row['operation'] == 'probe.snapshot' and '/tablet-e2e' in row['module']
                            for row in self.trace_rows()))
        module_log = (self.run_root / 'debug-private/module-tablet-e2e.stdout-stderr.private.log').read_text()
        self.assertNotIn('requires --tablet-policy', module_log)


if __name__ == '__main__':
    unittest.main(verbosity=2)
