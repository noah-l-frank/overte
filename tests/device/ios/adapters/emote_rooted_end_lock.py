"""Existing-inode exclusive ownership for Emote end and historical replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import os
import threading
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy


@contextmanager
def held_existing(lock):
    need(isinstance(lock,ScriptSourceLock))
    if lock._owner is not None:
        owner=lock._owner;lock.assert_held()
        try:yield
        finally:need(lock._owner is owner);lock.assert_held()
        return
    descriptor=owner=None
    try:
        import fcntl
        try:descriptor=os.open(lock.path,os.O_RDWR|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        except OSError:raise NativeUIError('Existing Emote end source lock is unavailable') from None
        lock._check(descriptor,lock.path)
        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ScriptSourceBusy('Emote end source is busy') from None
        owner=(lock.path,descriptor,os.getpid(),threading.get_ident());lock._owner=owner
        lock.assert_held()
        try:yield
        finally:need(lock._owner is owner);lock.assert_held()
    finally:
        if owner is not None and lock._owner is owner:lock._owner=None
        if descriptor is not None:os.close(descriptor)
