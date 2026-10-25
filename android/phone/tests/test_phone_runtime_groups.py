#!/usr/bin/env python3
"""Host-only admission, concurrency, timeout and cancellation counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('phone_groups_under_test', HERE / 'phone-e2e-runtime-regressions.py')
driver = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = driver
spec.loader.exec_module(driver)


class PhoneRuntimeGroupsTests(unittest.TestCase):
    def test_pure_listing_covers_default_execute_extended_without_host_commands(self):
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('No command during list')):
            for flags, expected in (([], 190), (['--execute'], 238), (['--extended'], 191),
                                    (['--execute', '--extended'], 239)):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(driver.main(['--list-groups', *flags]), 0)
                value = json.loads(output.getvalue())
                files = [name for row in value['groups'] for name in row['files']]
                self.assertEqual(len(files), expected)
                self.assertEqual(len(set(files)), expected)
                self.assertEqual(value['jobs'], 4)
                self.assertTrue(all(len(row['files']) <= 20 for row in value['groups']))

    def test_registry_mutations_never_dispatch_or_claim_a_plan(self):
        original = driver.load_registry()
        for change in ('missing', 'duplicate', 'foreign', 'budget', 'mode'):
            registry = copy.deepcopy(original)
            if change == 'missing':
                registry['groups'][0]['files'].pop()
            elif change == 'duplicate':
                registry['groups'][0]['files'].append(registry['groups'][0]['files'][0])
            elif change == 'foreign':
                registry['groups'][0]['files'][0] = '/tmp/foreign.py'
            elif change == 'budget':
                registry['groups'][0]['timeoutSeconds'] += 1
            else:
                registry['modes']['default'].pop()
            with patch.object(driver, 'load_registry', return_value=registry), \
                 patch.object(driver, 'run_groups', side_effect=AssertionError('No dispatch')) as dispatch, \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(driver.main(['--list-groups']), 2)
                dispatch.assert_not_called()

    def test_unknown_duplicate_and_wrong_mode_selection_never_dispatch(self):
        prepared = driver.load_registry()['modes']['execute'][0]
        for arguments in (['--group', 'absent'], ['--group', prepared],
                          ['--group', 'host-basics', '--group', 'host-basics'], ['--jobs', '0'], ['--jobs', '5']):
            with patch.object(driver, 'run_groups', side_effect=AssertionError('No dispatch')), \
                 contextlib.redirect_stderr(io.StringIO()):
                try:
                    result = driver.main(arguments)
                except SystemExit as error:
                    result = error.code
                self.assertNotEqual(result, 0)

    def execute_fixture(self, programs, *, jobs=2, deadlines=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        scripts = {}
        for name, code in programs.items():
            script = root / (name + '.py')
            script.write_text(code)
            scripts[name] = script
        output = root / 'results'
        group = {'id': 'host-fixture', 'files': list(programs), 'timeoutSeconds': 30}
        with patch.object(driver, 'file_command', side_effect=lambda name: [sys.executable, '-B', str(scripts[name])]), \
             patch.object(driver, 'file_timeout', side_effect=lambda name: (deadlines or {}).get(name, 5)), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = driver.run_groups([group], jobs=jobs, output_dir=output)
        return result, json.loads((output / 'summary.json').read_bytes()), output

    def test_isolated_files_overlap_and_all_original_results_are_accounted(self):
        code = 'import time\ntime.sleep(.2)\nprint("complete host fixture")\n'
        result, report, output = self.execute_fixture({'first': code, 'second': code, 'third': code}, jobs=2)
        self.assertEqual(result, 0)
        self.assertEqual(report['selectedFiles'], 3)
        self.assertEqual(report['completedFiles'], 3)
        self.assertEqual(report['scope'], 'HOST_CONTRACTS_NOT_DEVICE_ACCEPTANCE')
        self.assertTrue(all(row['status'] == 'passed' for row in report['results']))
        events = [json.loads(line) for line in (output / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([row['event'] for row in events[:2]], ['begin', 'begin'])
        self.assertEqual(sorted(row['file'] for row in events if row['event'] == 'end'), ['first', 'second', 'third'])
        self.assertEqual(len(list(output.glob('file-*.log'))), 3)
        self.assertEqual((output.stat().st_mode & 0o777), 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir()))

    def test_failure_and_timeout_stay_red_with_complete_private_logs(self):
        programs = {'failed': 'print("original diagnostic", flush=True)\nraise SystemExit(3)\n',
                    'timed': 'import time\nprint("before timeout", flush=True)\ntime.sleep(30)\n',
                    'passed': 'print("independent completed host fixture")\n'}
        result, report, output = self.execute_fixture(programs, deadlines={'failed': 5, 'timed': .15, 'passed': 5})
        self.assertEqual(result, 1)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual([row['status'] for row in report['results']], ['failed', 'timeout', 'passed'])
        self.assertIn('original diagnostic', (output / 'file-0001.log').read_text())
        self.assertIn('before timeout', (output / 'file-0002.log').read_text())
        self.assertIn('errors="2"', (output / 'junit.xml').read_text())
        self.assertIn('skipped="0"', (output / 'junit.xml').read_text())

    def test_own_detached_descendant_is_reaped_before_success_return(self):
        result, report, output = self.execute_fixture({'detached': '''import subprocess,sys
+child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
+print(child.pid,flush=True)
+'''.replace('\n+', '\n')})
        self.assertEqual(result, 0)
        pid = int((output / 'file-0001.log').read_text().strip())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertFalse(report['cleanupError'])

    def test_owner_rejects_existing_children_or_threads_without_signalling_them(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
        try:
            with self.assertRaisesRegex(driver.GroupError, 'no existing children'):
                driver.run_groups([{'id': 'unused', 'files': ['unused']}])
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=5)
        release = threading.Event()
        thread = threading.Thread(target=release.wait)
        thread.start()
        try:
            with self.assertRaisesRegex(driver.GroupError, 'one thread'):
                driver.run_groups([{'id': 'unused', 'files': ['unused']}])
            self.assertTrue(thread.is_alive())
        finally:
            release.set()
            thread.join(timeout=5)

    def test_original_file_and_actor_receive_sigterm_without_kill_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / 'original.py'
            script.write_text('''import json,os,signal,subprocess,sys
actor=subprocess.Popen([sys.executable,'-c',
 'import json,signal;print(json.dumps(sorted(int(s) for s in signal.pthread_sigmask(signal.SIG_BLOCK,[]))),flush=True);signal.pause()'],stdout=subprocess.PIPE,text=True)
try:
 actor_mask=json.loads(actor.stdout.readline())
 actor.terminate();actor_code=actor.wait(timeout=2)
 print(json.dumps(dict(pid=os.getpid(),argv=sys.argv,mask=sorted(int(s) for s in signal.pthread_sigmask(signal.SIG_BLOCK,[])),actorMask=actor_mask,actorReturncode=actor_code)),flush=True)
finally:
 if actor.poll() is None:actor.kill();actor.wait()
 actor.stdout.close()
signal.pause()
''')
            command = [sys.executable, '-B', str(script), 'literal argument with spaces']
            # Reproduce the scheduler's real masked-spawn registration boundary.
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGINT, signal.SIGTERM))
            try:
                process = subprocess.Popen(driver.supervised_command(command), stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, start_new_session=True)
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            try:
                packet = json.loads(process.stdout.readline())
                self.assertEqual(packet['pid'], process.pid)
                self.assertEqual(packet['argv'], command[2:])
                for blocked in (packet['mask'], packet['actorMask']):
                    self.assertNotIn(int(signal.SIGTERM), blocked)
                    self.assertNotIn(int(signal.SIGINT), blocked)
                self.assertEqual(packet['actorReturncode'], -signal.SIGTERM)
                process.terminate()
                # No stop_worker/SIGKILL escalation is involved in this proof.
                self.assertEqual(process.wait(timeout=2), -signal.SIGTERM)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                process.stdout.close()
                process.stderr.close()

    def test_late_interruption_after_all_file_passes_is_red_in_json_and_junit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            group = {'id': 'late-interruption', 'files': ['finished'], 'timeoutSeconds': 125}
            records = [{'file': 'finished', 'groupId': group['id'], 'timeoutSeconds': 90,
                        'status': 'passed', 'returncode': 0, 'durationSeconds': .1}]
            result = driver.reports(root, [group], records, 4, signal.SIGTERM, False)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['groups'][0]['status'], 'failed')
            junit = ET.parse(root / 'junit.xml').getroot()
            self.assertEqual(junit.attrib['tests'], '2')
            self.assertEqual(junit.attrib['errors'], '1')
            self.assertIsNotNone(junit.find("./testcase[@name='interrupted']/error"))

    def test_cancellation_terminates_owned_processes_and_marks_unstarted_rows_red(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        base = Path(root.name)
        slow = base / 'slow.py'
        slow.write_text('import os,time\nprint(os.getpid(),flush=True)\ntime.sleep(30)\n')
        results = base / 'results'
        wrapper = base / 'wrapper.py'
        wrapper.write_text('''import importlib.util,sys
+from pathlib import Path
+sys.path.insert(0,sys.argv[1])
+spec=importlib.util.spec_from_file_location('driver',Path(sys.argv[1])/'phone-e2e-runtime-regressions.py')
+d=importlib.util.module_from_spec(spec);sys.modules[spec.name]=d;spec.loader.exec_module(d)
+d.file_command=lambda name:[sys.executable,'-B',sys.argv[2]]
+d.file_timeout=lambda name:30
+raise SystemExit(d.run_groups([dict(id='cancel-proof',files=['one','two','three'],timeoutSeconds=90)],jobs=1,output_dir=Path(sys.argv[3])))
+'''.replace('\n+', '\n'))
        with (base / 'wrapper.log').open('wb') as log:
            process = subprocess.Popen([sys.executable, '-B', str(wrapper), str(HERE), str(slow), str(results)],
                                       stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 5
            while not (results / 'file-0001.log').exists() or not (results / 'file-0001.log').stat().st_size:
                self.assertIsNone(process.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.02)
            child = int((results / 'file-0001.log').read_text().strip())
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=5), 128 + signal.SIGTERM)
            report = json.loads((results / 'summary.json').read_bytes())
            self.assertEqual(report['status'], 'failed')
            self.assertEqual([row['status'] for row in report['results']], ['cancelled', 'not-run', 'not-run'])
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == '__main__':
    unittest.main(verbosity=2)
