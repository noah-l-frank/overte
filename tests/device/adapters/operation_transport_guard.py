"""Context-local optional final transport guards; no observation provenance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from adapters.normal_ui import NativeUIError

_CURRENT=ContextVar('overte_operation_transport_guards',default=())


def check():
    for guard in _CURRENT.get():
        if guard() is False:raise NativeUIError('Operation transport guard refused delivery')


@contextmanager
def scope(guard):
    if not callable(guard):raise NativeUIError('Operation transport guard requires a callable')
    token=_CURRENT.set(_CURRENT.get()+(guard,))
    try:check();yield;check()
    finally:_CURRENT.reset(token)
