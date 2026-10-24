#!/usr/bin/env python3
"""Verify network launcher selection and exactly-once test execution."""
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

LAUNCHER = Path(__file__).resolve().parents[1] / 'ci/host-test-network.sh'


class HostTestNetwork(unittest.TestCase):
    def invoke(self, *, available=True, hosted=False, runner='github-hosted',
               system='Linux', code=0, arguments=True):
        with tempfile.TemporaryDirectory(prefix='overte-network-launcher-') as directory:
            root = Path(directory)
            binaries = root / 'bin'
            binaries.mkdir()
            log, marker = root / 'calls.jsonl', root / 'test-executions'
            scripts = {
                'unshare': '''import json, os, sys
with open(os.environ['TEST_LOG'], 'a') as output:
    output.write(json.dumps({'tool':'unshare','args':sys.argv[1:]})+'\\n')
if sys.argv[1:] == ['--user','--map-root-user','--net','/usr/bin/true']:
    raise SystemExit(0 if os.environ['TEST_AVAILABLE']=='1' else 1)
command = sys.argv[sys.argv.index('--')+1:]
os.execv(command[0], command)
''',
                'sudo': '''import json, os, sys
assert sys.argv[1:3] == ['-n','unshare']
with open(os.environ['TEST_LOG'], 'a') as output:
    output.write(json.dumps({'tool':'sudo','args':sys.argv[1:]})+'\\n')
os.execv(os.environ['TEST_UNSHARE'], sys.argv[2:])
''',
                'uname': "import os; print(os.environ['TEST_SYSTEM'])\n",
                'id': "print('1001')\n",
            }
            for name, script in scripts.items():
                path = binaries / name
                path.write_text('#!' + sys.executable + '\n' + script)
                path.chmod(0o755)
            environment = {'PATH': str(binaries) + os.pathsep + os.defpath,
                           'TEST_LOG': str(log), 'TEST_AVAILABLE': '1' if available else '0',
                           'TEST_UNSHARE': str(binaries / 'unshare'), 'TEST_SYSTEM': system}
            if hosted:
                environment.update(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT=runner)
            command = [str(LAUNCHER)]
            if arguments:
                program = ("from pathlib import Path; import sys; "
                           "path=Path(sys.argv[1]); "
                           "path.write_text(path.read_text()+'run\\n' if path.exists() else 'run\\n'); "
                           "raise SystemExit(int(sys.argv[2]))")
                command += [sys.executable, '-c', program, str(marker), str(code)]
            result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                    timeout=10, check=False)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            executions = marker.read_text().splitlines() if marker.exists() else []
            return result, calls, executions

    def test_clean_environment_uses_unprivileged_namespace_without_sudo(self):
        result, calls, executions = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row['tool'] for row in calls], ['unshare', 'unshare'])
        self.assertEqual(calls[1]['args'][:4], ['--user', '--map-root-user', '--net', '--'])
        self.assertEqual(executions, ['run'])

    def test_test_failure_is_preserved_without_privileged_retry(self):
        result, calls, executions = self.invoke(hosted=True, code=23)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual([row['tool'] for row in calls], ['unshare', 'unshare'])
        self.assertEqual(executions, ['run'])

    def test_unrecognized_host_cannot_use_sudo(self):
        for hosted, runner, system in ((False, 'github-hosted', 'Linux'),
                                       (True, 'self-hosted', 'Linux'),
                                       (True, 'github-hosted', 'Darwin')):
            with self.subTest(hosted=hosted, runner=runner, system=system):
                result, calls, executions = self.invoke(available=False, hosted=hosted,
                                                        runner=runner, system=system)
                self.assertEqual(result.returncode, 64)
                self.assertEqual([row['tool'] for row in calls], ['unshare'])
                self.assertFalse(executions)

    def test_only_recognized_host_uses_noninteractive_privileged_fallback(self):
        result, calls, executions = self.invoke(available=False, hosted=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row['tool'] for row in calls], ['unshare', 'sudo', 'unshare'])
        self.assertEqual(calls[1]['args'][:7],
                         ['-n', 'unshare', '--net', '--setgid', '1001', '--setuid', '1001'])
        self.assertEqual(executions, ['run'])

    def test_missing_command_never_probes_or_executes(self):
        result, calls, executions = self.invoke(arguments=False)
        self.assertEqual(result.returncode, 64)
        self.assertFalse(calls)
        self.assertFalse(executions)


if __name__ == '__main__':
    unittest.main()
