"""Serialize historical originals using only an already existing private inode."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import os
import threading
from adapters.native_feature_observation import need
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy


class ArchiveSourceLock(ScriptSourceLock):
    @contextmanager
    def held(self):
        # A complete archive cannot mint a missing lock owner or create a file.
        import fcntl
        if self._owner is not None:
            owner=self._owner;self.assert_held()
            yield
            need(self._owner is owner);self.assert_held();return
        descriptor=None
        try:
            descriptor=os.open(self.path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            self._check(descriptor,self.path)
            try:fcntl.flock(descriptor,fcntl.LOCK_SH|fcntl.LOCK_NB)
            except BlockingIOError:raise ScriptSourceBusy('Historical original source is busy') from None
            self._owner=(self.path,descriptor,os.getpid(),threading.get_ident())
            self.assert_held();yield;self.assert_held()
        finally:
            self._owner=None
            if descriptor is not None:os.close(descriptor)
