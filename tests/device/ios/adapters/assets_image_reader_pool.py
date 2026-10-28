"""Selected generation-carrying Qt pool histories; never global pool drainage.

Incomplete concurrent POD cuts remain valid pending original observations. A
complete selected-edge proof requires later complete immutable histories.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.script_feature.history import same
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_image_reader as reader,assets_image_reader_storage as storage_source
from ios.adapters.assets_image_reader_queue import command as queue_command,acquisition
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.assets_model_origin import identity,stamp,ordered

VERSION=1
ACTION='feature-ios-assets-image-reader-pool'
FILE=ACTION+'.json'
LIMIT=262144
UNAVAILABLE=('byteCopyCompletionAvailable','globalPoolCompletionAvailable','decoderCompletionAvailable',
    'gpuCompletionAvailable','resourceRetirementAvailable')
KINDS={1:'pool-created',2:'pool-destructor-body-tail-observed',3:'registered',4:'registration-retired',
    5:'start-entered',6:'start-returned',7:'start-unwound',8:'try-start-entered',9:'try-start-returned',10:'try-start-unwound',
    11:'reserved-entered',12:'reserved-returned',13:'reserved-unwound',14:'enqueued',15:'slot-removed',16:'worker-assigned',
    17:'run-entered',18:'run-returned',19:'run-unwound',20:'auto-delete-entered',21:'auto-delete-returned',
    22:'iteration-returned',23:'iteration-unwound',24:'cancel-delete-entered',25:'cancel-delete-returned',
    26:'cancel-scope-returned',27:'cancel-scope-unwound',28:'try-take-entered',29:'try-take-returned',30:'try-take-unwound',31:'take-matched'}
ROOTS={5:(6,7),8:(9,10),11:(12,13)}


def command(value):
    queue_command(dict(value,action='feature-ios-assets-image-reader-queue'))
    need(value['action']==ACTION);return value


def u64(value):
    need(type(value) is str and re.fullmatch('[1-9][0-9]{0,19}',value) is not None and int(value)<=2**64-1)
    return int(value)


def numbered(rows,key,limit,reserved,complete):
    need(type(rows) is list and len(rows)<=limit and integer(reserved,0,limit))
    ids=[]
    for row in rows:
        need(type(row) is dict and integer(row.get(key),1,reserved));ids.append(row[key])
    need(ids==sorted(set(ids)))
    if complete:need(ids==list(range(1,reserved+1)))
    return {row[key]:row for row in rows}


def qt_history(value):
    exact(value,{'qtRunnablePoolProtocolVersion','instance','clockDomain','epochMs','steadyNs','healthy','cutComplete',
        'mutationSerial','inFlight','poolCount','reservedRegistrations','reservedAdmissions','reservedEvents','registrations','admissions','events'})
    need(type(value['qtRunnablePoolProtocolVersion']) is int and value['qtRunnablePoolProtocolVersion']==1
        and value['clockDomain']=='qtcore-runnable-pool-steady-nanoseconds' and type(value['healthy']) is bool
        and type(value['cutComplete']) is bool and integer(value['epochMs'],1) and integer(value['poolCount'],0,64)
        and integer(value['mutationSerial'],0) and integer(value['inFlight'],0,4096))
    identity(value['instance']);snapshot_steady=u64(value['steadyNs']);complete=value['cutComplete']
    if complete:need(value['inFlight']==0)
    regs=numbered(value['registrations'],'id',64,value['reservedRegistrations'],complete)
    admissions=numbered(value['admissions'],'id',128,value['reservedAdmissions'],complete)
    events=numbered(value['events'],'sequence',2048,value['reservedEvents'],complete)
    allocations=set()
    for row in regs.values():
        exact(row,{'id','allocationId','live'});identity(row['allocationId']);need(type(row['live']) is bool and row['allocationId'] not in allocations);allocations.add(row['allocationId'])
    for row in admissions.values():
        exact(row,{'id','poolId','registrationId','operation'})
        need(integer(row['poolId'],1,value['poolCount']) and integer(row['registrationId'],1,value['reservedRegistrations'])
            and type(row['operation']) is int and row['operation'] in ROOTS)
    for event in events.values():
        exact(event,{'sequence','kind','poolId','registrationId','admissionId','slotId','threadSlotId','operationId','epochMs','steadyNs','flags'})
        k=event['kind'];need(type(k) is int and k in KINDS and integer(event['poolId'],0,value['poolCount'])
            and integer(event['registrationId'],0,value['reservedRegistrations']) and integer(event['admissionId'],0,value['reservedAdmissions'])
            and integer(event['slotId'],0,2**53-1) and integer(event['threadSlotId'],1,128) and integer(event['operationId'],0,2**53-1)
            and integer(event['epochMs'],1,value['epochMs']) and u64(event['steadyNs'])<=snapshot_steady and integer(event['flags'],0,5))
        p,r,a,s,o,f=(event[key] for key in ('poolId','registrationId','admissionId','slotId','operationId','flags'))
        if k in (1,2):need(p>0 and (r,a,s,o,f)==(0,0,0,0,0))
        elif k in (3,4):need(r>0 and (p,a,s,o,f)==(0,0,0,0,0))
        elif k in (28,29,30,31):
            need(p>0 and r>0 and o>0)
            if k==28:need((a,s,f)==(0,0,0))
            elif k==31:need(a>0 and s>0 and f==0)
            elif k==29:need(s==0 and f in (0,1) and bool(a)==bool(f))
            else:need(s==0 and f in (0,1))
        else:
            need(p>0 and r>0 and a>0 and o==0)
            if k==14:need(s>0 and f==0)
            elif k==15:need(s>0 and 1<=f<=4)
            elif k==17:need(s==0 and f in (2,3,4,5))
            elif k in (6,9,12):need(s==0 and f in (0,1))
            else:need(s==0 and f==0)
        if a in admissions:need(admissions[a]['registrationId']==r and admissions[a]['poolId']==p)
    if complete:
        for pid in range(1,value['poolCount']+1):
            created=[row for row in events.values() if row['kind']==1 and row['poolId']==pid]
            destroyed=[row for row in events.values() if row['kind']==2 and row['poolId']==pid]
            need(len(created)==1 and len(destroyed)<=1)
            if destroyed:need(created[0]['epochMs']<=destroyed[0]['epochMs'] and u64(created[0]['steadyNs'])<=u64(destroyed[0]['steadyNs']))
        for rid,reg in regs.items():
            registered=[row for row in events.values() if row['kind']==3 and row['registrationId']==rid]
            retired=[row for row in events.values() if row['kind']==4 and row['registrationId']==rid]
            need(len(registered)==1 and len(retired)==(0 if reg['live'] else 1))
        need(len({row['registrationId'] for row in admissions.values()})==len(admissions))
        for aid,row in admissions.items():
            roots=[event for event in events.values() if event['admissionId']==aid and event['kind'] in ROOTS]
            need(len(roots)==1 and roots[0]['kind']==row['operation'])
    return value


def history(value,before,after):
    exact(value,{'assetImageReaderPoolHistoryVersion','instance','source1Instance','complete','clockDomain','clock','bindings','qt'}|set(UNAVAILABLE))
    need(type(value['assetImageReaderPoolHistoryVersion']) is int and value['assetImageReaderPoolHistoryVersion']==1
        and type(value['complete']) is bool and value['clockDomain']=='native-assets-image-reader-pool'
        and all(value[key] is False for key in UNAVAILABLE))
    identity(value['instance']);identity(value['source1Instance']);stamp(value['clock'])
    need(before['epochMs']<=value['clock']['epochMs']<=after['epochMs'])
    q=qt_history(value['qt']);need(q['instance']==value['instance'] and before['epochMs']<=q['epochMs']<=value['clock']['epochMs'])
    links=numbered(value['bindings'],'registrationId',64,q['reservedRegistrations'],q['cutComplete'])
    allocations=set();tasks=set()
    regs={row['id']:row for row in q['registrations']}
    for key,row in links.items():
        exact(row,{'registrationId','allocationId','taskId','resourceId','attached'})
        for field in ('allocationId','taskId','resourceId'):identity(row[field])
        need(row['allocationId'] not in allocations and row['taskId'] not in tasks);allocations.add(row['allocationId']);tasks.add(row['taskId'])
        stamp(row['attached']);ordered(row['attached'],value['clock'])
        if key in regs:need(regs[key]['allocationId']==row['allocationId'])
    return value


def successor(before,after):
    need(before['instance']==after['instance'] and before['source1Instance']==after['source1Instance']
        and (before['complete'] or not after['complete']))
    ordered(before['clock'],after['clock']);a,b=before['qt'],after['qt']
    need(a['instance']==b['instance'] and a['epochMs']<=b['epochMs'] and u64(a['steadyNs'])<=u64(b['steadyNs'])
        and a['mutationSerial']<=b['mutationSerial'] and (a['healthy'] or not b['healthy']))
    for key in ('poolCount','reservedRegistrations','reservedAdmissions','reservedEvents'):need(a[key]<=b[key])
    for key,index in (('bindings','registrationId'),):
        new={row[index]:row for row in after[key]}
        for row in before[key]:need(row[index] in new and same(row,new[row[index]]))
    for key,index in (('registrations','id'),('admissions','id'),('events','sequence')):
        new={row[index]:row for row in b[key]}
        for row in a[key]:
            need(row[index] in new);actual=new[row[index]]
            if key=='registrations':need(row['allocationId']==actual['allocationId'] and (row['live'] or not actual['live']))
            else:need(same(row,actual))


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAssetsImageReaderPoolVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsImageReaderPoolVersion']) is int and value['iosAssetsImageReaderPoolVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-assets-image-reader-pool');identity(value['instance'])
    a,b=value['clockBefore'],value['clockAfter'];stamp(a);stamp(b);ordered(a,b)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500
        and abs((b['epochMs']-a['epochMs'])-(b['monotonicMs']-a['monotonicMs']))<=250)
    if epoch is not None:
        from adapters.native_feature_observation import fresh
        fresh(b['epochMs'],epoch)
    history(value['source'],a,b)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'])
        ordered(previous['clockAfter'],a);successor(previous['source'],value['source'])
    return value


def original(value):return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def parent_links(value,storage,parent):
    original(value);actual=storage_source.parent_links(storage,parent);source=value['source']
    need(source['complete'] and source['source1Instance']==actual['source1Instance'] and value['processId']==storage['processId']
        and value['runId']==storage['runId'] and value['clockAfter']['epochMs']<=storage['clockBefore']['epochMs'])
    allocations={row['id']:row for row in actual['allocations'] if row['taskId']}
    originals={row['id']:row for row in parent['source']['tasks']}
    for binding in source['bindings']:
        need(binding['allocationId'] in allocations);row=allocations[binding['allocationId']]
        need(binding['taskId']==row['taskId'] and binding['resourceId']==row['resourceId']
            and row['sourceAttached']['epochMs']<=binding['attached']['epochMs'])
        task=originals[row['taskId']]
        if task['constructorReturned'] is not None:need(binding['attached']['epochMs']<=task['constructorReturned']['epochMs'])
    if source['qt']['cutComplete']:
        for event in source['qt']['events']:
            if event['kind']!=4:continue
            bound=next(row for row in source['bindings'] if row['registrationId']==event['registrationId'])
            row=allocations[bound['allocationId']];need(row['deleteEntered'] is not None)
            need(row['deleteEntered']['epochMs']<=event['epochMs'])
            if row['deleteReturned'] is not None:need(event['epochMs']<=row['deleteReturned']['epochMs'])
    return deepcopy(source)


class IOSAssetsImageReaderPool(IOSPlacesModel):
    _limit=LIMIT;_action=ACTION;_command=staticmethod(command);_validate=staticmethod(validate)
    _acquisition_key='iosAssetsImageReaderPoolAcquisitionVersion'
    def read(self,run,*,storage,source1,native_before_floor=None):
        try:
            started=self.monotonic();need(type(storage) is storage_source.IOSAssetsImageReaderStorage and type(source1) is reader.IOSAssetsImageReader
                and storage.pid==source1.pid==self.pid and storage.guard() is not False and source1.guard() is not False)
            value=super().read(run,native_before_floor=native_before_floor);packet=storage.read(run,source1=source1)
            raw=storage.original();need(type(raw) is str and len(raw.encode())<=storage_source.LIMIT)
            actual=decode(raw,limit=storage_source.LIMIT);need(same(actual,packet))
            acquisition(actual,storage.acquisition,'iosAssetsImageReaderStorageAcquisitionVersion')
            prior=getattr(self,'_storage_history',None)
            if prior is not None:storage_source.validate(actual,dict(schemaVersion=1,action=storage_source.ACTION,commandId=actual['requestId'],runId=run),self.pid,previous=prior)
            self._storage_history=deepcopy(actual);facts=parent_links(value,actual,storage.parent_original)
            ended=self.monotonic();need(number(started,0,1e15) and number(ended,started,started+1.5) and ended-started<1.5
                and storage.guard() is not False and source1.guard() is not False and self.guard() is not False)
            self.storage_original=deepcopy(actual);self.storage_acquisition=deepcopy(storage.acquisition)
            self.parent_original=deepcopy(storage.parent_original);self.parent_acquisition=deepcopy(storage.parent_acquisition)
            self.bound_facts=facts;self.binding_host_span=(started,ended);return deepcopy(value)
        except Exception:
            self.storage_original=self.storage_acquisition=self.parent_original=self.parent_acquisition=self.bound_facts=self.binding_host_span=None
            raise NativeUIError('Actual generation-carrying pool/Storage/Source1 original is unavailable or invalid') from None
