"""Existing Emote observation pipeline with the explicit scope-three reader."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.emote_held_observation import IOSEmoteHeldObservationDecoder,IOSEmoteHeldObserver
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope


class IOSEmoteRootedObservationDecoder(IOSEmoteHeldObservationDecoder):
    Marker=IOSEmoteRootedMarkerScope


class IOSEmoteRootedObserver(IOSEmoteHeldObserver):
    Decoder=IOSEmoteRootedObservationDecoder
