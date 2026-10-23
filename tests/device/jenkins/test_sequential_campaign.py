#!/usr/bin/env python3
"""Host-only campaign orchestration counters; these grant no device acceptance."""
from __future__ import annotations

from contextlib import redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
DEVICE = HERE.parent
spec = importlib.util.spec_from_file_location('sequential_campaign', HERE / 'sequential_campaign.py')
campaign = importlib.util.module_from_spec(spec)
spec.loader.exec_module(campaign)
REVISION = 'b' * 40


class SequentialCampaignTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='overte-campaign-host-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        device = self.source / 'tests/device'
        device.mkdir(parents=True)
        for name in ('run.py', 'adapter_client.py', 'contracts.py', 'execution_identity.py',
                     'capabilities.json', 'run_control_plane_tests.py'):
            shutil.copyfile(DEVICE / name, device / name)
        (device / 'probe.py').write_text('raise SystemExit(0)\n')
        self.catalog = device / 'catalog.json'
        self.catalog.write_text(json.dumps({'schemaVersion': 1, 'modules': [
            dict(id=name, description='Host orchestration fixture', command=['probe.py', name],
                 suites=['all'], requires=[], timeoutSeconds=5)
            for name in ('first', 'second')]}))
        self.policy = device / 'policy.json'
        self.policy.write_text('{}')
        (self.root / 'archive').write_bytes(b'controlled source archive fixture')
        (self.root / 'apk').write_bytes(b'controlled package fixture; not installable')
        (self.root / 'adapter.json').write_text('{}')
        (self.root / 'environment.json').write_text(json.dumps({'schemaVersion': 1, 'environment': {
            'OVERTE_DEVICE_TARGET_SELECTOR': 'private-selector-never-publish'}}))
        files = {str(p.relative_to(self.source)): campaign.digest(p)
                 for p in self.source.rglob('*') if p.is_file()}
        self.receipt = {'build': {'sourceRevision': REVISION,
            'apkSha256': campaign.digest(self.root / 'apk'),
            'sourceArchiveSha256': campaign.digest(self.root / 'archive'),
            'sourceFilesSha256': {'tests/device/run.py': files['tests/device/run.py']}},
            'verifiedPackage': {'sha256': campaign.digest(self.root / 'apk'),
                'source_revision': REVISION, 'debuggable': True, 'signature_verified': True}}
        (self.root / 'receipt.json').write_text(json.dumps(self.receipt))
        self.manifest = dict(campaignVersion=1, sourceRevision=REVISION, sourceRoot='source',
            sourceArchive=self.reference('archive'), sourceFiles=files, apk=self.reference('apk'),
            buildReceipt=self.reference('receipt.json'),
            catalog=self.reference('tests/device/catalog.json', self.source),
            tabletPolicy=self.reference('tests/device/policy.json', self.source),
            runs=[dict(id=name, setup=[], adapter=self.reference('adapter.json'),
                       environment=self.reference('environment.json')) for name in ('first', 'second')])
        self.calls = []
        self.stage = self.root / 'workspace/campaign-results'

    def reference(self, path, root=None):
        return {'path': path, 'sha256': campaign.digest((root or self.root) / path)}

    def make(self, executor=None):
        manifest = self.root / 'incoming/manifest/artifact'
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(self.manifest))
        return campaign.Campaign(self.root, campaign.digest(manifest), REVISION,
                                 stage=self.stage, executor=executor or self.executor)

    def executor(self, argv, cwd, env, timeout, log):
        output = Path(argv[argv.index('--output-dir') + 1])
        catalog = json.loads(Path(argv[argv.index('--catalog') + 1]).read_text())
        names = [row['id'] for row in catalog['modules']]
        self.calls.append(names[-1])
        self.assertEqual(cwd, self.source)
        self.assertEqual(env['OVERTE_DEVICE_CONTINUE_AFTER_MODULE_ERROR'], '1')
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual([argv[i + 1] for i, arg in enumerate(argv) if arg == '--required-setup'], names[:-1])
        for row in catalog['modules']:
            self.assertEqual(row['command'][:2], [sys.executable, str(self.source / 'tests/device/probe.py')])
        output.mkdir()
        campaign.atomic_json(output / 'summary.json', {'schemaVersion': 1,
            'results': [dict(id=name, status='passed') for name in names]})
        (output / 'junit.xml').write_text('<testsuite/>')
        campaign.atomic_json(output / 'run-manifest.json', {'actualHostFixtureInvocation': names})
        identity = dict(contract='overte-sh004-result-v1', sourceRevision=REVISION,
                        artifactSha256=self.manifest['apk']['sha256'])
        for key, name in [('runSha256', 'run-manifest.json'), ('summarySha256', 'summary.json'),
                          ('junitSha256', 'junit.xml')]:
            identity[key] = campaign.digest(output / name)
        campaign.atomic_json(output / 'result-identity.json', identity)
        log.write_text('private-selector-never-publish raw diagnostic\n')
        return dict(returncode=0, timedOut=False, ownedChildrenLeaked=False)

    def read_summary(self):
        return json.loads((self.stage / 'summary.json').read_text())

    def test_source_bound_targets_once_setup_is_a_required_prefix_and_output_is_sanitized(self):
        self.manifest['runs'][1]['setup'] = ['first']
        instance = self.make()
        self.assertEqual(instance.run(), 0)
        self.assertEqual(self.calls, ['first', 'second'])
        value = self.read_summary()
        self.assertEqual(value['plannedTargets'], 2)
        self.assertEqual(value['results'][1]['setup'], [{'id': 'first', 'status': 'passed'}])
        self.assertEqual(len(ET.parse(self.stage / 'junit.xml').findall('testcase')), 2)
        for name in ('summary.json', 'junit.xml'):
            self.assertNotIn('private-selector', (self.stage / name).read_text())
            self.assertNotIn(str(self.root), (self.stage / name).read_text())

    def test_hash_receipt_and_inventory_fail_before_any_dispatch(self):
        # Each subcase has a fresh owned campaign; no previous verdict is reused.
        for mutation in ('apk', 'archive', 'source', 'receipt', 'inventory'):
            with self.subTest(mutation=mutation):
                if mutation != 'apk':
                    self.tearDownFixture()
                    self.setUp()
                if mutation == 'receipt':
                    self.receipt['build']['sourceRevision'] = 'c' * 40
                    (self.root / 'receipt.json').write_text(json.dumps(self.receipt))
                    self.manifest['buildReceipt'] = self.reference('receipt.json')
                elif mutation == 'inventory':
                    self.manifest['runs'].pop()
                instance = self.make()
                if mutation in ('apk', 'archive'):
                    (self.root / mutation).write_bytes(b'foreign late bytes')
                elif mutation == 'source':
                    (self.source / 'tests/device/probe.py').write_text('foreign source')
                self.assertEqual(instance.run(), 1)
                self.assertEqual(self.calls, [])
                self.assertTrue(all(row['status'] == 'error' and not row['attempted']
                                    for row in self.read_summary()['results']))

    def tearDownFixture(self):
        self.temporary.cleanup()

    def test_missing_summary_and_bad_result_identity_do_not_block_next_target(self):
        for corruption in ('missing', 'foreign', 'changed', 'skipped', 'cleanup'):
            with self.subTest(corruption=corruption):
                if corruption != 'missing':
                    self.tearDownFixture()
                    self.setUp()
                def execute(argv, cwd, env, timeout, log):
                    outcome = self.executor(argv, cwd, env, timeout, log)
                    if self.calls[-1] == 'first':
                        output = Path(argv[argv.index('--output-dir') + 1])
                        if corruption == 'missing':
                            (output / 'summary.json').unlink()
                        elif corruption == 'foreign':
                            identity = json.loads((output / 'result-identity.json').read_text())
                            identity['sourceRevision'] = 'd' * 40
                            campaign.atomic_json(output / 'result-identity.json', identity)
                        else:
                            value = json.loads((output / 'summary.json').read_text())
                            if corruption == 'skipped':
                                value['results'][0]['status'] = 'skipped'
                            elif corruption == 'cleanup':
                                value['results'].append(dict(id='target-cleanup', status='error'))
                            else:
                                value['changedAfterIdentity'] = True
                            campaign.atomic_json(output / 'summary.json', value)
                    return outcome
                instance = self.make(execute)
                self.assertEqual(instance.run(), 1)
                self.assertEqual(self.calls, ['first', 'second'])
                self.assertEqual([row['status'] for row in self.read_summary()['results']], ['error', 'passed'])
                if corruption == 'missing':
                    self.assertEqual(self.read_summary()['results'][0]['reason'], 'missing-summary')

    def test_failed_required_setup_is_never_graded_as_target_success(self):
        self.manifest['runs'][1]['setup'] = ['first']
        def execute(argv, cwd, env, timeout, log):
            outcome = self.executor(argv, cwd, env, timeout, log)
            if self.calls[-1] == 'second':
                output = Path(argv[argv.index('--output-dir') + 1])
                campaign.atomic_json(output / 'summary.json', {'schemaVersion': 1, 'results': [
                    dict(id='first', status='failed'), dict(id='second', status='skipped')]})
                outcome['returncode'] = 1
            return outcome
        self.assertEqual(self.make(execute).run(), 1)
        row = self.read_summary()['results'][1]
        self.assertEqual((row['status'], row['reason']), ('error', 'setup-not-passed'))

    def test_per_target_directory_failure_still_attempts_next_target(self):
        instance = self.make()
        (instance.private / 'first').write_text('controlled collision')
        self.assertEqual(instance.run(), 1)
        self.assertEqual(self.calls, ['second'])
        self.assertEqual([row['status'] for row in self.read_summary()['results']], ['error', 'passed'])

    def test_late_source_change_rejects_current_result_and_prevents_later_dispatch(self):
        def execute(argv, cwd, env, timeout, log):
            outcome = self.executor(argv, cwd, env, timeout, log)
            (self.source / 'tests/device/probe.py').write_text('foreign source after actual result')
            return outcome
        self.assertEqual(self.make(execute).run(), 1)
        self.assertEqual(self.calls, ['first'])
        self.assertEqual([row['status'] for row in self.read_summary()['results']], ['error', 'error'])
        self.assertEqual([row['attempted'] for row in self.read_summary()['results']], [True, False])

    def test_failed_global_admission_stages_error_without_inventing_target_attempts(self):
        self.make()
        result = subprocess.run([sys.executable, '-B', str(HERE / 'sequential_campaign.py'),
            '--campaign-root', str(self.root), '--manifest-sha256', '0' * 64,
            '--source-revision', REVISION], env=os.environ | {'WORKSPACE': str(self.stage.parent)},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        value = self.read_summary()
        self.assertTrue(value['admissionFailed'])
        self.assertEqual(value['plannedTargets'], 0)
        self.assertEqual(value['results'][0]['status'], 'error')
        self.assertFalse(value['results'][0]['attempted'])
        self.assertEqual(ET.parse(self.stage / 'junit.xml').getroot().get('errors'), '1')
        self.assertNotIn(str(self.root), result.stdout + result.stderr)

    @unittest.skipUnless(os.name == 'posix' and os.geteuid() != 0, 'Real owner permission-denial counter')
    def test_public_write_denial_continues_all_targets_stays_red_and_preserves_complete_fallback(self):
        for mode in ('recovers', 'unavailable', 'unsafe-path'):
            with self.subTest(mode=mode):
                if mode != 'recovers':
                    self.tearDownFixture()
                    self.setUp()
                def execute(argv, cwd, env, timeout, log):
                    outcome = self.executor(argv, cwd, env, timeout, log)
                    if self.calls[-1] == 'first':
                        self.stage.chmod(0)
                    elif mode == 'recovers':
                        self.stage.chmod(0o700)
                    return outcome
                instance = self.make(execute)
                if mode == 'unsafe-path':
                    self.stage.mkdir(parents=True)
                    foreign = self.root / 'must-not-overwrite.xml'
                    foreign.write_text('foreign original')
                    (self.stage / 'junit.xml').symlink_to(foreign)
                    with self.assertRaisesRegex(campaign.CampaignError, 'unsafe-junit-output'):
                        instance.run()
                    self.assertEqual(self.calls, [])
                    self.assertEqual(instance.staging_errors, 0)
                    self.assertEqual(foreign.read_text(), 'foreign original')
                    continue
                console = io.StringIO()
                try:
                    with redirect_stderr(console):
                        self.assertEqual(instance.run(), 1)
                finally:
                    self.stage.chmod(0o700)
                self.assertEqual(self.calls, ['first', 'second'])
                private = json.loads((instance.private / 'progress.json').read_text())
                self.assertEqual(private['status'], 'failed')
                self.assertGreaterEqual(private['publicStagingErrors'], 1)
                self.assertEqual([row['status'] for row in private['results']], ['passed', 'passed'])
                self.assertTrue(all(row['attempted'] for row in private['results']))
                fallback = [line for line in console.getvalue().splitlines()
                            if line.startswith('CAMPAIGN_SANITIZED_FALLBACK ')]
                self.assertEqual(len(fallback), 1)
                self.assertEqual(json.loads(fallback[0].split(' ', 1)[1]), private)
                self.assertNotIn('private-selector', console.getvalue())
                self.assertNotIn(str(self.root), console.getvalue())
                if mode == 'recovers':
                    self.assertEqual(self.read_summary(), private)
                    junit = ET.parse(self.stage / 'junit.xml').getroot()
                    self.assertEqual(junit.get('errors'), '1')
                    self.assertIsNotNone(junit.find("testcase[@name='campaign-public-staging']/error"))

    @unittest.skipUnless(sys.platform.startswith('linux') and hasattr(os, 'fork'), 'Linux subreaper contract')
    def test_real_escaped_orphan_missing_summary_is_cleaned_and_next_target_runs(self):
        # A real child double-forks/setsid and outlives its runner. No target or
        # adapter is involved; the existing standalone command_owner adopts it.
        child = self.root / 'orphan.py'
        pidfile = self.root / 'orphan.pid'
        child.write_text('''import os, pathlib, time
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        pathlib.Path(os.environ['HOST_ORPHAN_PID']).write_text(str(os.getpid()))
        time.sleep(60)
    os._exit(0)
while not pathlib.Path(os.environ['HOST_ORPHAN_PID']).exists():
    time.sleep(.01)
os._exit(0)
''')
        observed = []
        def execute(argv, cwd, env, timeout, log):
            if not self.calls:
                self.calls.append('first')
                result = campaign.execute([sys.executable, str(child)], cwd,
                    env | {'HOST_ORPHAN_PID': str(pidfile)}, 5, log)
                observed.append(result)
                self.assertIsNone(campaign.process_identity(int(pidfile.read_text())))
                return result
            return self.executor(argv, cwd, env, timeout, log)
        self.assertEqual(self.make(execute).run(), 1)
        self.assertTrue(observed[0]['ownedChildrenLeaked'])
        self.assertFalse(observed[0]['timedOut'])
        self.assertEqual(self.calls, ['first', 'second'])
        self.assertEqual([row['status'] for row in self.read_summary()['results']], ['error', 'passed'])
        self.assertEqual(self.read_summary()['results'][0]['reason'], 'runner-left-owned-children')


if __name__ == '__main__':
    unittest.main(verbosity=2)
