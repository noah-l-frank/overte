"""PCM lease factory on a held actual iOS recording owner; no capabilities."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.audio_runtime import IOSAudioRuntime
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease,INPUT_ORIGIN_PROFILE


def lease(runtime,selector,recorded,*,profile=None):
    need(profile is None or type(profile) is str and profile==INPUT_ORIGIN_PROFILE)
    need(isinstance(runtime,IOSAudioRuntime));recorded.bound()
    need(recorded.store.path==runtime.state_path(selector).with_name('ios-audio-recorded-owner.json'))
    source=runtime._sources(selector);need(source['binding']==recorded.binding)
    preview=source['observer'].recorded_preview_observer()
    return IOSAudioPCMLease(PrivateFeatureState(runtime.state_path(selector).with_name('ios-audio-pcm-lease.json')),
        recorded,native=source['clock_source'],preview=preview,profile=profile)


def close_lease(runtime,selector,recorded):
    """Existing owner, explicit no-allocation close mode on the original SDK."""
    need(isinstance(runtime,IOSAudioRuntime));recorded.bound()
    need(recorded.store.path==runtime.state_path(selector).with_name('ios-audio-recorded-owner.json'))
    source=runtime._sources(selector);need(source['binding']==recorded.binding)
    preview=source['observer'].recorded_preview_observer()
    return IOSAudioPCMLease(PrivateFeatureState(runtime.state_path(selector).with_name('ios-audio-close-lease.json')),
        recorded,native=source['clock_source'],preview=preview,close_only=True)
