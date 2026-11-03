"""Current action admission around existing canonical/episode SDK factories."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.assets_action_phase import AssetsActionScope
from ios.adapters.assets_runtime import AssetsNativeInput


class AssetsActionRuntime:
    def __init__(self,*args,assets_action,**kwargs):
        need(type(assets_action) is AssetsActionScope);self.assets_action=assets_action;super().__init__(*args,**kwargs)
    def _bind_action(self,selector,parts):
        scope=self.assets_action;scope.runtime_guard(self,selector,parts['binding']);original=parts['check']
        def checked():
            scope.runtime_guard(self,selector,parts['binding']);need(original() is not False);return True
        parts['check']=checked
        seen=set()
        for transport in (parts['observer'],getattr(parts['clock_source'].send,'__self__',None)):
            need(transport is not None)
            if id(transport) in seen:continue
            seen.add(id(transport));before=transport.before_send
            def final(before=before):
                checked()
                if before is not None:need(before() is not False)
                checked()
            transport.before_send=final
        parts['native']=AssetsNativeInput.from_original(parts['native'],checked)
        checked();return parts
    def _sources(self,selector):
        self.assets_action.runtime_guard(self,selector);return self._bind_action(selector,super()._sources(selector))
    def _assets_sources(self,selector,lock):
        self.assets_action.runtime_guard(self,selector);return self._bind_action(selector,super()._assets_sources(selector,lock))
