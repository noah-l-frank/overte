"""Closed historical dispatch for unchanged Avatar marker scope originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope


def scope_type(value):
    need(type(value) is dict and type(value.get('iosAvatarMarkerScopeVersion')) is int)
    version=value['iosAvatarMarkerScopeVersion'];need(version in (1,2))
    return IOSAvatarHeldMarkerScope if version==2 else IOSAvatarMarkerScope


def archive(value,**kwargs):return scope_type(value).archive(value,**kwargs)
