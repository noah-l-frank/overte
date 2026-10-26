"""Existing installed-session source scope for ordinary editor integration."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.lifecycle_originals import IOSLifecycleSources
from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
from ios.adapters.lifecycle_input_owner import LifecycleInputOwner
from ios.adapters.lifecycle_navigation_owner import LifecycleNavigationOwner
from ios.adapters.lifecycle_editors import LifecycleEditors


class IOSLifecycleEditorsRuntime:
    def __init__(self,adapter):self.adapter=adapter

    @contextmanager
    def editors(self,selector,run):
        source=IOSScriptRuntime(self.adapter)._sources(selector)
        root=self.adapter.state_path(selector).parent;lock=ScriptSourceLock(root/'script-feature-sources.lock')
        with lock.held():
            previous_check=source['check']
            def guard():lock.assert_held();need(previous_check() is not False);return True
            source['check']=guard;originals=IOSLifecycleSources(source,run)
            owners=[];readers=[]
            for owner_type,reader_name in ((LifecycleNavigationOwner,'lifecycle_navigation_inputs'),(LifecycleInputOwner,'lifecycle_inputs')):
                owner=owner_type(PrivateFeatureState(root/owner_type.store_name('primary')),lock,source['binding'],run,'primary',source['native'],guard)
                reader=getattr(source['observer'],reader_name)(clock_source=source['clock_source']);old_guard=reader.guard
                def read_guard(original_guard=old_guard):guard();need(original_guard() is not False);return True
                reader.guard=read_guard;owners.append(owner);readers.append(reader)
            history=LifecycleEditorHistory(PrivateFeatureState(root/'lifecycle-editor-owner.json'),source['binding'],run,lock,guard)
            yield LifecycleEditors(PrivateFeatureState(root/'ios-lifecycle-editors-owner.json'),history,originals,
                owners[0],readers[0],owners[1],readers[1])
            guard()
