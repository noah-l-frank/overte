"""Strict actual processing/device originals, never whole byte/decoder/GPU end."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import same
from ios.adapters import assets_image_reader as parent_source
from ios.adapters.assets_image_reader_queue import command as queue_command,acquisition
from ios.adapters.assets_model_origin import identity,stamp,ordered
from ios.adapters.places_model import IOSPlacesModel

VERSION=HISTORY_VERSION=1
ACTION='feature-ios-assets-image-reader-processing'
FILE=ACTION+'.json'
LIMIT=262144
PHASES=('bindingEntered','processingEntered','processingReturned','processingUnwound','rawEntered','rawReturned','rawUnwound',
    'contentResetEntered','contentResetReturned','deviceDestroyedObserved')
UNAVAILABLE=('byteCopyCompletionAvailable','basePoolCompletionAvailable','decoderCompletionAvailable',
    'gpuCompletionAvailable','resourceRetirementAvailable')


def command(value):
    queue_command(dict(value,action='feature-ios-assets-image-reader-queue'))
    need(value['action']==ACTION);return value


def phase(value,upper):
    exact(value,{'epochMs','monotonicMs','threadContextId'});identity(value['threadContextId'])
    stamp({key:value[key] for key in ('epochMs','monotonicMs')},upper);return value


def follows(before,after):
    if after is not None:
        need(before is not None and before['epochMs']<=after['epochMs'] and before['monotonicMs']<=after['monotonicMs'])


def history(value,before,after):
    exact(value,{'assetImageReaderProcessingHistoryVersion','instance','source1Instance','complete','clockDomain','clock','tasks','calls'}|set(UNAVAILABLE))
    need(type(value['assetImageReaderProcessingHistoryVersion']) is int and value['assetImageReaderProcessingHistoryVersion']==1
        and type(value['complete']) is bool and value['clockDomain']=='native-assets-image-reader-processing'
        and all(value[key] is False for key in UNAVAILABLE))
    identity(value['instance']);identity(value['source1Instance']);stamp(value['clock'])
    need(before['epochMs']<=value['clock']['epochMs']<=after['epochMs']
        and type(value['tasks']) is list and 1<=len(value['tasks'])<=64 and type(value['calls']) is list and len(value['calls'])<=64)
    tasks={}
    for row in value['tasks']:
        exact(row,{'taskId','resourceId','prepared','derivedMarkerAlive'});need(type(row['derivedMarkerAlive']) is bool);identity(row['taskId']);identity(row['resourceId']);phase(row['prepared'],value['clock'])
        need(row['taskId'] not in tasks);tasks[row['taskId']]=row
    calls=set();devices=set();parents=set()
    for row in value['calls']:
        exact(row,{'id','taskId','resourceId','deviceId','deviceOwnersAlive'}|set(PHASES))
        for key in ('id','taskId','resourceId','deviceId'):identity(row[key])
        need(row['id'] not in calls and row['deviceId'] not in devices and row['taskId'] not in parents
            and row['taskId'] in tasks and tasks[row['taskId']]['resourceId']==row['resourceId'] and type(row['deviceOwnersAlive']) is bool)
        calls.add(row['id']);devices.add(row['deviceId']);parents.add(row['taskId'])
        for key in PHASES:
            if row[key] is not None:phase(row[key],value['clock'])
        need(row['bindingEntered'] is not None);follows(tasks[row['taskId']]['prepared'],row['bindingEntered'])
        for start,ends in (('bindingEntered',('processingEntered','deviceDestroyedObserved')),('processingEntered',('rawEntered','processingReturned','processingUnwound')),
                ('rawEntered',('rawReturned','rawUnwound')),('rawReturned',('contentResetEntered',)),('contentResetEntered',('contentResetReturned',))):
            for end in ends:follows(row[start],row[end])
        need(row['processingReturned'] is None or row['processingUnwound'] is None)
        need(row['rawReturned'] is None or row['rawUnwound'] is None)
        for key in PHASES[:-1]:
            if row[key] is not None:need(row[key]['threadContextId']==row['bindingEntered']['threadContextId'])
        if row['processingReturned'] is not None:
            need(row['rawReturned'] is not None and row['rawUnwound'] is None and row['contentResetReturned'] is not None)
            follows(row['contentResetReturned'],row['processingReturned'])
        if row['rawUnwound'] is not None:need(row['contentResetEntered'] is None)
    return value


def successor(before,after):
    need(before['instance']==after['instance'] and before['source1Instance']==after['source1Instance']
        and (before['complete'] or not after['complete']) and len(after['tasks'])>=len(before['tasks']) and len(after['calls'])>=len(before['calls']))
    ordered(before['clock'],after['clock'])
    for a,b in zip(before['tasks'],after['tasks']):
        need(same({k:v for k,v in a.items() if k!='derivedMarkerAlive'},{k:v for k,v in b.items() if k!='derivedMarkerAlive'})
            and (a['derivedMarkerAlive'] or not b['derivedMarkerAlive']))
    for a,b in zip(before['calls'],after['calls']):
        for key in a:
            if key=='deviceOwnersAlive':need(a[key] or not b[key])
            elif key in PHASES:
                if a[key] is not None:need(same(a[key],b[key]))
                # Worker/destruction callbacks sample BEFORE the observer mutex;
                # late publication does not move their original sample forward.
            else:need(same(a[key],b[key]))


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAssetsImageReaderProcessingVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsImageReaderProcessingVersion']) is int and value['iosAssetsImageReaderProcessingVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-assets-image-reader-processing');identity(value['instance'])
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


def original(value):return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def parent_links(value,parent):
    original(value);parent_source.original(parent);source=value['source']
    need(source['complete'] and parent['source']['complete'] and source['source1Instance']==parent['source']['instance']
        and value['processId']==parent['processId'] and value['runId']==parent['runId'] and value['clockAfter']['epochMs']<=parent['clockBefore']['epochMs'])
    tasks={row['id']:row for row in parent['source']['tasks']}
    need([row['taskId'] for row in source['tasks']]==[row['id'] for row in parent['source']['tasks'][:len(source['tasks'])]])
    for row in source['tasks']:
        actual=tasks[row['taskId']]
        need(actual['resourceId']==row['resourceId'] and actual['constructorEntered']['epochMs']<=row['prepared']['epochMs'])
        if actual['constructorReturned'] is not None:need(row['prepared']['epochMs']<=actual['constructorReturned']['epochMs'])
        if not row['derivedMarkerAlive']:need(not actual['derivedMarkerAlive'])
    for row in source['calls']:
        actual=tasks[row['taskId']]
        need(actual['readEntered'] is not None and actual['readEntered']['epochMs']<=row['bindingEntered']['epochMs'])
        if row['processingReturned'] is not None and actual['readReturned'] is not None:
            need(row['processingReturned']['epochMs']<=actual['readReturned']['epochMs'])
    return deepcopy(source)


class IOSAssetsImageReaderProcessing(IOSPlacesModel):
    _limit=LIMIT;_action=ACTION;_command=staticmethod(command);_validate=staticmethod(validate)
    _acquisition_key='iosAssetsImageReaderProcessingAcquisitionVersion'
    def read(self,run,*,source1,native_before_floor=None):
        try:
            started=self.monotonic();need(type(source1) is parent_source.IOSAssetsImageReader and source1.pid==self.pid and source1.guard() is not False)
            value=super().read(run,native_before_floor=native_before_floor);parent=source1.read(run)
            raw=source1.original();need(type(raw) is str and len(raw.encode())<=parent_source.LIMIT)
            actual=decode(raw,limit=parent_source.LIMIT);parent_source.original(actual)
            need(same(actual,parent));acquisition(actual,source1.acquisition,'iosAssetsImageReaderAcquisitionVersion')
            prior=getattr(self,'_parent_history',None)
            if prior is not None:parent_source.validate(actual,dict(schemaVersion=1,action=parent_source.ACTION,commandId=actual['requestId'],runId=run),self.pid,previous=prior)
            self._parent_history=deepcopy(actual);facts=parent_links(value,actual)
            ended=self.monotonic();need(number(started,0,1e15) and number(ended,started,started+1.5) and ended-started<1.5
                and source1.guard() is not False and self.guard() is not False)
            self.parent_original=deepcopy(actual);self.parent_acquisition=deepcopy(source1.acquisition)
            self.bound_facts=facts;self.binding_host_span=(started,ended);return deepcopy(value)
        except Exception:
            self.parent_original=self.parent_acquisition=self.bound_facts=self.binding_host_span=None
            raise NativeUIError('Actual ImageReader processing/Source1 original is unavailable or invalid') from None
