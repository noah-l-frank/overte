"""Existing-session factory for the closed Lifecycle normal-input owner.

This internal component supplies no complete feature capability or cleanup.
Unresolved journals intentionally block ordinary installed session teardown.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.lifecycle_input_owner import LifecycleInputOwner
from ios.adapters.lifecycle_navigation_owner import LifecycleNavigationOwner


class IOSLifecycleInputRuntime:
    _owner_type=LifecycleInputOwner
    _reader_name='lifecycle_inputs'

    def __init__(self,adapter):self.adapter=adapter

    @contextmanager
    def inputs(self,selector,run,*,role='primary'):
        source=IOSScriptRuntime(self.adapter)._sources(selector)
        root=self.adapter.state_path(selector).parent;lock=ScriptSourceLock(root/'script-feature-sources.lock')
        with lock.held():
            def guard():
                lock.assert_held();need(source['check']() is not False);return True
            owner_type=self._owner_type
            owner=owner_type(PrivateFeatureState(root/owner_type.store_name(role)),lock,source['binding'],run,role,source['native'],guard)
            reader=getattr(source['observer'],self._reader_name)(clock_source=source['clock_source']);old_guard=reader.guard
            def original_guard():guard();need(old_guard() is not False);return True
            reader.guard=original_guard
            yield owner,reader
            guard()


class IOSLifecycleNavigationRuntime(IOSLifecycleInputRuntime):
    _owner_type=LifecycleNavigationOwner
    _reader_name='lifecycle_navigation_inputs'
