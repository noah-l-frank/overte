"""Existing bound SDK transports for passive Avatar scene originals.

All clock users share the actual independent native reader whose send is
journalled by the source owner. No hidden fresh clock reader escapes ownership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.native_script_files import NativeScriptFiles
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.avatar_file_receipts import IOSAvatarFileReceipts
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_pointers import IOSAvatarPointers
from ios.adapters.script_runtime import IOSScriptRuntime


def owners(runtime,selector,scope,*,epoch_ms,monotonic):
    need(isinstance(runtime,IOSScriptRuntime) and isinstance(scope,IOSAvatarMarkerScope)
        and callable(epoch_ms) and callable(monotonic));scope.bound();scope.lock.assert_held()
    actual=runtime._sources(selector);need(same(actual['binding'],scope.binding))
    clock=actual['clock_source'];need(isinstance(clock,NativeFeatureObservation) and clock.ios and not clock.native_clock_bound
        and clock.pid==int(scope.binding['processIdentity']))
    observer=actual['observer'];original=observer.script_fixture_files();need(isinstance(original,NativeScriptFiles))
    # The product source/API is unchanged. Only this private copy's clock is
    # tied to the already bound, durably journalled native source.
    files=NativeScriptFiles(original.send,original.original,lambda:clock.read(clock.sequence)['capturedEpochMs'],
        original.guard,original.pid,ios=True,monotonic=monotonic,sleep=original.sleep)
    base=runtime.state_path(selector)
    shared=dict(root=scope.root,binding=scope.binding,run=scope.run,role=scope.role,lock=scope.lock,guard=scope.guard,
        native=clock,epoch_ms=epoch_ms,monotonic=monotonic)
    return dict(files=IOSAvatarFileReceipts(PrivateFeatureState(base.with_name('ios-avatar-'+scope.role+'-file-receipts.json')),files=files,**shared),
        pointers=IOSAvatarPointers(PrivateFeatureState(base.with_name('ios-avatar-'+scope.role+'-pointers.json')),pointer=observer.pointer_state(clock),**shared))
