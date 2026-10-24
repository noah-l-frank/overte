"""Reuse a typed decode only inside its original actual-read membership scope.

This marker adds no path to a census. A new census must execute the original
readers again, even inside the same immutable validation round. Existing file,
inventory and owner-context guards remain the caller's responsibility.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_file_reads import active,scope


def current():
    if not active():return None
    with scope() as reads:return reads


class OriginalMembership:
    def __init__(self):
        self.reads=current()
        self.paths=None if self.reads is None else frozenset(self.reads)

    def matches(self):
        reads=current()
        return reads is self.reads and (reads is None or self.paths<=reads)
