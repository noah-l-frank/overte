"""Host-only renderer, request, artifact-scope and pinned-bootstrap contracts."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import phone_job as job
from phone_selection import build_index, select_plan
CATALOG = HERE.parent / 'catalog.json'


def descriptor(root='/owned/deployment'):
    return dict(controllerRoot=root, controllerManifestSha256='b' * 64,
        agentLabel=job.AGENT, deviceResource=job.RESOURCE,
        liveBindings=dict(bridgeRelativePath='tools/phone_live.py', bridgeSha256='a' * 64,
                          manifestRelativePath='deployment.private.json'))


class PhoneJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = build_index(CATALOG)

    def test_groovy_literal_escaping_roundtrips_newlines_quotes_and_backslashes(self):
        import ast
        for value in ('line1\nline2', "single'quote", r'path\value', '$literal', 'tab\tcarriage\r'):
            self.assertEqual(value, ast.literal_eval(job._quote(value)))
        script = job.render_pipeline(self.index, descriptor())
        self.assertIn("name ==~ '(?:", script)

    def test_every_ui_selection_is_an_exact_python_precomputed_plan(self):
        for key, plan in self.index['plans'].items():
            request = dict(TEST_SCOPE=plan['scope'])
            arguments = dict(scope=plan['scope'])
            if plan['scope'] == 'feature-area':
                request['FEATURE_AREA'] = plan['featureArea']; arguments['feature_area'] = plan['featureArea']
            if plan['scope'] == 'single-test':
                request['TEST_CASE'] = plan['testCase']; arguments['test_case'] = plan['testCase']
            self.assertEqual(key, job.selection_key(self.index, request))
            self.assertEqual(plan, select_plan(self.index, **arguments))

    def test_only_absent_values_receive_declared_safe_plan_defaults(self):
        self.assertEqual(job.DEFAULTS, job.normalize_request(self.index, {}))
        self.assertEqual(job.DEFAULTS, job.normalize_request(self.index, dict.fromkeys(job.DEFAULTS)))
        self.assertEqual('readiness', job.selection_key(self.index, {}))
        for key in job.DEFAULTS:
            for invalid in ('', 'unknown', False, 0, {}, '$(touch /tmp/foreign)', 'live\n'):
                with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                    job.normalize_request(self.index, {key: invalid})
        with self.assertRaises(ValueError):
            job.normalize_request(self.index, {'PRIVATE_TARGET': 'foreign'})

    def test_ui_irrelevant_dimensions_do_not_become_extra_selection_arguments(self):
        request = job.DEFAULTS | dict(TEST_SCOPE='single-test', TEST_CASE='domain-enter', FEATURE_AREA='audio')
        self.assertEqual('single-test:domain-enter', job.selection_key(self.index, request))
        self.assertEqual(['launch-smoke', 'domain-enter'], self.index['plans'][job.selection_key(self.index, request)]['moduleIds'])

    def test_embedded_index_is_chunked_pinned_and_matches_the_real_catalog(self):
        script = job.render_pipeline(self.index, descriptor())
        section = script.split('String encoded = [', 1)[1].split("].join('')", 1)[0]
        chunks = re.findall(r"'([A-Za-z0-9+/=]+)'", section)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(value) <= job.CHUNK_BYTES for value in chunks))
        raw = base64.b64decode(''.join(chunks), validate=True)
        self.assertEqual(self.index, json.loads(raw))
        self.assertIn(hashlib.sha256(raw).hexdigest(), script)
        selection = script.split('String phoneSelectionJson', 1)[1].split('@NonCPS', 1)[0]
        self.assertIn('index.plans[key]', selection)
        self.assertNotIn('moduleIds.collect', selection)
        self.assertNotIn('moduleIds.sort', selection)

    def test_plan_stage_has_no_agent_shell_lock_workspace_or_device_acquisition(self):
        script = job.render_pipeline(self.index, descriptor())
        pipeline = script.split('\npipeline {', 1)[1]
        self.assertTrue(pipeline.lstrip().startswith('agent none'))
        plan = pipeline.split("stage('Selection plan')", 1)[1].split("stage('Live execution')", 1)[0]
        for forbidden in ('node(', 'agent {', 'lock(', 'sh(', 'writeFile', 'readFile', 'checkout', 'archiveArtifacts'):
            self.assertNotIn(forbidden, plan)
        self.assertIn('when { beforeAgent true;', pipeline)
        self.assertIn("agent { label 'overte-device-pixel6a' }", pipeline)
        self.assertIn("lock(resource: 'android-device-01')", pipeline)

    def test_parsed_json_never_crosses_suspending_pipeline_steps(self):
        script = job.render_pipeline(self.index, descriptor())
        helpers, pipeline = script.split('\npipeline {', 1)
        self.assertNotIn('JsonSlurper', pipeline)
        self.assertIn('@NonCPS\nString phoneSelectionJson', helpers)
        self.assertIn('@NonCPS\nMap normalizedPhoneRequest', helpers)
        self.assertIn('String plan = phoneSelectionJson', pipeline)
        self.assertIn('JsonOutput.prettyPrint(JsonOutput.toJson(', helpers)
        self.assertNotIn('JsonSlurper()', helpers)

    def test_publication_is_only_the_own_active_standard_build_archive(self):
        script = job.render_pipeline(self.index, descriptor())
        method = script.split('void publishPhonePlan', 1)[1].split('\npipeline {', 1)[0]
        for required in ("run.parent.fullName != 'overte-pixel6a'", 'run.number != expectedBuild',
                         '!run.isBuilding()', 'jenkins.model.StandardArtifactManager',
                         "resolve('selection-plan.json')", 'LinkOption.NOFOLLOW_LINKS',
                         'StandardOpenOption.CREATE_NEW', 'Files.readAllBytes(output)'):
            self.assertIn(required, method)
        public = script.split('String phoneSelectionJson', 1)[1].split('void publishPhonePlan', 1)[0]
        self.assertNotIn('/owned/deployment', public)
        self.assertNotIn('liveBindings', public)
        self.assertNotIn('controllerRoot', public)

    def test_xml_and_pipeline_parameter_choices_share_one_source(self):
        xml = ET.fromstring(job.render_job_xml(self.index, descriptor()))
        actual = {}
        for row in xml.findall('./properties/hudson.model.ParametersDefinitionProperty/parameterDefinitions/hudson.model.ChoiceParameterDefinition'):
            actual[row.findtext('name')] = [node.text for node in row.findall('./choices/a/string')]
        self.assertEqual(job.parameter_choices(self.index), actual)
        self.assertEqual(['plan', 'live'], actual['EXECUTION'])
        self.assertEqual(['debug-hold'], actual['FAILURE_POLICY'])
        self.assertEqual('world-navigation', actual['FEATURE_AREA'][0])
        self.assertEqual('domain-enter', actual['TEST_CASE'][0])
        self.assertEqual('false', xml.findtext('./definition/sandbox'))
        self.assertEqual(job.render_pipeline(self.index, descriptor()), xml.findtext('./definition/script'))

    def test_private_unbounded_or_unregistered_public_index_is_rejected(self):
        cases = []
        for change in ('path', 'extra', 'qualified', 'oversize'):
            index = deepcopy(self.index)
            module = index['plans']['readiness']['modules'][0]
            if change == 'path': module['description'] = '/home/private/credential.json'
            if change == 'extra': index['plans']['readiness']['selector'] = 'private'
            if change == 'qualified': index['plans']['readiness']['qualification']['device'] = 'passed'
            if change == 'oversize': module['description'] = 'x' * (job.MAX_INDEX_BYTES + 1)
            cases.append(index)
        for index in cases:
            with self.assertRaises(ValueError): job.render_pipeline(index, descriptor())

    def test_descriptor_and_env_cannot_inject_a_shell_or_switch_target(self):
        for change in (dict(agentLabel='other'), dict(deviceResource='other'),
                       dict(controllerRoot='/owned/../other'), dict(controllerRoot='/owned/$(id)'),
                       dict(controllerManifestSha256='invalid')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                job.render_pipeline(self.index, descriptor() | change)
        for relative in ('../foreign', '/foreign', 'a/../../foreign', 'a\nb', 'a;id'):
            config = descriptor();config['liveBindings']['bridgeRelativePath'] = relative
            with self.assertRaises(ValueError):job.render_pipeline(self.index, config)
        script = job.render_pipeline(self.index, descriptor())
        for name in ('EXECUTION', 'SCOPE', 'AREA', 'CASE', 'FAILURE_POLICY', 'RUN_NAMESPACE'):
            self.assertIn('OVT_PHONE_' + name + '=', script)
        self.assertNotIn('${params.', script)
        self.assertNotIn('sh "', script)
        self.assertIn("env.JOB_NAME + '-' + env.BUILD_NUMBER", script)

    def test_released_failed_hold_does_not_prompt_again_and_unexpected_exit_keeps_lock(self):
        script = job.render_pipeline(self.index, descriptor())
        live = script.split("stage('Live execution')", 1)[1]
        self.assertIn('returnStatus: true', live)
        self.assertIn('if (bridgeStatus != 0)', live)
        hold = live.split('if (bridgeStatus != 0)', 1)[1]
        self.assertIn('if (bridgeStatus != 77)', hold)
        self.assertIn("currentBuild.result = 'FAILURE'", hold)
        self.assertIn("ok: 'Leave failed run and release resource'", hold)
        self.assertLess(live.index("lock(resource: 'android-device-01')"), live.index("input(id: 'pixelBridgeFailureHold'"))
        self.assertIn("error('PHONE_LIVE_FAILED_NO_CLEANUP_OR_NEXT_TEST')", hold)
        self.assertIn('throw interrupted', live)
        self.assertNotIn('catchError', live)
        self.assertNotIn('post {', script)
        self.assertIn('followSymlinks: false', live)
        self.assertIn('archiveArtifacts(artifacts: patterns', live)
        self.assertIn("paths.add('pixel-job-public/' + build + '/' + name)", script)

    def test_bootstrap_preserves_explicit_failed_hold_release_exit_77(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);(root / 'tools').mkdir()
            bridge = root / 'tools/phone_live.py';bridge.write_text('raise SystemExit(77)\n')
            manifest = root / 'deployment.private.json';manifest.write_text('{}\n')
            config = descriptor(str(root))
            config['liveBindings']['bridgeSha256'] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            config['controllerManifestSha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            result = subprocess.run([sys.executable, '-I', '-B', '-c', job._live_bootstrap(config)], capture_output=True, timeout=5)
            self.assertEqual(77, result.returncode)

    def public_export_fixture(self, workspace):
        root = workspace / 'pixel-job-public' / '9';root.mkdir(parents=True, mode=0o700)
        (workspace / 'pixel-job-public').chmod(0o700)
        core = {'summary.json': b'{"status":"failed"}\n', 'junit.xml': b'<testsuite/>\n',
                'diagnostic-events.safe.jsonl': b'{"event":"hold"}\n'}
        reference = lambda body: dict(sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        refs = {name: reference(body) for name, body in core.items()}
        artifact = dict(schemaVersion=1, runId='pixel-run-9', contextSha256='d' * 64, generation='c' * 32,
                        files=[dict(path=name, **ref) for name, ref in refs.items()])
        encoded = lambda value: (json.dumps(value, sort_keys=True) + '\n').encode()
        core['artifact-index.json'] = encoded(artifact)
        marker = {key: artifact[key] for key in ('schemaVersion', 'runId', 'contextSha256', 'generation')}
        marker['artifacts'] = refs | {'artifact-index.json': reference(core['artifact-index.json'])}
        core['debug-state.json'] = encoded(marker)
        index = dict(schemaVersion=1, job='overte-pixel6a', build=9, runNamespace='overte-pixel6a-9',
                     files={name: reference(body) for name, body in core.items()})
        core['export-index.json'] = encoded(index)
        core['EXPORT_READY'] = (hashlib.sha256(core['export-index.json']).hexdigest() + '\n').encode()
        for name, body in core.items():
            path = root / name;path.write_bytes(body);path.chmod(0o600)
        return root

    def export_probe(self, workspace):
        import os
        environment = dict(os.environ, WORKSPACE=str(workspace), BUILD_NUMBER='9', JOB_NAME='overte-pixel6a',
                           OVT_PHONE_PUBLIC_ROOT=str(workspace / 'pixel-job-public' / '9'))
        return subprocess.run([sys.executable, '-I', '-B', '-c', job._public_export_probe()],
                              env=environment, capture_output=True, text=True, timeout=5)

    def test_public_watcher_archives_sealed_whitelist_while_worker_is_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            self.assertEqual('WAIT', self.export_probe(workspace).stdout.strip())
            root = self.public_export_fixture(workspace)
            result = self.export_probe(workspace)
            self.assertEqual(0, result.returncode, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual('SEALED_PUBLIC_EXPORT_VERIFIED', receipt['state'])
            self.assertEqual(9, receipt['build'])
            self.assertEqual(sorted(p.name for p in root.iterdir()), receipt['files'])
        script = job.render_pipeline(self.index, descriptor())
        self.assertIn("'Run selected tests':", script)
        self.assertIn("'Publish sealed public evidence':", script)
        self.assertIn('parallel(', script)
        self.assertIn('waitUntil(initialRecurrencePeriod: 5000', script)
        self.assertIn('if (bridgeFinished)', script)
        self.assertNotIn("archiveArtifacts(artifacts: '**'", script)

    def test_public_watcher_rejects_tamper_foreign_build_extra_file_and_symlink(self):
        for fault in ('tamper', 'foreign-build', 'extra', 'symlink', 'partial-seal'):
            with tempfile.TemporaryDirectory() as directory, self.subTest(fault=fault):
                workspace = Path(directory);root = self.public_export_fixture(workspace)
                if fault == 'tamper': (root / 'summary.json').write_bytes(b'changed bytes')
                elif fault == 'extra': (root / 'foreign.private.json').write_text('private')
                elif fault == 'symlink':
                    (root / 'summary.json').unlink();(root / 'summary.json').symlink_to(root / 'junit.xml')
                elif fault == 'partial-seal': (root / 'EXPORT_READY').write_text('partial')
                else:
                    index = json.loads((root / 'export-index.json').read_text());index['build'] = 8
                    raw = (json.dumps(index) + '\n').encode();(root / 'export-index.json').write_bytes(raw)
                    (root / 'EXPORT_READY').write_text(hashlib.sha256(raw).hexdigest() + '\n')
                result = self.export_probe(workspace)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual('OVT_PHONE_PUBLIC_EXPORT_REJECTED', result.stderr.strip())
                self.assertNotIn('private', result.stdout)

    def test_actual_bootstrap_pins_both_files_and_rejects_tamper_or_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);(root / 'tools').mkdir()
            bridge = root / 'tools/phone_live.py'
            bridge.write_text("import json,sys;print(json.dumps({'arguments':sys.argv[1:]}))\n")
            manifest = root / 'deployment.private.json';manifest.write_text('{}\n')
            config = descriptor(str(root))
            config['liveBindings']['bridgeSha256'] = hashlib.sha256(bridge.read_bytes()).hexdigest()
            config['controllerManifestSha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            bootstrap = job._live_bootstrap(config)
            result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap], capture_output=True, text=True, timeout=5)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(['run', '--manifest', str(manifest), '--manifest-sha256', config['controllerManifestSha256']], json.loads(result.stdout)['arguments'])
            manifest.write_text('{"changed":true}\n')
            result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap], capture_output=True, text=True, timeout=5)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('OVT_PHONE_PINNED_DEPLOYMENT_REQUIRED', result.stderr)
            manifest.write_text('{}\n');bridge.rename(root / 'foreign.py');bridge.symlink_to(root / 'foreign.py')
            result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap], capture_output=True, text=True, timeout=5)
            self.assertNotEqual(0, result.returncode)


if __name__ == '__main__':
    unittest.main()
