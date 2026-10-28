"""Explicit rooted Observer3/Recovery2 consumer for original CallbackSample3.

Default rooted/ordinary owners remain closed for these profiles. The existing
connection: native callback vocabulary records real duty, never a ready ACK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import partial
from adapters.native_feature_observation import need
from adapters.script_feature.history import unpack
from ios.adapters.emote_images import changed,callback_duty
from ios.adapters.emote_sample_recovery import IOSEmoteSampleRecovery,validate_abandonment
from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples,archived_sample
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObservationDecoder,IOSEmoteRootedObserver

RESOURCE='connection:emote-native-callbacks'
validate_abandonment3=partial(validate_abandonment,sample_versions=(3,))


class IOSEmoteCallbackSampleRecovery(IOSEmoteSampleRecovery):
    FormatVersion=2
    SampleReads=(3,)
    ValidateAbandonment=staticmethod(validate_abandonment3)


class IOSEmoteCallbackRootedDecoder(IOSEmoteRootedObservationDecoder):
    ImageArchive=staticmethod(archived_sample)
    ImageChange=staticmethod(partial(changed,callback_only=True))

    def image_resources(self,value):
        sample=value['image']
        # Retired/no-image originals do not yet carry the full typed drain
        # envelope. Keep that future terminal slice closed rather than infer
        # global absence from a live drain performed before this original.
        need(sample is not None)
        # derive() already fully validated this exact sample/image/owner/PNG
        # before asking for its as-of-cut public responsibility. No native
        # query or fresh absence is inferred by this historical decoder.
        need(type(sample['iosEmoteSampleVersion']) is int and sample['iosEmoteSampleVersion']==3)
        frames=unpack(sample['payload']);need(len(frames)==1)
        return [RESOURCE] if callback_duty(frames[0]['retirement']) else []


class IOSEmoteCallbackRootedObserver(IOSEmoteRootedObserver):
    OwnerVersion=3
    OwnerReads=(3,)
    Decoder=IOSEmoteCallbackRootedDecoder
    SampleRecovery=IOSEmoteCallbackSampleRecovery

    def __init__(self,*args,**kwargs):
        need(isinstance(kwargs.get('samples'),IOSEmoteCallbackSamples))
        super().__init__(*args,**kwargs)

    def observe(self,after_sequence,*,input_barrier=None,retired=False):
        # No-image/quiet observations cannot erase a known previous duty. The
        # original live owner must independently inspect/drain it first.
        if retired or self.samples.scope.state['phase']!='ready':self.samples.drain()
        return super().observe(after_sequence,input_barrier=input_barrier,retired=retired)

    def abandon_read(self):
        if self.state['pending'] is not None and self.state['pending']['original'] is None:
            # Reentry may not block in the old drain loop while an actual
            # previously observed callback still owns its ticket. The selected
            # feature propagates this typed readiness only after SDK unwind.
            self.samples.before_capture()
        return super().abandon_read()
