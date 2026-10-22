"""Selected iOS native-QML Emote controls over existing ordinary Qt input.

The semantic projection retains exact original tokens and native clocks. Tablet
navigation eligibility is derived only from the validated original visible frame;
it supplies no pose, animation or feature verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid
from adapters.native_feature_observation import need,integer
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import control_id,metadata,snapshot,same_reference

VERSION=2
READS=(1,2)


def project(original):
    need(type(original) is dict and type(original.get('emoteControlsVersion')) is int
        and original['emoteControlsVersion'] in READS and integer(original.get('emoteSourceSequence'),1))
    if original['emoteControlsVersion']==2:
        from ios.adapters.emote_ui_inventory import validate
        validate(original['emoteInventory'])
    rows=deepcopy([row for row in original['controls'] if control_id(row['id'])])
    for row in rows:
        frame=row.pop('frame')
        if not row['id'].startswith('emote.'):
            need(type(frame) is dict and frame['width']>0 and frame['height']>0)
            row['inputReady']=row['enabled']
        metadata(row)
    return snapshot(dict(emoteControlsVersion=1,open=original['tabletShown'],ready=original['ready'],
        scope=dict(instance=original['instance'],generation=original['emoteGeneration'],sequence=original['lastSequence'],
            sourceSequence=original['emoteSourceSequence'],elapsedMs=original['elapsedMs'],
            capturedEpochMs=original['sampleEpochMs'],processId=original['processId']),controls=rows))


class IOSEmoteIO:
    def __init__(self,native):
        need(callable(native.capture) and callable(native.deliver));self.native=native
        self.original_packet=None

    def capture(self):
        original=self.native.capture();value=project(original)
        self.original_packet=deepcopy(original);return value

    def input(self,identifier,*,reference,direction=None):
        need(control_id(identifier) and identifier!='emote.page'
            and (direction in ('up','down') if identifier=='emote.grid' else direction is None))
        current=self.capture();row=same_reference(reference,current,identifier)
        need(current['open'] and current['ready'] and row['enabled'] and row['inputReady'])
        scope=reference['scope']
        request=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=scope['instance'],
            sequence=scope['sequence']+1,observedElapsedMs=scope['elapsedMs'],fieldToken=row['token'],
            operation='scroll' if direction else 'activate')
        if direction:request['direction']=direction
        # Ownership must be durably journalled by the caller before this point.
        # A lost return propagates; no retry is sent by this transport.
        self.native.deliver(request)

    def activate(self,identifier,*,reference):self.input(identifier,reference=reference)
    def scroll(self,identifier,direction,*,reference):self.input(identifier,reference=reference,direction=direction)
