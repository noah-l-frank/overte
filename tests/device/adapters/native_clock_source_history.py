"""Restore pristine unbound iOS native-clock cursors from actual originals.

This is historical bookkeeping, never a measurement or a new source clock. A
bound reader is refused; neither the reader kind nor original DTO is relabelled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import NativeFeatureObservation,need,validate
from ios.adapters.login_source import nonce


def restore(reader,previous):
    need(isinstance(reader,NativeFeatureObservation) and reader.ios and not reader.native_clock_bound)
    if previous is None:return
    need(nonce(previous.get('requestId')))
    validate(previous,previous['requestId'],reader.pid,previous.get('capturedEpochMs'))
    need(reader.instance is None and reader.sequence==0 and reader.lifecycle is None and reader.captured_epoch==0
        and reader.voice_event_sequence==0 and reader.voice_history is None and reader.animation_history is None
        and reader.account_history is None and reader.rig is None and reader.rig_sequence==0)
    recorded=previous['audio'].get('recordedVoice',{});voice=animation=account=None
    if 'historyVersion' in recorded:
        from adapters.recorded_preview_history import accept_history
        voice=accept_history(None,recorded)
    if 'history' in previous['animation']:
        from adapters.native_animation_history import accept
        animation=accept(None,previous['animation']['rigId'],previous['animation']['history'])
    if 'observation' in previous['account']:
        from adapters.native_account_observation import accept
        account=accept(None,previous['account'])
    reader.instance,reader.sequence=previous['instance'],previous['sequence'];reader.captured_epoch=previous['capturedEpochMs']
    reader.lifecycle=deepcopy(previous['lifecycle']);reader.voice_event_sequence=recorded.get('event',{}).get('eventSequence',0)
    reader.voice_history,reader.animation_history,reader.account_history=deepcopy(voice),deepcopy(animation),deepcopy(account)
