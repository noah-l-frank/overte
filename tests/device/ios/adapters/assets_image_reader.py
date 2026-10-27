"""Independent ImageReader observer, never decoder/GPU/base/pool completion.

Queued receipts remain independent even when their payload looks unique.
Only the native synchronous invoke scope can supply direct attribution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.assets_model_origin import identity,stamp,ordered
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
HISTORY_VERSION=1
HISTORY_READS=(1,)
ACTION='feature-ios-assets-image-reader'
FILE=ACTION+'.json'
LIMIT=262144
PHASES=('constructorEntered','constructorReturned','runEntered','runReturned','runUnwound','readEntered','readReturned','readUnwound')
UNAVAILABLE=('queuedReceiverAttributionAvailable','ktxCompletionAvailable','byteCopyCompletionAvailable',
    'basePoolCompletionAvailable','decoderCompletionAvailable','gpuCompletionAvailable','resourceRetirementAvailable')


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
        and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}',value['runId']))
    return value


def end(row,entered,normal,unwound,clock):
    for key in (entered,normal,unwound):
        if row[key] is not None:stamp(row[key],clock)
    need(row[normal] is None or row[unwound] is None)
    ordered(row[entered],row[normal]);ordered(row[entered],row[unwound])


def dimensions(row):
    need(integer(row['width'],0,2**31-1) and integer(row['height'],0,2**31-1)
        and type(row['gpuKnown']) is bool and type(row['gpuOwnersAlive']) is bool
        and (row['gpuKnown'] or not row['gpuOwnersAlive']))


def history(value,before,after):
    exact(value,{'assetImageReaderHistoryVersion','instance','complete','clockDomain','clock','tasks','dispatches','receivers'}|set(UNAVAILABLE))
    need(type(value['assetImageReaderHistoryVersion']) is int and value['assetImageReaderHistoryVersion']==HISTORY_VERSION
        and type(value['complete']) is bool and value['clockDomain']=='native-assets-image-reader-observer'
        and all(value[key] is False for key in UNAVAILABLE))
    identity(value['instance']);stamp(value['clock'])
    # Inner observer monotonic time has its own epoch. It is not compared to
    # the outer main-thread bracket's distinct timer.
    need(before['epochMs']<=value['clock']['epochMs']<=after['epochMs'])
    need(type(value['tasks']) is list and len(value['tasks'])<=64
        and type(value['dispatches']) is list and len(value['dispatches'])<=256
        and type(value['receivers']) is list and len(value['receivers'])<=256)
    clock=value['clock'];tasks={};dispatches={};receivers=set();direct=set()
    for row in value['tasks']:
        exact(row,{'id','resourceId','resourceUrlFullyEncodedBytes','resourceUrlFullyEncodedSha256','constructorContentBytes',
            'derivedMarkerAlive','originalLeaseAlive','resourceObjectAlive','sourceOwnersAlive'}|set(PHASES))
        identity(row['id']);identity(row['resourceId']);need(row['id'] not in tasks);tasks[row['id']]=row
        need(integer(row['resourceUrlFullyEncodedBytes'],0,4096)
            and type(row['resourceUrlFullyEncodedSha256']) is str and re.fullmatch('[a-f0-9]{64}',row['resourceUrlFullyEncodedSha256'])
            and integer(row['constructorContentBytes'],0,2**63-1)
            and all(type(row[key]) is bool for key in ('derivedMarkerAlive','originalLeaseAlive','resourceObjectAlive','sourceOwnersAlive')))
        for key in PHASES:
            if row[key] is not None:stamp(row[key],clock)
        need(row['constructorEntered'] is not None);ordered(row['constructorEntered'],row['constructorReturned'])
        ordered(row['constructorReturned'],row['runEntered']);ordered(row['runEntered'],row['readEntered'])
        end(row,'runEntered','runReturned','runUnwound',clock);end(row,'readEntered','readReturned','readUnwound',clock)
        for field in ('readReturned','readUnwound'):
            for last in ('runReturned','runUnwound'):
                if row[field] is not None and row[last] is not None:ordered(row[field],row[last])
        if row['readEntered'] is not None and row['runReturned'] is not None:need(row['readReturned'] is not None)
    for row in value['dispatches']:
        exact(row,{'id','taskId','branch','width','height','gpuKnown','gpuOwnersAlive','entered','invokeReturned','invokeAccepted'})
        identity(row['id']);need(row['id'] not in dispatches);dispatches[row['id']]=row
        need(type(row['taskId']) is str and row['taskId'] in tasks and row['branch'] in ('cache-reuse','decode-failed','final-output'))
        dimensions(row);stamp(row['entered'],clock);task=tasks[row['taskId']];ordered(task['readEntered'],row['entered'])
        if row['branch']=='decode-failed':need(not row['gpuKnown'] and row['width']==row['height']==0)
        if row['branch']=='cache-reuse':need(row['gpuKnown'])
        if row['invokeReturned'] is None:need(row['invokeAccepted'] is None)
        else:
            stamp(row['invokeReturned'],clock);ordered(row['entered'],row['invokeReturned']);need(type(row['invokeAccepted']) is bool)
            for field in ('readReturned','readUnwound'):
                if task[field] is not None:ordered(row['invokeReturned'],task[field])
    for row in value['receivers']:
        exact(row,{'id','resourceId','width','height','gpuKnown','gpuOwnersAlive','entered','returned','unwound','dispatchId',
            'attribution','sourceKnown','sourceOwnersAlive'})
        identity(row['id']);identity(row['resourceId']);need(row['id'] not in receivers);receivers.add(row['id'])
        need(row['resourceId'] in {task['resourceId'] for task in tasks.values()}
            and type(row['sourceKnown']) is bool and type(row['sourceOwnersAlive']) is bool
            and (row['sourceKnown'] or not row['sourceOwnersAlive']))
        dimensions(row);need(row['entered'] is not None);end(row,'entered','returned','unwound',clock)
        if row['dispatchId'] is None:need(row['attribution']=='unavailable-queued-or-other-producer')
        else:
            need(type(row['dispatchId']) is str and row['dispatchId'] in dispatches
                and row['dispatchId'] not in direct and row['attribution']=='synchronous-invoke-scope');direct.add(row['dispatchId'])
            parent=dispatches[row['dispatchId']];task=tasks[parent['taskId']]
            need(row['resourceId']==task['resourceId'] and all(row[key]==parent[key] for key in ('width','height','gpuKnown')))
            ordered(parent['entered'],row['entered'])
            if parent['invokeReturned'] is not None:
                need(parent['invokeAccepted'] and row['returned'] is not None);ordered(row['returned'],parent['invokeReturned'])
    return value


def successor(before,after):
    need(before['instance']==after['instance'] and (before['complete'] or not after['complete']))
    ordered(before['clock'],after['clock'])
    for name,phases,liveness in (('tasks',PHASES,('derivedMarkerAlive','originalLeaseAlive','resourceObjectAlive','sourceOwnersAlive')),
            ('dispatches',('invokeReturned','invokeAccepted'),('gpuOwnersAlive',)),
            ('receivers',('returned','unwound'),('gpuOwnersAlive','sourceOwnersAlive'))):
        need(len(after[name])>=len(before[name]))
        for first,last in zip(before[name],after[name]):
            for key in first:
                if key in liveness:need(first[key] or not last[key])
                elif key in phases:
                    if first[key] is not None:need(same(first[key],last[key]))
                    elif type(last[key]) is dict:ordered(before['clock'],last[key])
                else:need(same(first[key],last[key]))


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAssetsImageReaderVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsImageReaderVersion']) is int and value['iosAssetsImageReaderVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-assets-image-reader');identity(value['instance'])
    a,b=value['clockBefore'],value['clockAfter'];stamp(a);stamp(b);ordered(a,b)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500
        and abs((b['epochMs']-a['epochMs'])-(b['monotonicMs']-a['monotonicMs']))<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    history(value['source'],a,b)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'])
        ordered(previous['clockAfter'],a);successor(previous['source'],value['source'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def tasks(value):
    """Observed task lifecycle facts only, with every completion flag false."""
    original(value);need(value['source']['complete'] and value['source']['tasks'])
    return deepcopy(value['source'])


class IOSAssetsImageReader(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAssetsImageReaderAcquisitionVersion'
