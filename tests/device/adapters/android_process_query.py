"""Original bounded own-UID Android PID selection; errors are never absence.

The closed ps header/exit ABI is required. This is a pre-launch observation,
not kernel ESRCH or proof that a package/candidate owns a found/reused PID.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import subprocess
import time

from adapters.native_feature_observation import integer, number
from adapters.normal_feature_state import need
from adapters.normal_ui import NativeUIError

VERSION = 1


class AndroidProcessQuery:
    def __init__(self, transport, package, guard, *, monotonic=time.monotonic):
        need(type(package) is str and re.fullmatch('[A-Za-z0-9_]+(?:[.][A-Za-z0-9_]+)+', package)
             and callable(guard) and callable(monotonic)
             and type(transport.command) is list and 0 < len(transport.command) <= 5
             and all(type(part) is str and bool(part) for part in transport.command))
        self.command = list(transport.command)
        self.package, self.guard, self.monotonic = package, guard, monotonic

    def read(self, target, pid):
        need(type(target) is str and bool(target) and not target.startswith('-')
             and not any(ord(char) < 32 for char in target) and integer(pid, 1, 2147483647))
        try:
            started = self.monotonic(); need(number(started, 0, 1e15))
            need(self.guard() is not False)
            before = self.monotonic(); need(number(before, 0, 1e15) and before >= started and before - started < 5)
            # No shell script, mutation, signal, user payload or unchecked
            # output reaches the target. run-as retains the selected app UID.
            argv = [*self.command, '-s', target, 'exec-out', 'run-as', self.package,
                    '/system/bin/ps', '-p', str(pid), '-o', 'PID']
            result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=5 - (before - started), check=False)
            need(type(result.returncode) is int and result.returncode in (0, 1)
                 and type(result.stdout) is bytes and len(result.stdout) <= 128 and result.stdout.endswith(b'\n')
                 and type(result.stderr) is bytes and result.stderr == b'')
            lines = result.stdout.decode('ascii').replace('\r', '').splitlines()
            need(len(lines) in (1, 2) and lines[0].strip() == 'PID')
            found = []
            if len(lines) == 2:
                row = lines[1].strip()
                need(re.fullmatch('[1-9][0-9]{0,9}', row) and int(row) == pid and result.returncode == 0)
                found.append(int(row))
            need(self.guard() is not False)
            after = self.monotonic(); need(number(after, 0, 1e15) and after >= before and after - started < 5)
            return dict(processQueryVersion=VERSION, queryProcessId=pid, complete=True,
                        processIds=found, nativeReturnCode=result.returncode)
        except Exception:
            raise NativeUIError('Original Android PID selection is unavailable or invalid') from None
