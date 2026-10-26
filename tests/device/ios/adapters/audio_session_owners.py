"""Fail closed before ordinary SDK work with unretired Audio responsibility.

Page closure and tap retirement are useful components, not a complete Audio
callback/source/process retirement proof. No such final protocol exists yet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from feature_journeys.contract import identifier

PREFIX='ios-audio-'


def owners_absent(adapter,selector):
    root=adapter.state_path(selector).parent
    if not root.exists():return True
    PrivateFeatureState(root/'audio-entry-boundary.json')._parent()
    entries=list(root.iterdir());need(len(entries)<=4096)
    return not any(path.name.startswith(PREFIX) for path in entries)


def ensure_released(adapter,selector):
    if not owners_absent(adapter,selector):
        raise NativeUIError('Audio ownership requires original complete cleanup before ordinary session operations')
    return True


def register_scope(adapter,selector,binding,run,artifact_root):
    """Persist the source location before any Audio input or evidence write.

    This also keeps external artifact roots discoverable if their operation
    owner is lost. It supplies no native or cleanup fact.
    """
    root=Path(artifact_root);need(root.is_absolute() and root.resolve()==root)
    value=dict(iosAudioScopeVersion=1,binding=context(binding),runId=identifier(run),artifactRoot=str(root))
    store=PrivateFeatureState(adapter.state_path(selector).with_name('ios-audio-scope.json'));previous=store.read()
    if previous is None:store.write(value,None)
    else:need(same(previous,value))
    need(same(store.read(),value));return value


def installed_entry(function):
    @wraps(function)
    def entry(self,selector,*args,**kwargs):
        ensure_released(self,selector);return function(self,selector,*args,**kwargs)
    return entry
