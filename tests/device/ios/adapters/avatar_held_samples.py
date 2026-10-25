"""Explicit sample version two binds the actual held marker scope two.

GPU/PNG acquisition originals and storage formats remain unchanged. Version-one
samples retain their original scope-one and full-drain interpretation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
from ios.adapters.avatar_samples import IOSAvatarSamples


class IOSAvatarHeldSamples(IOSAvatarSamples):
    VERSION=2
    Marker=IOSAvatarHeldMarkerScope


def sample_type(value):
    need(type(value) is dict and type(value.get('iosAvatarSamplesVersion')) is int)
    version=value['iosAvatarSamplesVersion'];need(version in (1,2))
    return IOSAvatarHeldSamples if version==2 else IOSAvatarSamples


def history(value,**kwargs):return sample_type(value).history(value,**kwargs)
