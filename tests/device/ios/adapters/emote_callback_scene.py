"""Explicit callback Rendered4/Keyed4/Scene4 over original Native4 evidence.

No legacy constructor is opened or normalized. Original world pixels, key/IME,
Scope holders, current owner membership and clocks retain their existing guards.
This source profile stops at scene quiet; paired Live/OS/SDK end stays closed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.emote_callback_retirement import IOSEmoteCallbackNativeRetirement,IOSEmoteCallbackRetirementFeature,PROFILE5
from ios.adapters.emote_rendered_retirement import IOSEmoteRenderedRetirement
from ios.adapters.emote_keyed_retirement import IOSEmoteKeyedRetirement
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedRenderedRetirement,IOSEmoteRootedKeyedRetirement
from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_observer import EmoteObservationPending

VERSION=4


class IOSEmoteCallbackRenderedRetirement(IOSEmoteRootedRenderedRetirement):
    FORMAT_VERSION=VERSION

    def __init__(self,store,native,frames,*,historical=False):
        need(type(native) is IOSEmoteCallbackNativeRetirement)
        # The unchanged underlying constructor performs all binding/root/
        # original frame-owner checks. Rooted2's exact type gate stays literal.
        IOSEmoteRenderedRetirement.__init__(self,store,native,frames,historical=historical)


class IOSEmoteCallbackKeyedRetirement(IOSEmoteRootedKeyedRetirement):
    FORMAT_VERSION=VERSION

    def __init__(self,store,rendered,keys,*,historical=False):
        need(type(rendered) is IOSEmoteCallbackRenderedRetirement)
        IOSEmoteKeyedRetirement.__init__(self,store,rendered,keys,historical=historical)


class IOSEmoteCallbackSceneRetirement(IOSEmoteRootedSceneRetirement):
    def __init__(self,owner):
        need(type(owner) is IOSEmoteCallbackKeyedRetirement);self.owner=owner


PROFILE6=dict(PROFILE5,callbackProfileVersion=3,renderedRetirementVersion=4,keyedRetirementVersion=4,sceneProfileVersion=4)


class IOSEmoteCallbackSceneFeature(IOSEmoteCallbackRetirementFeature):
    FORMAT_VERSION=6
    PAIRED_FORMAT_VERSION=6
    RenderedRetirement=IOSEmoteCallbackRenderedRetirement
    KeyedRetirement=IOSEmoteCallbackKeyedRetirement

    def profile_envelope(self,state):
        value=IOSEmoteRootedFeature.profile_envelope(self,state)
        if self.previous is not None:need(self.previous.get('iosEmoteFeatureVersion')==6 and same(self.previous.get('callbackProfile'),PROFILE6))
        return dict(value,callbackProfile=deepcopy(PROFILE6))

    def rendered_retirement_owner(self,parts,*,native=None):
        return IOSEmoteFeature.rendered_retirement_owner(self,parts,native=native)

    def retirement_sample(self,parts,after_sequence=0,*,fresh_end=False):
        # This explicit scene profile has not created a legacy RootedLive2
        # owner. The original component recovery/quiet/input/source pipeline
        # repeats, preserving existing Native4/Rendered4/Keyed4 once-only WALs.
        return IOSEmoteFeature.retirement_sample(self,parts,after_sequence,fresh_end=fresh_end)

    def retirement_public(self,owner,reference,public):
        value=IOSEmoteCallbackSceneRetirement(owner).read(reference)
        need(same(value['sourcePublic'],public));return value['public']

    def retirement_decoder(self,owner):return IOSEmoteCallbackSceneRetirement(owner).actor_original

    def terminal(self,call):
        raise EmoteObservationPending('Callback Scene4 is retained; paired Live/process/SDK end profile remains closed')
