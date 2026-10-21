"""Restore original source floors only; no transport or fresh measurements."""
# Decomposition reviewed at frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import NativeFeatureObservation,need,validate
from ios.adapters.login_source import nonce

VERSION=1


def restore_native(reader,previous):
    need(isinstance(reader,NativeFeatureObservation) and reader.ios and reader.native_clock_bound)
    if previous is None:return
    need(nonce(previous.get('requestId')))
    validate(previous,previous['requestId'],reader.pid,previous.get('capturedEpochMs'))
    need(reader.instance is None and reader.sequence==0 and reader.lifecycle is None
         and reader.captured_epoch==0 and reader.voice_event_sequence==0
         and reader.voice_history is None and reader.animation_history is None and reader.account_history is None
         and reader.rig is None and reader.rig_sequence==0)
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
    reader.instance,reader.sequence=previous['instance'],previous['sequence']
    reader.captured_epoch=previous['capturedEpochMs'];reader.lifecycle=deepcopy(previous['lifecycle'])
    reader.voice_event_sequence=recorded.get('event',{}).get('eventSequence',0)
    reader.voice_history,reader.animation_history,reader.account_history=deepcopy(voice),deepcopy(animation),deepcopy(account)


def follow_native(before,after):
    """Pure original-source prefix validation, including every present history."""
    for packet in (before,after):
        need(type(packet) is dict and nonce(packet.get('requestId')))
        validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'])
    need(after['processId']==before['processId'] and after['instance']==before['instance']
         and after['requestId']!=before['requestId'] and after['sequence']>before['sequence']
         and after['requestedEpochMs']>=before['capturedEpochMs'] and after['capturedEpochMs']>=before['capturedEpochMs']
         and all(after['lifecycle'][k]>=v for k,v in before['lifecycle'].items()))
    old,new=before['account'],after['account']
    if 'observation' in old:
        from adapters.native_account_observation import accept
        need('observation' in new);accept(accept(None,old),new)
    old,new=before['animation'],after['animation']
    if 'history' in old:
        from adapters.native_animation_history import accept
        need('history' in new);accept(accept(None,old['rigId'],old['history']),new['rigId'],new['history'])
    old,new=before['audio'].get('recordedVoice',{}),after['audio'].get('recordedVoice',{})
    need(new.get('event',{}).get('eventSequence',0)>=old.get('event',{}).get('eventSequence',0))
    if 'historyVersion' in old:
        from adapters.recorded_preview_history import accept_history
        need('historyVersion' in new);accept_history(accept_history(None,old),new)
