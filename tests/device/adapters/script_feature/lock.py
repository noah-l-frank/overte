"""Bounded host serialization for the fixed native Script source channels."""
# Derived from frozen Phone source fe4684bf46585088370b3a328a738f147e670b97.
# Platform input and clocks are supplied by the owning runtime.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import threading
import time

from adapters.native_feature_observation import need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError

VERSION = 1


class ScriptSourceBusy(NativeUIError):
    """Only genuine contention may be retried by the independent publisher."""


class ScriptSourceLock:
    def __init__(self, path, *, timeout=5):
        need(number(timeout, 0.01, 5))
        self.path, self.timeout = Path(path), timeout
        self._owner = None

    def _check(self, descriptor, path):
        need(self.path == path)
        PrivateFeatureState(path)._parent()
        info, current = os.fstat(descriptor), path.lstat()
        need(stat.S_ISREG(info.st_mode) and stat.S_ISREG(current.st_mode)
             and info.st_nlink == current.st_nlink == 1 and info.st_size == 0
             and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600
             and (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino))

    def assert_held(self):
        try:
            need(self._owner is not None)
            path, descriptor, pid, thread = self._owner
            need(pid == os.getpid() and thread == threading.get_ident())
            self._check(descriptor, path)
        except Exception:
            raise NativeUIError('Script source serialization is unavailable') from None

    @contextmanager
    def held(self):
        # Only an explicitly shared instance held by this exact process/thread
        # can nest. Another instance/role/process still needs its own OS lock.
        if self._owner is not None:
            owner = self._owner
            self.assert_held()
            try:
                yield
            finally:
                # Check the exact lock even when the protected operation
                # raises. Its own typed failure must survive a valid exit.
                need(self._owner is owner)
                self.assert_held()
            return
        descriptor = owner = None
        path = self.path
        try:
            import fcntl  # A host without this primitive fails closed.
            PrivateFeatureState(path)._parent()
            descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
                                 | getattr(os, 'O_NONBLOCK', 0), 0o600)
            self._check(descriptor, path)
            started = previous = time.monotonic();contended=False
            for attempt in range(202):
                self._check(descriptor, path)
                now = time.monotonic()
                need(number(now, 0, 1e15) and previous <= now)
                if now-started>=self.timeout:
                    if contended:raise ScriptSourceBusy('Script source is busy')
                    need(False)
                previous = now
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    contended=True
                    if attempt>=201:raise ScriptSourceBusy('Script source is busy')
                    time.sleep(min(0.025, self.timeout / 4))
            self._check(descriptor, path)
            owner = (path, descriptor, os.getpid(), threading.get_ident())
            self._owner = owner
        except ScriptSourceBusy:
            raise ScriptSourceBusy('Script source is busy') from None
        except Exception:
            raise NativeUIError('Script source serialization is unavailable') from None
        else:
            try:
                yield
            finally:
                # Body exceptions are not serialization errors. Preserve the
                # original object only after proving the lock still belongs
                # to this process/thread and the same original inode.
                need(self._owner is owner)
                self.assert_held()
        finally:
            if owner is not None and self._owner is owner:
                self._owner = None
            # Closing releases the OS lock, including on process death. Never
            # unlink the stable inode: waiters must keep the same lock domain.
            if descriptor is not None:
                os.close(descriptor)
