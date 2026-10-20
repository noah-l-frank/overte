"""Bounded host serialization for the fixed native Script source channels."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import time

from adapters.native_feature_observation import need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError

VERSION = 1


class PhoneScriptSourceLock:
    def __init__(self, path, *, timeout=5):
        need(number(timeout, 0.01, 5))
        self.path, self.timeout = Path(path), timeout

    @contextmanager
    def held(self):
        descriptor = None
        try:
            import fcntl  # A host without this primitive fails closed.
            parent = PrivateFeatureState(self.path)
            parent._parent()
            descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
                                 | getattr(os, 'O_NONBLOCK', 0), 0o600)
            def check():
                parent._parent()
                info, current = os.fstat(descriptor), self.path.lstat()
                need(stat.S_ISREG(info.st_mode) and stat.S_ISREG(current.st_mode)
                     and info.st_nlink == current.st_nlink == 1 and info.st_size == 0
                     and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o600
                     and (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino))
            check()
            started = previous = time.monotonic()
            for attempt in range(202):
                check()
                now = time.monotonic()
                need(number(now, 0, 1e15) and previous <= now and now - started < self.timeout)
                previous = now
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    need(attempt < 201)
                    time.sleep(min(0.025, self.timeout / 4))
            check()
            yield
            check()
        except Exception:
            raise NativeUIError('Phone Script source serialization is unavailable') from None
        finally:
            # Closing releases the OS lock, including on process death. Never
            # unlink the stable inode: waiters must keep the same lock domain.
            if descriptor is not None:
                os.close(descriptor)
