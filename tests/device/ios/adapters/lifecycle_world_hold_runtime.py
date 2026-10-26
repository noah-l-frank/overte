"""Current installed/PID-gated composition; authenticated HID stays explicit.

No canonical RPC supplies a retained HID context yet. A caller must already
own that actual factory; absent transport cannot be reconstructed or installed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import same
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.lifecycle_originals import IOSLifecycleSources
from ios.adapters.lifecycle_editors import LifecycleEditors
from ios.adapters.lifecycle_world_attempt import LifecycleWorldAttempt
from ios.adapters.lifecycle_world_hold import LifecycleWorldHold


class IOSLifecycleWorldHoldRuntime:
    def __init__(self,adapter):self.adapter=adapter
    def child(self,selector,editors,attempt,session_factory):
        need(type(editors) is LifecycleEditors and type(attempt) is LifecycleWorldAttempt and callable(session_factory))
        editors.history.check();attempt.bound();need(attempt.history is editors.history)
        source=IOSScriptRuntime(self.adapter)._sources(selector)
        need(same(source['binding'],editors.binding))
        root=self.adapter.state_path(selector).parent;need(root==editors.history.store.path.parent)
        original=source['check'];lock=editors.history.lock
        def check():lock.assert_held();need(original() is not False);return True
        source['check']=check
        sources=IOSLifecycleSources(source,editors.run,epoch_ms=editors.sources.epoch_ms,monotonic=editors.sources.monotonic)
        # Retain the unchanged actual first-attempt owner; only the second
        # attempt's passive readers use this freshly admitted canonical scope.
        owner=LifecycleWorldHold(PrivateFeatureState(root/'ios-lifecycle-world-hold.json'),attempt,session_factory)
        owner.sources=sources;owner.reader=source['observer'].lifecycle_world(source['clock_source'])
        owner.geometry=source['observer'].geometry();owner.ui=NativeUI(source['client'],source['session'],check)
        return owner
