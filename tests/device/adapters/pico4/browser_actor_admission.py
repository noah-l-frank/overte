"""Original configuration/Parent and whole budget for explicit Browser Actor6."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import time

from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_execution_budget import BrowserExecutionBudget
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.operation_host import process_identity
from adapters.script_journey.history import canonical

VERSION = 1
UNRESOLVED = []


class BrowserActorAdmission:
    def __init__(self, path, configuration, *, monotonic=time.monotonic):
        need(type(configuration) is dict and configuration.get('picoFeatureObserverVersion') == 6
            and type(configuration['picoFeatureObserverVersion']) is int and configuration['area'] == 'tablet-web')
        self.configuration = deepcopy(configuration)
        self.digest = json_digest(self.configuration)
        self.budget = self._budget = BrowserExecutionBudget(configuration['browserOwnerBudget'], monotonic=monotonic)
        self.host = host_identity(); self.parent_pid = os.getppid()
        self.parent = configuration['browserParentHostProcessIdentity']
        need(type(self.parent) is str and process_identity(self.parent_pid) == self.parent)
        self.store = PrivateFeatureState(Path(path)); self.file = self._file = object.__new__(LifecycleProcessFile)
        self.failed = False
        try:
            LifecycleProcessFile.__init__(self.file, self.store)
            need(self.file.file is not None and self.file.raw == canonical(self.configuration) + b'\n')
            self.original = self._original = (self.file, self.store, self.file.file, self.file.parent,
                self.host, self.parent_pid, self.parent, self.digest, self.budget)
            self.check()
        except BaseException:
            self.failed = True; UNRESOLVED.append(self); raise

    def check(self):
        try:
            need(not self.failed and self.original is self._original
                and all(current is original for current, original in zip(
                    (self.file, self.store, self.file.file, self.file.parent), self.original[:4]))
                and self.file is self._file and self.budget is self._budget is self.original[8]
                and (host_identity(), os.getppid(), self.parent, self.digest) == self.original[4:8]
                and json_digest(self.configuration) == self.digest
                and process_identity(self.parent_pid) == self.parent)
            self.budget.same(self.configuration['browserOwnerBudget']); self.file.guard()
            return self.budget.check()
        except BaseException:
            self.failed = True
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            raise

    def now(self):
        return self.check()

    def close_host(self):
        try:
            need(self.file is self._file)
            if hasattr(self, 'original'):
                need(all(current is original for current, original in zip(
                    (self.file, self.store, self.file.file, self.file.parent), self.original[:4])))
            return self.file.close_host()
        except Exception:
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            return False
