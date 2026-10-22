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


def record(path):
    active=_ACTIVE.get()
    if active is not None:active.add(Path(path))


@contextmanager
def scope():
    # Nested original readers belong to the same synchronous full decoder.
    previous=_ACTIVE.get()
    if previous is not None:yield previous;return
    value=set();token=_ACTIVE.set(value)
    try:yield value
    finally:_ACTIVE.reset(token)
