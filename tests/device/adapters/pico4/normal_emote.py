"""Original Pico Emote chooser over the existing VR tablet pointer transport."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import control_id,snapshot,same_reference


def project(original):
    need(type(original.get('emoteControlsVersion')) is int and original['emoteControlsVersion']==2)
    controls=[]
    for original_row in original['controls']:
        if not control_id(original_row['id']):continue
        row=deepcopy(original_row)
        # Shared navigation rows have no feature-specific readiness flag. This
        # admission follows their measured native enabled/visible survey; the
        # native dispatcher independently checks exact ownership at delivery.
        if row['id'].startswith('tablet.'):
            need(set(row)<= {'id','token','enabled','focused','inputReady'})
            row['inputReady']=original['ready'] and row['enabled']
        controls.append(row)
    return snapshot(dict(emoteControlsVersion=2,open=original['open'],ready=original['ready'],controls=controls,
        scope=dict(instance=original['bridgeId'],generation=original['generation'],sequence=original['lastCommandSequence'],
            sourceSequence=original['emoteSourceSequence'],elapsedMs=original['elapsedMs'],
            capturedEpochMs=original['updatedEpochMs'],processId=original['processId'])))


class PicoEmoteIO:
    def __init__(self,original,*,before_send=None):
        self.original=original
        if before_send is not None:self.original.navigation.io.bind_before_send(before_send)
    def capture(self):
        try:return project(self.original.capture())
        except Exception:raise NativeUIError('Pico original Emote UI is unavailable or invalid') from None
    def activate(self,identifier,*,reference):self.original.navigation.input(identifier,reference=reference)
    def scroll(self,identifier,direction,*,reference):
        self.original.navigation.input(identifier,'scroll',direction=direction,reference=reference)
