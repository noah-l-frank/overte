"""Context-local actual file reads for successful historical ownership replay.

This set is not product evidence. Only a successful full typed original decoder
and an unchanged independent inventory lease may turn it into membership.
Hooks perform no I/O and never qualify an arbitrary carrier's contents.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_ACTIVE=ContextVar('original_file_read_membership',default=None)
_COLLECT=ContextVar('original_file_read_collection',default=())
_READONLY=ContextVar('original_file_read_only',default=False)


def record(path):
    active=_ACTIVE.get()
    if active is not None:active.add(Path(path))
    for collected in _COLLECT.get():collected.add(Path(path))


def active():return _ACTIVE.get() is not None


@contextmanager
def scope(*,fresh=False):
    # Nested original readers belong to the same synchronous full decoder.
    previous=_ACTIVE.get()
    if previous is not None and not fresh:yield previous;return
    value=set();token=_ACTIVE.set(value)
    try:yield value
    finally:_ACTIVE.reset(token)


@contextmanager
def collect():
    """Observe every actual read, including isolated nested membership scopes.

    This passive trace grants no membership or product fact. Only the caller's
    complete successful typed decoder and independent file lease may qualify it.
    Each collector is independent; existing scope(fresh=True) stays isolated.
    """
    value=set();token=_COLLECT.set((*_COLLECT.get(),value))
    try:yield value
    finally:_COLLECT.reset(token)


def check_writable():
    """An explicit passive area may prohibit private state mutation."""
    if _READONLY.get():
        from adapters.normal_ui import NativeUIError
        raise NativeUIError('Passive original read area prohibits private state mutation')


@contextmanager
def readonly():
    """Default-inactive platform-neutral barrier; nesting preserves its caller."""
    token=_READONLY.set(True)
    try:yield
    finally:_READONLY.reset(token)
