"""Explicit component v2 retains actual rooted Emote holders before OS end.

This decodes original native/input/file/pixel cleanup, not complete process
retirement. Legacy component v1 keeps its literal full-resource-drain readers.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters import original_marker_holders as holders
from adapters.native_feature_observation import need
from ios.adapters.emote_retirement import IOSEmoteRetirement
from ios.adapters.emote_rendered_retirement import IOSEmoteRenderedRetirement
from ios.adapters.emote_keyed_retirement import IOSEmoteKeyedRetirement
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObservationDecoder
from ios.adapters.emote_archive_round import derived,component_read


class IOSEmoteRootedNativeRetirement(IOSEmoteRetirement):
    FORMAT_VERSION=2
    Marker=IOSEmoteRootedMarkerScope
    Decoder=IOSEmoteRootedObservationDecoder

    def __init__(self,*args,**kwargs):
        # No component may write v1 under a new class on unintegrated hooks.
        need(getattr(IOSEmoteRetirement,'FORMAT_VERSION',None)==1)
        super().__init__(*args,**kwargs)

    def web_quiet(self,scope,current,admitted):
        need(type(scope) is self.Marker)
        return holders.web('emote',current['web'],admitted['web'],partial=scope.state['cleanupMode']!='full')

    def decode(self,value):
        return component_read(self,value,lambda:super(IOSEmoteRootedNativeRetirement,self).decode(value))

    def derive(self,reference):
        return component_read(self,reference,lambda:derived(self,reference,lambda:self.derive_original(reference)))

    def derive_original(self,reference):
        derived=super().derive(reference);original=self.original(reference)
        scope=self.Marker.archive(original['scope'],root=self.root,binding=self.binding,
            run=self.run,role=self.role,lock=self.lock)
        # This extra private projection cannot pass a legacy Complete publisher.
        # Every normal public/source fact retains its unchanged original DTO.
        return dict(derived,held=scope.held_originals())


class IOSEmoteRootedRenderedRetirement(IOSEmoteRenderedRetirement):
    FORMAT_VERSION=2
    Marker=IOSEmoteRootedMarkerScope

    def __init__(self,store,native,frames,*,historical=False):
        need(type(native) is IOSEmoteRootedNativeRetirement)
        super().__init__(store,native,frames,historical=historical)

    def derive(self,reference):
        def checked():
            self.lock.assert_held();self.primary_lock.assert_held()
            # Membership is current owner context, not an immutable fact of
            # the reference. It must run even when a derivation is reused.
            need(self.original(reference)['nativeReference'] in self.native_owner.state['records'])
            return derived(self,reference,lambda:super(IOSEmoteRootedRenderedRetirement,self).derive(reference))
        return component_read(self,reference,checked)

    def decode(self,value):
        return component_read(self,value,lambda:super(IOSEmoteRootedRenderedRetirement,self).decode(value))


class IOSEmoteRootedKeyedRetirement(IOSEmoteKeyedRetirement):
    FORMAT_VERSION=2
    Marker=IOSEmoteRootedMarkerScope

    def __init__(self,store,rendered,keys,*,historical=False):
        need(type(rendered) is IOSEmoteRootedRenderedRetirement)
        super().__init__(store,rendered,keys,historical=historical)

    def derive(self,reference):
        def checked():
            self.lock.assert_held();self.primary_lock.assert_held()
            need(self.original(reference)['renderedReference'] in self.rendered_owner.state['records'])
            return derived(self,reference,lambda:super(IOSEmoteRootedKeyedRetirement,self).derive(reference))
        return component_read(self,reference,checked)

    def decode(self,value):
        return component_read(self,value,lambda:super(IOSEmoteRootedKeyedRetirement,self).decode(value))
