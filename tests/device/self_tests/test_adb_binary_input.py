"""Actual private Python subprocess stdin/stdout through the shared SDK seam.

The selected executable is Python, not ADB. No device or server is contacted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import subprocess
import sys
import unittest
from unittest.mock import patch

from adb_transport import AdbTransport


class AdbBinaryInputTests(unittest.TestCase):
    def setUp(self):self.transport=AdbTransport(sys.executable)

    def test_actual_binary_input_larger_than_text_control_cap_keeps_nul_invalid_utf8_and_carriage_return(self):
        literal=bytes(range(256))*200+b'\x00\xff\r\n'
        actual=self.transport.execute_bytes(['-c','import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())'],
            input_bytes=literal,timeout=5)
        self.assertEqual(literal,actual)

    def test_omitted_input_preserves_actual_binary_output_and_default_call_signature(self):
        actual=self.transport.execute_bytes(['-c',"import sys;sys.stdout.buffer.write(b'\\x00\\xff\\r\\n')"],timeout=5)
        self.assertEqual(b'\x00\xff\r\n',actual)
        with patch('adb_transport.subprocess.run',return_value=subprocess.CompletedProcess(['declared'],0,stdout=b'ok')) as run:
            self.assertEqual(b'ok',self.transport.execute_bytes(['declared']))
            self.assertNotIn('input',run.call_args.kwargs);self.assertNotIn('text',run.call_args.kwargs)

    def test_nonbytes_input_is_refused_before_any_subprocess(self):
        with patch('adb_transport.subprocess.run') as run:
            for value in ('text',bytearray(b'bytes'),memoryview(b'bytes'),True,0):
                with self.subTest(value=type(value).__name__),self.assertRaisesRegex(RuntimeError,'binary input'):
                    self.transport.execute_bytes(['declared'],input_bytes=value)
            run.assert_not_called()

    def test_actual_nonzero_child_keeps_literal_when_check_false_and_check_true_refuses(self):
        command=['-c',"import sys;sys.stdout.buffer.write(sys.stdin.buffer.read());sys.exit(7)"]
        self.assertEqual(b'\x00\xff',self.transport.execute_bytes(command,input_bytes=b'\x00\xff',check=False,timeout=5))
        with self.assertRaisesRegex(RuntimeError,'binary operation failed'):
            self.transport.execute_bytes(command,input_bytes=b'\x00\xff',timeout=5)

    def test_actual_timeout_retains_literal_partial_stdout_in_original_exception_cause(self):
        command=['-c','import sys,time;sys.stdout.buffer.write(sys.stdin.buffer.read());sys.stdout.buffer.flush();time.sleep(5)']
        with self.assertRaisesRegex(RuntimeError,'binary operation timed out') as caught:
            self.transport.execute_bytes(command,input_bytes=b'\x00\xff\r\n',timeout=.3)
        self.assertIs(type(caught.exception.__cause__),subprocess.TimeoutExpired)
        self.assertEqual(b'\x00\xff\r\n',caught.exception.__cause__.output)


if __name__=='__main__':unittest.main()
