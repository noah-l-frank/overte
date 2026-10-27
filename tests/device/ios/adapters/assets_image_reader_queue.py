"""Separate strict queued-source facts; no storage/GPU/Resource retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from ios.adapters.assets_model_origin import identity,stamp,ordered
from ios.adapters import assets_image_reader as parent_source
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
HISTORY_VERSION=1
HISTORY_READS=(1,)
ACTION='feature-ios-assets-image-reader-queue'
FILE=ACTION+'.json'
LIMIT=262144
PHASES=('bindingEntered','invokeReturned','receiverEntered','receiverReturned','receiverUnwound')
QT_PHASES=('created','deliveryEntered','deliveryReturned','deliveryUnwound','argumentValuesDestroyed')
UNAVAILABLE=('eventStorageCompletionAvailable','byteCopyCompletionAvailable','basePoolCompletionAvailable',
    'decoderCompletionAvailable','gpuCompletionAvailable','resourceRetirementAvailable')


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
        and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}',value['runId']))
    return value


def qt_stamp(value,upper):
    exact(value,{'epochMs','steadyNs'})
    need(integer(value['epochMs'],1,upper['epochMs']) and type(value['steadyNs']) is str
        and re.fullmatch(r'-?(?:0|[1-9][0-9]{0,18})',value['steadyNs'])
        and value['steadyNs']!='-0' and -(2**63)<=int(value['steadyNs'])<=2**63-1)
    return value


def qt_ordered(before,after):
    if after is not None:
        need(before is not None and before['epochMs']<=after['epochMs']
            and int(before['steadyNs'])<=int(after['steadyNs']))


def history(value,before,after):
    exact(value,{'assetImageReaderQueueHistoryVersion','instance','source1Instance','complete',
        'clockDomain','clock','qtClockDomain','entries'}|set(UNAVAILABLE))
    need(type(value['assetImageReaderQueueHistoryVersion']) is int and value['assetImageReaderQueueHistoryVersion']==1
        and type(value['complete']) is bool and value['clockDomain']=='native-assets-image-reader-queue-observer'
        and value['qtClockDomain']=='qtcore-metacall-steady-nanoseconds'
        and all(value[key] is False for key in UNAVAILABLE))
    identity(value['instance']);identity(value['source1Instance']);stamp(value['clock'])
    need(before['epochMs']<=value['clock']['epochMs']<=after['epochMs']
        and type(value['entries']) is list and 1<=len(value['entries'])<=256)
    dispatches=set();events=set();receivers=set();clock=value['clock']
    for row in value['entries']:
        exact(row,{'dispatchId','taskId','resourceId','methodIndex','invokeAccepted','eventId','receiverId',
            'receiverObjectAlive'}|set(PHASES)|set(QT_PHASES))
        for key in ('dispatchId','taskId','resourceId'):identity(row[key])
        need(row['dispatchId'] not in dispatches);dispatches.add(row['dispatchId'])
        need(integer(row['methodIndex'],0,131070) and type(row['receiverObjectAlive']) is bool
            and row['bindingEntered'] is not None)
        for key in PHASES:
            if row[key] is not None:stamp(row[key],clock)
        for key in QT_PHASES:
            if row[key] is not None:qt_stamp(row[key],clock)
        if row['invokeReturned'] is None:need(row['invokeAccepted'] is None)
        else:need(type(row['invokeAccepted']) is bool);ordered(row['bindingEntered'],row['invokeReturned'])
        if row['eventId'] is None:
            need(all(row[key] is None for key in QT_PHASES)
                and all(row[key] is None for key in ('receiverId','receiverEntered','receiverReturned','receiverUnwound')))
        else:
            need(integer(row['eventId'],1,256) and row['eventId'] not in events and row['created'] is not None)
            events.add(row['eventId'])
            need(row['bindingEntered']['epochMs']<=row['created']['epochMs'])
            if row['invokeReturned'] is not None:
                need(row['invokeAccepted'] and row['created']['epochMs']<=row['invokeReturned']['epochMs'])
            need(row['deliveryReturned'] is None or row['deliveryUnwound'] is None)
            qt_ordered(row['created'],row['deliveryEntered'])
            qt_ordered(row['deliveryEntered'],row['deliveryReturned']);qt_ordered(row['deliveryEntered'],row['deliveryUnwound'])
            qt_ordered(row['created'],row['argumentValuesDestroyed'])
            if row['deliveryEntered'] is not None and row['argumentValuesDestroyed'] is not None:
                end=row['deliveryReturned'] or row['deliveryUnwound'];need(end is not None)
                qt_ordered(end,row['argumentValuesDestroyed'])
            # Deliberately no ordering between producer invokeReturned and main-thread delivery/destruction.
        if row['receiverId'] is None:
            need(all(row[key] is None for key in ('receiverEntered','receiverReturned','receiverUnwound')))
        else:
            identity(row['receiverId']);need(row['receiverId'] not in receivers);receivers.add(row['receiverId'])
            need(row['eventId'] is not None and row['deliveryEntered'] is not None and row['receiverEntered'] is not None)
            need(row['deliveryEntered']['epochMs']<=row['receiverEntered']['epochMs']
                and (row['receiverReturned'] is None or row['receiverUnwound'] is None))
            ordered(row['receiverEntered'],row['receiverReturned']);ordered(row['receiverEntered'],row['receiverUnwound'])
            for end in ('deliveryReturned','deliveryUnwound'):
                if row[end] is not None:
                    local=row['receiverReturned' if end=='deliveryReturned' else 'receiverUnwound'];need(local is not None)
                    need(local['epochMs']<=row[end]['epochMs'])
    return value


def successor(before,after):
    need(before['instance']==after['instance'] and before['source1Instance']==after['source1Instance']
        and (before['complete'] or not after['complete']) and len(after['entries'])>=len(before['entries']))
    ordered(before['clock'],after['clock'])
    mutable=set(PHASES[1:])|set(QT_PHASES)|{'eventId','receiverId','invokeAccepted'}
    for first,last in zip(before['entries'],after['entries']):
        for key in first:
            if key=='receiverObjectAlive':need(first[key] or not last[key])
            elif key in mutable:
                if first[key] is not None:need(same(first[key],last[key]))
                elif type(last[key]) is dict and key in PHASES:
                    ordered(before['clock'],last[key])
                # Qt samples its original phase clock BEFORE waiting on Bridge's
                # mutex. A later published receipt can predate the prior query.
            else:need(same(first[key],last[key]))


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAssetsImageReaderQueueVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsImageReaderQueueVersion']) is int and value['iosAssetsImageReaderQueueVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-assets-image-reader-queue');identity(value['instance'])
    a,b=value['clockBefore'],value['clockAfter'];stamp(a);stamp(b);ordered(a,b)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500
        and abs((b['epochMs']-a['epochMs'])-(b['monotonicMs']-a['monotonicMs']))<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    history(value['source'],a,b)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId']);ordered(previous['clockAfter'],a)
        successor(previous['source'],value['source'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def parent_links(value,parent):
    """Structural link check only; authoritative reader additionally reads actual parent bytes."""
    original(value);parent_source.original(parent)
    need(value['processId']==parent['processId'] and value['runId']==parent['runId']
        and value['source']['complete'] and parent['source']['complete']
        and value['source']['source1Instance']==parent['source']['instance']
        and value['clockAfter']['epochMs']<=parent['clockBefore']['epochMs'])
    tasks={row['id']:row for row in parent['source']['tasks']}
    dispatches={row['id']:row for row in parent['source']['dispatches']}
    receivers={row['id']:row for row in parent['source']['receivers']}
    for row in value['source']['entries']:
        need(row['taskId'] in tasks and row['dispatchId'] in dispatches)
        task,dispatch=tasks[row['taskId']],dispatches[row['dispatchId']]
        need(dispatch['taskId']==row['taskId'] and task['resourceId']==row['resourceId']
            and dispatch['entered']['epochMs']<=row['bindingEntered']['epochMs'])
        if row['created'] is not None and dispatch['invokeReturned'] is not None:
            need(row['created']['epochMs']<=dispatch['invokeReturned']['epochMs'])
        if row['invokeReturned'] is not None:
            need(dispatch['invokeReturned'] is not None and dispatch['invokeAccepted']==row['invokeAccepted']
                and dispatch['invokeReturned']['epochMs']<=row['invokeReturned']['epochMs'])
        if row['receiverId'] is not None:
            need(row['receiverId'] in receivers);receiver=receivers[row['receiverId']]
            need(receiver['resourceId']==row['resourceId'] and receiver['dispatchId'] is None
                and receiver['attribution']=='unavailable-queued-or-other-producer'
                and row['deliveryEntered']['epochMs']<=receiver['entered']['epochMs']
                and receiver['entered']['epochMs']<=row['receiverEntered']['epochMs'])
            for parent_end in ('returned','unwound'):
                if receiver[parent_end] is not None:
                    need(row['receiverEntered']['epochMs']<=receiver[parent_end]['epochMs'])
            for source_key,parent_key in (('receiverReturned','returned'),('receiverUnwound','unwound')):
                if row[source_key] is not None:
                    need(receiver[parent_key] is not None and receiver[parent_key]['epochMs']<=row[source_key]['epochMs'])
    return deepcopy(value['source'])


class IOSAssetsImageReaderQueue(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAssetsImageReaderQueueAcquisitionVersion'

    def read(self,run,*,source1,native_before_floor=None):
        try:
            started=self.monotonic()
            need(type(source1) is parent_source.IOSAssetsImageReader and source1.pid==self.pid)
            need(source1.guard() is not False)
            value=super().read(run,native_before_floor=native_before_floor)
            parent=source1.read(run)
            need(source1.guard() is not False)
            raw=source1.original();need(type(raw) is str and len(raw.encode())<=parent_source.LIMIT)
            actual=decode(raw,limit=parent_source.LIMIT);parent_source.original(actual)
            acquisition=source1.acquisition
            exact(acquisition,{'hostBeforeMonotonic','hostAfterMonotonic','nativeRequestedEpochMs',
                'nativeAfterEpochMs','originalSha256','iosAssetsImageReaderAcquisitionVersion'})
            need(same(actual,parent) and type(acquisition['iosAssetsImageReaderAcquisitionVersion']) is int
                and acquisition['iosAssetsImageReaderAcquisitionVersion']==1
                and acquisition['originalSha256']==digest(actual)
                and number(acquisition['hostBeforeMonotonic'],0,1e15)
                and number(acquisition['hostAfterMonotonic'],acquisition['hostBeforeMonotonic'],
                    acquisition['hostBeforeMonotonic']+1.5)
                and acquisition['hostAfterMonotonic']-acquisition['hostBeforeMonotonic']<1.5
                and integer(acquisition['nativeRequestedEpochMs'],1,actual['clockBefore']['epochMs'])
                and integer(acquisition['nativeAfterEpochMs'],acquisition['nativeRequestedEpochMs'])
                and source1.guard() is not False and self.guard() is not False)
            fresh(actual['clockAfter']['epochMs'],acquisition['nativeAfterEpochMs'])
            prior=getattr(self,'_parent_history',None)
            if prior is not None:
                parent_source.validate(actual,dict(schemaVersion=1,action=parent_source.ACTION,
                    commandId=actual['requestId'],runId=run),self.pid,previous=prior)
            # Preserve every valid actual parent, including failure, as history;
            # swapping reader objects cannot heal an observed incomplete source.
            self._parent_history=deepcopy(actual)
            facts=parent_links(value,actual)
            ended=self.monotonic();need(number(started,0,1e15) and number(ended,started,started+1.5) and ended-started<1.5)
            self.parent_original=deepcopy(actual);self.parent_acquisition=deepcopy(source1.acquisition)
            self.bound_facts=facts;self.binding_host_span=(started,ended)
            return deepcopy(value)
        except Exception:
            self.parent_original=self.parent_acquisition=self.bound_facts=self.binding_host_span=None
            raise NativeUIError('Original ImageReader queue/source1 parent is unavailable or invalid') from None
