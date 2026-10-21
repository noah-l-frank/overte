"""Original native/UI source floors restored without issuing a live read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need,validate as native_packet
from feature_journeys.contract import identifier

VERSION=1


def restore_native(reader,previous):
    """Restore original source-owned histories without issuing a native read."""
    if previous is None:return
    native_packet(previous,identifier(previous.get('requestId')),reader.pid,previous.get('capturedEpochMs'))
    need(reader.instance is None and reader.sequence==0 and reader.lifecycle is None
         and reader.rig is None and reader.rig_sequence==0 and reader.voice_event_sequence==0
         and reader.voice_history is None and reader.animation_history is None and reader.account_history is None)
    reader.instance,reader.sequence=previous['instance'],previous['sequence']
    reader.lifecycle=deepcopy(previous['lifecycle'])
    recorded=previous['audio'].get('recordedVoice',{})
    reader.voice_event_sequence=recorded.get('event',{}).get('eventSequence',0)
    if 'historyVersion' in recorded:
        from adapters.recorded_preview_history import accept_history
        reader.voice_history=accept_history(None,recorded)
    animation=previous['animation']
    if 'history' in animation:
        from adapters.native_animation_history import accept
        reader.animation_history=accept(None,animation['rigId'],animation['history'])
    if 'observation' in previous['account']:
        from adapters.native_account_observation import accept
        reader.account_history=accept(None,previous['account'])


def restore_ui(reader,previous,validator):
    if previous is None:return
    validator(previous,identifier(previous.get('commandId')),reader.pid,previous.get('capturedEpochMs'))
    need(reader.instance is None and reader.generation is None and reader.sequence==0)
    reader.instance,reader.generation=previous['instance'],previous['generation']
    reader.sequence,reader.elapsed=previous['sourceSequence'],previous['elapsedMs']
    reader.last_command,reader.epoch_floor=previous['lastCommandSequence'],previous['capturedEpochMs']
    restore=getattr(reader,'restore_inventory',None)
    if callable(restore):restore(previous)
