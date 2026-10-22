"""Preserve all original native histories across Emote clock boundaries.

Historical v1 Emote archives used the common unprefixed nonce grammar. Current
iOS reads retain their ios- prefix; neither original identity is rewritten.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import need,validate

VERSION=1


def follow(before,after):
    for value in (before,after):
        need(type(value) is dict and type(value.get('requestId')) is str
            and re.fullmatch('(?:ios-)?[0-9a-f]{32}',value['requestId']))
        validate(value,value['requestId'],value['processId'],value['capturedEpochMs'])
    need(before['instance']==after['instance'] and before['processId']==after['processId']
        and after['requestId']!=before['requestId'] and after['sequence']>before['sequence']
        and after['requestedEpochMs']>=before['capturedEpochMs'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and all(after['lifecycle'][key]>=count for key,count in before['lifecycle'].items()))
    old,new=before['animation'],after['animation']
    if 'history' in old:
        from adapters.native_animation_history import accept
        need('history' in new);accept(accept(None,old['rigId'],old['history']),new['rigId'],new['history'])
    old,new=before['account'],after['account']
    if 'observation' in old:
        from adapters.native_account_observation import accept
        need('observation' in new);accept(accept(None,old),new)
    old,new=before['audio'].get('recordedVoice',{}),after['audio'].get('recordedVoice',{})
    need(new.get('event',{}).get('eventSequence',0)>=old.get('event',{}).get('eventSequence',0))
    if 'historyVersion' in old:
        from adapters.recorded_preview_history import accept_history
        need('historyVersion' in new);accept_history(accept_history(None,old),new)
