"""Fail closed before ordinary SDK work while Lifecycle cleanup is unresolved."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError

PREFIXES=('ios-lifecycle-','lifecycle-editor-','lifecycle-input-proof-','lifecycle-navigation-proof-')


def ensure_released(adapter,selector):
    root=adapter.state_path(selector).parent
    if not root.exists():return True
    PrivateFeatureState(root/'lifecycle-entry-boundary.json')._parent()
    entries=list(root.iterdir());need(len(entries)<=4096)
    if any(path.name.startswith(PREFIXES) for path in entries):
        # No complete Lifecycle restoration/quiet/end proof exists yet. An
        # input ACK or retained source archive cannot retire this responsibility.
        raise NativeUIError('Lifecycle ownership requires its original complete cleanup before ordinary session operations')
    return True


def installed_entry(function):
    @wraps(function)
    def entry(self,selector,*args,**kwargs):
        ensure_released(self,selector);return function(self,selector,*args,**kwargs)
    return entry
