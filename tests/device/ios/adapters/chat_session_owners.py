"""Retain unfinished Chat drafts/history before ordinary session/SDK work."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from feature_journeys.contract import identifier


def owners_absent(adapter,selector):
    root=adapter.state_path(selector).parent
    if not root.exists():return True
    PrivateFeatureState(root/'chat-entry-boundary.json')._parent();entries=list(root.iterdir());need(len(entries)<=4096)
    return not any(path.name.startswith('ios-chat-') for path in entries)


def ensure_released(adapter,selector):
    if not owners_absent(adapter,selector):
        raise NativeUIError('Chat ownership requires original complete cleanup before ordinary session operations')
    return True


def register_scope(adapter,selector,binding,run,artifact_root):
    root=Path(artifact_root);need(root.is_absolute() and root.resolve(strict=True)==root and root.is_dir())
    PrivateFeatureState(root/'chat-scope-boundary.json')._parent()
    value=dict(iosChatScopeVersion=1,binding=context(binding),runId=identifier(run),artifactRoot=str(root))
    store=PrivateFeatureState(adapter.state_path(selector).with_name('ios-chat-scope.json'));previous=store.read()
    if previous is None:store.write(value,None)
    else:need(same(value,previous))
    need(same(store.read(),value));return value


def installed_entry(function):
    @wraps(function)
    def entry(self,selector,*args,**kwargs):
        ensure_released(self,selector);return function(self,selector,*args,**kwargs)
    return entry
