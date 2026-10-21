"""Original iOS candidate/native birth and old-PID absence for Graphics restart."""
# Decomposition reviewed at frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# iOS numeric PID binding, source nonces and original clocks remain platform-owned.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_completed_frame import nonce
from adapters.native_feature_observation import exact,need,validate as native_packet
from adapters.native_process_presence import validate as presence_packet
from adapters.normal_feature_state import context
from adapters.restart_inputs import validate_native_restart
from adapters.script_feature.history import same

VERSION=1


def validate(value):
    exact(value,{'input','oldNative','native','exit'});plan=value['input']
    exact(plan,{'restartInputVersion','componentOnly','oldBinding','oldNative','phase','newBinding','newNative','ownerFiles','scriptHandoff'})
    need(type(plan['restartInputVersion']) is int and plan['restartInputVersion']==1 and plan['componentOnly'] is False
         and plan['phase']=='observed' and plan['scriptHandoff'] is None and type(plan['ownerFiles']) is list
         and len(plan['ownerFiles'])==3 and len(set(plan['ownerFiles']))==3 and all(type(path) is str for path in plan['ownerFiles']))
    old,new=context(plan['oldBinding']),context(plan['newBinding'])
    need(all(re.fullmatch('[1-9][0-9]{0,9}',binding['processIdentity']) for binding in (old,new))
         and all(same(old[key],new[key]) for key in ('sourceRevision','artifactSha256','sessionId','generation','targetFingerprint')))
    validate_native_restart(plan['oldNative'],plan['newNative'])
    for binding,packet,original in ((old,value['oldNative'],plan['oldNative']),(new,value['native'],plan['newNative'])):
        need(nonce(packet['requestId']) and 'requestedEpochMs' in packet)
        native_packet(packet,packet['requestId'],int(binding['processIdentity']),packet['capturedEpochMs'])
        need(same(dict(pid=packet['processId'],instance=packet['instance'],lifecycle=packet['lifecycle']),original))
    before,after=value['oldNative'],value['native']
    need(after['requestedEpochMs']>=before['capturedEpochMs'] and same(after['graphics'],before['graphics']))
    exited=value['exit'];need(nonce(exited['commandId']))
    query=dict(schemaVersion=1,commandId=exited['commandId'],action='feature-process-presence',queryProcessId=before['processId'])
    presence_packet(exited,query,after['processId'],exited['capturedEpochMs'])
    need(exited['presence']=='absent' and exited['instance']==after['instance'] and exited['capturedEpochMs']>=after['capturedEpochMs'])
    return deepcopy(value)
