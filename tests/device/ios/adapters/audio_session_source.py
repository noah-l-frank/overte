"""Passive actual OS authorization and cached gate facts, separately named."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters.keyboard_source import clock,identifier
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-audio-session'
FILE=ACTION+'.json'
LIMIT=8192


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and value['commandId'].startswith('ios-'))
    identifier(value['commandId'][4:]);identifier(value['runId']);return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAudioSessionVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','lifecycle','source'})
    need(type(value['iosAudioSessionVersion']) is int and value['iosAudioSessionVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and integer(pid,1) and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-audio-session')
    identifier(value['instance']);a,b=value['clockBefore'],value['clockAfter'];clock(a);clock(b,floor=a)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    life=value['lifecycle'];exact(life,{'backgrounds','activations','launches'})
    need(all(integer(count,0,1000000) for count in life.values()) and life['launches']>=1)
    source=value['source'];exact(source,{'available','osPermission','gatePermission','outcome',
        'foreground','interrupted','captureAllowed','playbackAllowed','outputRevision'})
    for key in ('available','foreground','interrupted','captureAllowed','playbackAllowed'):need(type(source[key]) is bool)
    need(integer(source['osPermission'],0,3) and integer(source['gatePermission'],0,3)
        and integer(source['outcome'],0,6) and integer(source['outputRevision']))
    if source['captureAllowed']:need(source['available'] and source['gatePermission']==1 and source['outcome']==2
        and source['foreground'] and not source['interrupted'])
    if not source['available']:need(not source['captureAllowed'] and not source['playbackAllowed'] and source['osPermission']==0)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and source['outputRevision']>=previous['source']['outputRevision'] and all(life[key]>=count for key,count in previous['lifecycle'].items()))
        clock(a,floor=previous['clockAfter'])
    return value


def definite_permission(value):
    validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])
    source=value['source'];need(source['available'] and source['osPermission'] in (1,2))
    return 'granted' if source['osPermission']==1 else 'denied'


class IOSAudioSession(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAudioSessionAcquisitionVersion'
