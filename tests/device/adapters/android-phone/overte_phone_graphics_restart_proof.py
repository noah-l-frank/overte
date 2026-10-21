"""Closed original Graphics restart receipt; ACKs and PID replacement are insufficient."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re

from adapters.native_feature_observation import exact,need,validate as native_packet
from adapters.native_process_presence import validate as presence_packet
from adapters.normal_feature_state import context
from adapters.restart_inputs import validate_native_restart
from overte_phone_script_history import same
from adapters.native_phone_scene_loads import nonce

VERSION=1


def validate(value):
    exact(value,{'input','oldNative','native','exit'})
    plan=value['input']
    exact(plan,{'restartInputVersion','componentOnly','oldBinding','oldNative','phase','newBinding','newNative','ownerFiles','scriptHandoff'})
    need(type(plan['restartInputVersion']) is int and plan['restartInputVersion']==1 and plan['componentOnly'] is False
        and plan['phase']=='observed' and plan['scriptHandoff'] is None and type(plan['ownerFiles']) is list
        and len(plan['ownerFiles'])==3 and len(set(plan['ownerFiles']))==3 and all(type(path) is str for path in plan['ownerFiles']))
    old,new=context(plan['oldBinding']),context(plan['newBinding'])
    need(all(re.fullmatch('[1-9][0-9]{0,9}:[0-9]{1,20}',binding['processIdentity']) for binding in (old,new)))
    need(all(old[key]==new[key] for key in ('sourceRevision','artifactSha256','sessionId','generation','targetFingerprint')))
    validate_native_restart(plan['oldNative'],plan['newNative'])
    for binding,packet,original in ((old,value['oldNative'],plan['oldNative']),(new,value['native'],plan['newNative'])):
        need(nonce(packet['requestId']) and 'requestedEpochMs' in packet)
        native_packet(packet,packet['requestId'],int(binding['processIdentity'].split(':')[0]),packet['capturedEpochMs'])
        need(same(dict(pid=packet['processId'],instance=packet['instance'],lifecycle=packet['lifecycle']),original))
    before,after=value['oldNative'],value['native']
    need(after['requestedEpochMs']>=before['capturedEpochMs'] and after['graphics']==before['graphics'])
    exit=value['exit'];request=dict(schemaVersion=1,commandId=exit['commandId'],action='feature-process-presence',queryProcessId=before['processId'])
    need(nonce(exit['commandId']))
    presence_packet(exit,request,after['processId'],exit['capturedEpochMs'])
    need(exit['presence']=='absent' and exit['instance']==after['instance'] and exit['capturedEpochMs']>=after['capturedEpochMs'])
    return deepcopy(value)
