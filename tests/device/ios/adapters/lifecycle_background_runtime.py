"""Background-safe recovery over one existing installed Lifecycle session."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import time
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.lifecycle_originals import IOSLifecycleSources
from ios.adapters.lifecycle_background import LifecycleBackground,LifecycleOSContext


class IOSLifecycleBackgroundRuntime:
    def __init__(self,adapter):self.adapter=adapter

    def owner(self,selector,run,lock,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        root=self.adapter.state_path(selector).parent
        need(isinstance(lock,ScriptSourceLock) and lock.path==root/'script-feature-sources.lock');lock.assert_held()
        runtime=IOSScriptRuntime(self.adapter);store=PrivateFeatureState(root/'ios-lifecycle-background.json');saved=store.read()
        if saved is None:binding=runtime._sources(selector)['binding']
        else:
            need(type(saved) is dict and saved.get('runId')==run and type(saved.get('iosLifecycleBackgroundVersion')) is int
                 and saved['iosLifecycleBackgroundVersion']==1);binding=context(saved['binding'])
        os=LifecycleOSContext(runtime,selector,binding)
        def sources():
            lock.assert_held();os.probe(True);raw=runtime._sources(selector);old=raw['check']
            def guard():lock.assert_held();need(old() is not False);return True
            raw['check']=guard;return IOSLifecycleSources(raw,run,epoch_ms=epoch_ms,monotonic=monotonic)
        return LifecycleBackground(store,PrivateFeatureState(root/'lifecycle-editor-owner.json'),os,run,lock,sources,
            epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)

    @contextmanager
    def background(self,selector,run):
        root=self.adapter.state_path(selector).parent;lock=ScriptSourceLock(root/'script-feature-sources.lock')
        with lock.held():
            owner=self.owner(selector,run,lock);yield owner;owner.file_guard()

    def resume_chat(self,selector,editors,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        """Compose under the actual editor lock, including background recovery."""
        from ios.adapters.lifecycle_editors import LifecycleEditors
        from ios.adapters.lifecycle_editor_history import LifecycleEditorHistory
        need(isinstance(editors,LifecycleEditors));owner=self.owner(selector,editors.run,editors.lock,
            epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
        need(owner.history_store.path==editors.history.store.path and owner.binding==editors.binding)
        result=owner.act()
        # The input WAL is unchanged. Re-read the child's actual history CAS
        # before the existing editor recipe may issue its next normal input.
        editors.history=LifecycleEditorHistory(owner.history_store,editors.binding,editors.run,editors.lock,editors.sources.source['check'])
        if editors.previous is not None:editors.decode(editors.previous)
        return result
