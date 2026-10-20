"""Strict original subprocess decoding with synthetic ADB/OS boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.android_process_query import AndroidProcessQuery
from adapters.normal_ui import NativeUIError


class AndroidProcessQueryTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0.; self.okay = True; self.guards = 0
        self.transport = SimpleNamespace(command=['synthetic-adb', '-P', '5038'])
        self.reader = AndroidProcessQuery(self.transport, 'org.overte.pico', self.guard, monotonic=lambda: self.clock)
    def guard(self): self.guards += 1; return self.okay
    def result(self, stdout=b'  PID\n  123\n', stderr=b'', code=0):
        return subprocess.CompletedProcess([], code, stdout, stderr)
    def test_actual_found_pid_and_complete_header_only_absence_preserve_native_return_code(self):
        for data, code, pids in ((b' PID\n123\n', 0, [123]), (b'PID\n', 0, []), (b'  PID\r\n', 1, [])):
            with self.subTest(code=code, pids=pids), patch('adapters.android_process_query.subprocess.run', return_value=self.result(data, code=code)) as run:
                value = self.reader.read('test-only-target', 123)
                self.assertEqual(pids, value['processIds']); self.assertEqual(code, value['nativeReturnCode'])
                self.assertEqual(['synthetic-adb', '-P', '5038', '-s', 'test-only-target', 'exec-out', 'run-as',
                                  'org.overte.pico', '/system/bin/ps', '-p', '123', '-o', 'PID'], run.call_args.args[0])
                self.assertEqual(5, run.call_args.kwargs['timeout']); run.assert_called_once()
    def test_empty_failed_permission_foreign_or_multiple_pid_output_never_becomes_absence(self):
        for result in (self.result(b''), self.result(b'PID'), self.result(b'PID\n', code=2), self.result(b'PID\n', stderr=b'permission denied'),
                       self.result(b'PID\n124\n'), self.result(b'PID\n123\n124\n'), self.result(b'PID\n123\n', code=1),
                       self.result(b'PID\n0\n'), self.result(b'PID\n+123\n'), self.result(b'PID\n123.0\n'),
                       self.result(b'NAME\n'), self.result(b'PID\n\n'), self.result(b'\xff'), self.result(b' ' * 129),
                       self.result(b'PID\n', code=True), self.result('PID\n')):
            with self.subTest(stdout=str(result.stdout)[:20], code=result.returncode), patch('adapters.android_process_query.subprocess.run', return_value=result) as run:
                with self.assertRaises(NativeUIError): self.reader.read('test-only-target', 123)
                run.assert_called_once()
    def test_timeout_transport_or_missing_command_error_is_not_an_empty_process_list(self):
        for error in (subprocess.TimeoutExpired('synthetic', 5), OSError('synthetic transport loss')):
            with self.subTest(error=type(error).__name__), patch('adapters.android_process_query.subprocess.run', side_effect=error) as run:
                with self.assertRaises(NativeUIError): self.reader.read('test-only-target', 123)
                run.assert_called_once()
    def test_lost_candidate_before_or_after_query_does_not_return_a_receipt(self):
        self.okay = False
        with patch('adapters.android_process_query.subprocess.run') as run:
            with self.assertRaises(NativeUIError): self.reader.read('test-only-target', 123)
            run.assert_not_called()
        self.okay = True
        def observe(*args, **kwargs): self.okay = False; return self.result(b'PID\n')
        with patch('adapters.android_process_query.subprocess.run', side_effect=observe):
            with self.assertRaises(NativeUIError): self.reader.read('test-only-target', 123)
    def test_late_or_regressing_original_query_and_initial_guard_fail_before_success(self):
        for now in (5., 6., -1., float('nan')):
            self.clock = 0.
            def observe(*args, **kwargs): self.clock = now; return self.result(b'PID\n')
            with self.subTest(now=now), patch('adapters.android_process_query.subprocess.run', side_effect=observe):
                with self.assertRaises(NativeUIError): self.reader.read('test-only-target', 123)
        self.clock = 0.
        def slow_guard(): self.clock = 6; return True
        self.reader.guard = slow_guard
        with patch('adapters.android_process_query.subprocess.run') as run:
            with self.assertRaises(NativeUIError): self.reader.read('test-only-target', 123)
            run.assert_not_called()
    def test_pid_target_and_package_grammar_are_closed_before_any_subprocess(self):
        with patch('adapters.android_process_query.subprocess.run') as run:
            for pid in (True, 0, -1, 2**31, '123', 123.):
                with self.subTest(pid=pid), self.assertRaises(NativeUIError): self.reader.read('test-only-target', pid)
            for target in ('', '-x', 'test\nother'):
                with self.subTest(target=target), self.assertRaises(NativeUIError): self.reader.read(target, 123)
            with self.assertRaises(NativeUIError): AndroidProcessQuery(self.transport, 'org.overte.pico;unexpected', self.guard)
            run.assert_not_called()


if __name__ == '__main__': unittest.main()
