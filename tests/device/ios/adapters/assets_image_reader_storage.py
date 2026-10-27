"""Actual allocation generations and deallocation returns, never pool drainage."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.script_feature.history import same
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_image_reader as parent_source
from ios.adapters.assets_image_reader_queue import command as queue_command,acquisition
from ios.adapters.assets_image_reader_processing import phase,follows
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.assets_model_origin import identity,stamp,ordered

VERSION=HISTORY_VERSION=1
ACTION='feature-ios-assets-image-reader-storage'
FILE=ACTION+'.json'
LIMIT=262144
PHASES=('allocationEntered','allocationReturned','allocationThrew','sourceAttached','destructorBodyEntered','deleteEntered','deleteReturned')
UNAVAILABLE=('byteCopyCompletionAvailable','poolCompletionAvailable','decoderCompletionAvailable',
    'gpuCompletionAvailable','resourceRetirementAvailable')


def command(value):
    queue_command(dict(value,action='feature-ios-assets-image-reader-queue'))
    need(value['action']==ACTION);return value


def history(value,before,after):
    exact(value,{'assetImageReaderStorageHistoryVersion','instance','source1Instance','complete','clockDomain','clock','allocations'}|set(UNAVAILABLE))
    need(type(value['assetImageReaderStorageHistoryVersion']) is int and value['assetImageReaderStorageHistoryVersion']==1
        and type(value['complete']) is bool and value['clockDomain']=='native-assets-image-reader-storage'
        and all(value[key] is False for key in UNAVAILABLE))
    identity(value['instance']);identity(value['source1Instance']);stamp(value['clock'])
    need(before['epochMs']<=value['clock']['epochMs']<=after['epochMs']
        and type(value['allocations']) is list and 1<=len(value['allocations'])<=64)
    seen=set();tasks=set()
    for row in value['allocations']:
        exact(row,{'id','storageBytes','taskId','resourceId','sizedDelete','derivedMarkerAlive'}|set(PHASES));identity(row['id'])
        need(row['id'] not in seen and integer(row['storageBytes'],1,1048576) and type(row['derivedMarkerAlive']) is bool)
        seen.add(row['id'])
        need(type(row['taskId']) is str and type(row['resourceId']) is str and bool(row['taskId'])==bool(row['resourceId']))
        if row['taskId']:
            identity(row['taskId']);identity(row['resourceId']);need(row['taskId'] not in tasks);tasks.add(row['taskId'])
        else:need(row['derivedMarkerAlive'] is False)
        for key in PHASES:
            if row[key] is not None:phase(row[key],value['clock'])
        need(row['allocationEntered'] is not None and (row['allocationReturned'] is None or row['allocationThrew'] is None)
            and (row['sourceAttached'] is not None)==bool(row['taskId']))
        follows(row['allocationEntered'],row['allocationReturned']);follows(row['allocationEntered'],row['allocationThrew'])
        for key in ('allocationReturned','allocationThrew'):
            if row[key] is not None:need(row[key]['threadContextId']==row['allocationEntered']['threadContextId'])
        for key in ('sourceAttached','destructorBodyEntered','deleteEntered'):follows(row['allocationReturned'],row[key])
        if row['sourceAttached'] is not None:need(row['sourceAttached']['threadContextId']==row['allocationEntered']['threadContextId'])
        if row['destructorBodyEntered'] is not None:follows(row['sourceAttached'],row['destructorBodyEntered'])
        follows(row['deleteEntered'],row['deleteReturned'])
        if row['deleteEntered'] is not None:
            need(type(row['sizedDelete']) is bool)
            if row['destructorBodyEntered'] is not None:
                follows(row['destructorBodyEntered'],row['deleteEntered'])
                need(row['destructorBodyEntered']['threadContextId']==row['deleteEntered']['threadContextId'])
        else:need(row['sizedDelete'] is None)
        if row['deleteReturned'] is not None:need(row['deleteReturned']['threadContextId']==row['deleteEntered']['threadContextId'])
    return value


def successor(before,after):
    need(before['instance']==after['instance'] and before['source1Instance']==after['source1Instance']
        and (before['complete'] or not after['complete']) and len(after['allocations'])>=len(before['allocations']))
    ordered(before['clock'],after['clock'])
    for a,b in zip(before['allocations'],after['allocations']):
        for key in a:
            if key=='derivedMarkerAlive':
                if a['taskId']:need(a[key] or not b[key])
            elif key in PHASES or key=='sizedDelete':
                if a[key] is not None:need(same(a[key],b[key]))
            elif key in ('taskId','resourceId'):
                if a[key]:need(a[key]==b[key])
            else:need(same(a[key],b[key]))


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAssetsImageReaderStorageVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsImageReaderStorageVersion']) is int and value['iosAssetsImageReaderStorageVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-assets-image-reader-storage');identity(value['instance'])
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
    # Allocation attempt order can differ from constructor-task order when a
    # global new-handler constructs another ImageReader recursively. Real IDs,
    # not address/order/size coincidence, bind these two independent histories.
    for row in source['allocations']:
        if not row['taskId']:continue
        need(row['taskId'] in tasks);actual=tasks[row['taskId']]
        need(actual['resourceId']==row['resourceId'] and row['allocationReturned']['epochMs']<=actual['constructorEntered']['epochMs']
            and actual['constructorEntered']['epochMs']<=row['sourceAttached']['epochMs'])
        if actual['constructorReturned'] is not None:need(row['sourceAttached']['epochMs']<=actual['constructorReturned']['epochMs'])
        if not row['derivedMarkerAlive']:need(not actual['derivedMarkerAlive'])
        if row['destructorBodyEntered'] is not None:
            need(actual['constructorReturned'] is not None and actual['constructorReturned']['epochMs']<=row['destructorBodyEntered']['epochMs'])
    return deepcopy(source)


class IOSAssetsImageReaderStorage(IOSPlacesModel):
    _limit=LIMIT;_action=ACTION;_command=staticmethod(command);_validate=staticmethod(validate)
    _acquisition_key='iosAssetsImageReaderStorageAcquisitionVersion'
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
            raise NativeUIError('Actual ImageReader storage/Source1 original is unavailable or invalid') from None
