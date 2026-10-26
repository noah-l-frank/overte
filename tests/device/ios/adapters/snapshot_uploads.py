"""Original upload object/ticket/callback and body-FD facts, never server success."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.create_state import command as state_command
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.snapshot_captures import identity
from ios.adapters.snapshot_exports import FILE_NAME,stamp

VERSION=1
ACTION='feature-ios-snapshot-uploads'
FILE=ACTION+'.json'
LIMIT=262144
KINDS={'uploader','file','multipart','reply','reply-timer'}
METHODS={'upload-success','upload-failure','story-success','story-failure'}
SCOPE={'scopeGeneration','scopeActive','finished','error'}
DETAILS={'begin':set(),'resource-created':{'resource'},'resource-destroyed':{'resource'},'file-opened':{'resource','opened'},
    'ticket-issued':{'request'},'reply-created':{'request','reply','endpoint','scheme','hostSha256','port','authorizationPresent','operation'},
    'reply-finished':{'request','reply','status','networkError','ticketActive'},'callback-enter':{'callback'},'callback-left':{'callback'},
    'response-original':{'reply','byteCount','sha256'},'file-rejected':SCOPE,'cancel-entry':SCOPE,'cancel-invalidated':SCOPE,
    'completion-entry':SCOPE,'completion-issued':SCOPE}


def command(value):
    state_command(dict(value,action='feature-ios-create-state'));need(value['action']==ACTION);return value


def decimal(value,maximum=2**63-1):
    need(type(value) is str and re.fullmatch(r'0|[1-9][0-9]{0,19}',value) and int(value)<=maximum);return int(value)


def sha(value):need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value));return value


def file_fact(value):
    exact(value,{'device','inode','bytes','links','regular','mtimeSeconds','mtimeNanoseconds','ctimeSeconds','ctimeNanoseconds'})
    decimal(value['device'],2**64-1);decimal(value['inode'],2**64-1)
    need(integer(value['bytes'],0,2**53-1) and integer(value['links'],0,2**53-1) and type(value['regular']) is bool)
    for key in ('mtime','ctime'):decimal(value[key+'Seconds']);need(integer(value[key+'Nanoseconds'],0,999999999))
    return value


def fd_fact(value,first):
    exact(value,{'state','file'});need(value['state'] in ('unobserved','present','changed','absent','unknown'))
    if value['state'] in ('present','changed'):
        file_fact(value['file']);need(bool(first) and (same(value['file'],first)==(value['state']=='present')))
    else:need(value['file']=={})
    return value


def rows(values,maximum):
    need(type(values) is list and len(values)<=maximum);result={}
    for value in values:
        need(type(value) is dict and 'instance' in value);identity(value['instance']);need(value['instance'] not in result);result[value['instance']]=value
    return result


def ledger(source,epoch):
    exact(source,{'complete','uploads','resources','requests','callbacks','events','activity','transportFDObservationRequired'})
    need(type(source['complete']) is bool and source['transportFDObservationRequired'] is True)
    activity=source['activity'];exact(activity,{'slots','alive'});need(integer(activity['slots'],0,64) and integer(activity['alive'],0,activity['slots']))
    uploads,resources,requests,callbacks=(rows(source[key],limit) for key,limit in (('uploads',64),('resources',256),('requests',128),('callbacks',256)))
    for row in uploads.values():
        exact(row,{'instance','bornEpochMs','privateName','fileName','fileNameSha256','requests','scopeGeneration','scopeActive'})
        need(integer(row['bornEpochMs'],1,epoch) and type(row['privateName']) is bool and type(row['scopeActive']) is bool)
        sha(row['fileNameSha256']);decimal(row['scopeGeneration']);need(type(row['requests']) is list and len(row['requests'])==len(set(row['requests'])))
        if row['privateName']:
            need(type(row['fileName']) is str and re.fullmatch(FILE_NAME,row['fileName']) and hashlib.sha256(row['fileName'].encode()).hexdigest()==row['fileNameSha256'])
        else:need(row['fileName']=='')
    for row in resources.values():
        exact(row,{'instance','upload','kind','bornEpochMs','destroyedEpochMs','alive','openObserved','opened','descriptor','firstFile','fdBefore','fdAfter'})
        need(row['upload'] in uploads and row['kind'] in KINDS and integer(row['bornEpochMs'],uploads[row['upload']]['bornEpochMs'],epoch)
            and all(type(row[key]) is bool for key in ('alive','openObserved','opened')) and integer(row['descriptor'],-1,2**31-1))
        need((row['destroyedEpochMs'] is None) if row['alive'] else integer(row['destroyedEpochMs'],row['bornEpochMs'],epoch))
        if row['firstFile']:file_fact(row['firstFile']);need(row['kind']=='file' and row['opened'] and row['descriptor']>=0 and row['firstFile']['regular'])
        if row['kind']!='file':need(not row['openObserved'] and not row['opened'] and row['descriptor']==-1 and row['firstFile']=={})
        if row['opened']:need(row['openObserved'] and (not source['complete'] or row['descriptor']>=0 and bool(row['firstFile'])))
        else:need(row['descriptor']==-1 and row['firstFile']=={})
        for key in ('fdBefore','fdAfter'):fd_fact(row[key],row['firstFile'])
    for row in requests.values():
        exact(row,{'instance','upload','stage','issuedEpochMs','generation','active','diagnosticsComplete','reply'})
        need(row['upload'] in uploads and row['stage'] in ('upload','story') and integer(row['issuedEpochMs'],uploads[row['upload']]['bornEpochMs'],epoch)
            and decimal(row['generation'])>=1 and type(row['active']) is bool and type(row['diagnosticsComplete']) is bool)
        if row['reply']:need(row['reply'] in resources and resources[row['reply']]['upload']==row['upload'] and resources[row['reply']]['kind']=='reply')
        if source['complete']:need(row['diagnosticsComplete'])
    for owner,row in uploads.items():
        need(set(row['requests'])=={key for key,value in requests.items() if value['upload']==owner})
        generations=[decimal(requests[key]['generation']) for key in row['requests']];need(all(a<b for a,b in zip(generations,generations[1:])))
        need(not generations or decimal(row['scopeGeneration'])==0 and not row['scopeActive'] or decimal(row['scopeGeneration'])>=max(generations))
    for row in callbacks.values():
        exact(row,{'instance','upload','method','reply','enteredEpochMs','leftEpochMs','finishedAtEntry','scopeGeneration','scopeActiveAtEntry',
            'request','requestGeneration','requestActiveAtEntry','stackAlive'})
        need(row['upload'] in uploads and row['method'] in METHODS and row['request'] in requests and row['reply'] in resources)
        sent=requests[row['request']];need(sent['upload']==row['upload'] and sent['reply']==row['reply'] and row['method'].startswith(sent['stage']+'-')
            and row['requestGeneration']==sent['generation'] and integer(row['enteredEpochMs'],sent['issuedEpochMs'],epoch))
        decimal(row['scopeGeneration']);need(all(type(row[key]) is bool for key in ('finishedAtEntry','scopeActiveAtEntry','requestActiveAtEntry','stackAlive')))
        if row['leftEpochMs'] is not None:need(integer(row['leftEpochMs'],row['enteredEpochMs'],epoch))
    need(type(source['events']) is list and len(source['events'])<=1024);last=0;counts={}
    for index,event in enumerate(source['events'],1):
        exact(event,{'sequence','upload','kind','capturedEpochMs','detail'});owner,kind=event['upload'],event['kind']
        need(type(event['sequence']) is int and event['sequence']==index and owner in uploads and kind in DETAILS
            and integer(event['capturedEpochMs'],max(last,uploads[owner]['bornEpochMs']),epoch));last=event['capturedEpochMs'];detail=event['detail'];exact(detail,DETAILS[kind])
        if 'resource' in detail:need(detail['resource'] in resources and resources[detail['resource']]['upload']==owner)
        if 'request' in detail:need(detail['request'] in requests and requests[detail['request']]['upload']==owner)
        if 'reply' in detail:need(detail['reply'] in resources and resources[detail['reply']]['upload']==owner and resources[detail['reply']]['kind']=='reply')
        if 'callback' in detail:need(detail['callback'] in callbacks and callbacks[detail['callback']]['upload']==owner)
        if kind=='resource-destroyed':need(not resources[detail['resource']]['alive'] and resources[detail['resource']]['destroyedEpochMs']<=last)
        if kind=='file-opened':need(type(detail['opened']) is bool and resources[detail['resource']]['kind']=='file' and resources[detail['resource']]['openObserved'] and detail['opened']==resources[detail['resource']]['opened'])
        if kind=='reply-created':
            need(requests[detail['request']]['reply']==detail['reply'] and detail['endpoint'] in ('','/api/v1/snapshots','/api/v1/user_stories')
                and type(detail['scheme']) is str and len(detail['scheme'])<=32 and integer(detail['port'],0,65535)
                and type(detail['authorizationPresent']) is bool and integer(detail['operation'],0,10));sha(detail['hostSha256'])
        if kind=='reply-finished':
            need(requests[detail['request']]['reply']==detail['reply'] and (detail['status'] is None or integer(detail['status'],100,599))
                and integer(detail['networkError'],0,499) and type(detail['ticketActive']) is bool)
        if kind=='response-original':need(integer(detail['byteCount'],0,65536));sha(detail['sha256'])
        if kind in ('cancel-entry','cancel-invalidated','completion-entry','completion-issued','file-rejected'):
            decimal(detail['scopeGeneration']);need(all(type(detail[key]) is bool for key in ('scopeActive','finished','error')))
        key=(owner,kind,next((detail[name] for name in ('resource','request','callback','reply') if name in detail),''));counts[key]=counts.get(key,0)+1
        if kind in ('begin','resource-created','resource-destroyed','file-opened','ticket-issued','reply-created','reply-finished','callback-enter','callback-left','response-original','cancel-invalidated','completion-issued','file-rejected'):need(counts[key]==1)
    for key,row in uploads.items():need(counts.get((key,'begin',''))==1)
    for key,row in resources.items():
        need(counts.get((row['upload'],'resource-created',key))==1)
        if not row['alive']:need(counts.get((row['upload'],'resource-destroyed',key))==1)
    for key,row in requests.items():
        need(counts.get((row['upload'],'ticket-issued',key))==1)
        if row['reply']:need(counts.get((row['upload'],'reply-created',key))==1)
    for key,row in callbacks.items():
        need(counts.get((row['upload'],'callback-enter',key))==1)
        if row['leftEpochMs'] is not None:need(counts.get((row['upload'],'callback-left',key))==1)
    return uploads,resources,requests,callbacks


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosSnapshotUploadsVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosSnapshotUploadsVersion']) is int and value['iosSnapshotUploadsVersion']==1 and value['requestId']==query['commandId']
        and value['runId']==query['runId'] and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and integer(value['sequence'],1) and value['clockDomain']=='native-main-snapshot-uploads');identity(value['instance'])
    a,b=stamp(value['clockBefore']),stamp(value['clockAfter']);current=ledger(value['source'],b['epochMs'])
    need(all(a[key]<=b[key]<a[key]+1500 for key in a) and abs(b['epochMs']-a['epochMs']-(b['monotonicMs']-a['monotonicMs']))<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid);old=previous['source'];before=ledger(old,previous['clockAfter']['epochMs'])
        need(value['instance']==previous['instance'] and value['requestId']!=previous['requestId'] and value['sequence']>previous['sequence']
            and all(a[key]>=previous['clockAfter'][key] for key in a) and (old['complete'] or not value['source']['complete'])
            and len(value['source']['events'])>=len(old['events']) and same(value['source']['events'][:len(old['events'])],old['events']))
        mutable=({'requests','scopeGeneration','scopeActive'},{'alive','destroyedEpochMs','openObserved','opened','descriptor','firstFile','fdBefore','fdAfter'},
            {'active','diagnosticsComplete','reply'},{'leftEpochMs','stackAlive'})
        for earlier,later,changing in zip(before,current,mutable):
            for key,row in earlier.items():
                need(key in later and all(same(row[field],later[key][field]) for field in row if field not in changing))
                for flag in ('alive','active','diagnosticsComplete','stackAlive'):
                    if flag in row:need(row[flag] or not later[key][flag])
                for field in ('destroyedEpochMs','leftEpochMs'):
                    if field in row and row[field] is not None:need(row[field]==later[key][field])
                if 'openObserved' in row and row['openObserved']:need(all(same(row[field],later[key][field]) for field in ('openObserved','opened','descriptor','firstFile')))
                if 'scopeActive' in row:
                    older,newer=decimal(row['scopeGeneration']),decimal(later[key]['scopeGeneration'])
                    need((newer>=older or newer==0 and not later[key]['scopeActive']) and (older!=0 or newer==0)
                        and (row['scopeActive'] or not later[key]['scopeActive'] or newer>older))
    return value


def original(value):return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def decision(value,identifier):
    original(value);need(value['source']['complete']);uploads,_resources,requests,callbacks=ledger(value['source'],value['clockAfter']['epochMs'])
    need(identifier in uploads and uploads[identifier]['privateName'] and uploads[identifier]['fileName'].startswith('parity-'+value['runId'][:16]+'-'))
    terminal=[row for row in value['source']['events'] if row['upload']==identifier and row['kind'] in ('cancel-invalidated','completion-issued','file-rejected')]
    need(len(terminal)==1);row=terminal[0];detail=row['detail']
    if row['kind']=='cancel-invalidated':need(detail['finished'] and not detail['scopeActive']);status='cancelled'
    elif row['kind']=='file-rejected':status='error'
    else:need(detail['finished']);status='error' if detail['error'] else 'success'
    if status=='success':
        sent=[item for item in requests.values() if item['upload']==identifier];need(len(sent)==2 and {item['stage'] for item in sent}=={'upload','story'})
        for request in sent:
            related=[item for item in value['source']['events'] if item['upload']==identifier and item['detail'].get('request')==request['instance']]
            created=[item['detail'] for item in related if item['kind']=='reply-created'];finished=[item['detail'] for item in related if item['kind']=='reply-finished']
            need(len(created)==len(finished)==1 and created[0]['endpoint']==('/api/v1/snapshots' if request['stage']=='upload' else '/api/v1/user_stories')
                and created[0]['authorizationPresent'] and created[0]['operation']==4 and integer(finished[0]['status'],200,299)
                and finished[0]['networkError']==0 and finished[0]['ticketActive'])
            called=[item for item in callbacks.values() if item['request']==request['instance'] and item['method']==request['stage']+'-success']
            bodies=[item for item in value['source']['events'] if item['upload']==identifier and item['kind']=='response-original' and item['detail']['reply']==request['reply']]
            need(len(called)==len(bodies)==1 and called[0]['requestActiveAtEntry'] and called[0]['scopeActiveAtEntry'] and not called[0]['finishedAtEntry']
                and called[0]['scopeGeneration']==request['generation'] and bodies[0]['detail']['byteCount']>0)
    return dict(iosSnapshotUploadDecisionVersion=1,upload=identifier,status=status,nativeOriginal=deepcopy(row),nativeSignalDeliveryRequired=True,
        authenticatedBackendOriginalRequired=True,backendBodyMayAlreadyExist=True,resourceRetirementRequired=True,wholeFeatureRequired=True)


def local_objects_gone(value,identifier):
    original(value);need(value['source']['complete']);uploads,resources,requests,callbacks=ledger(value['source'],value['clockAfter']['epochMs'])
    need(identifier in uploads and uploads[identifier]['privateName'] and uploads[identifier]['fileName'].startswith('parity-'+value['runId'][:16]+'-')
        and not uploads[identifier]['scopeActive']);owned=[row for row in resources.values() if row['upload']==identifier]
    need(owned and sum(row['kind']=='uploader' for row in owned)==1 and all(not row['alive'] for row in owned)
        and all(not row['active'] for row in requests.values() if row['upload']==identifier)
        and all(row['leftEpochMs'] is not None and not row['stackAlive'] for row in callbacks.values() if row['upload']==identifier))
    files=[row for row in owned if row['kind']=='file'];need(len(files)==1 and all(row['opened'] and row['firstFile'] and row['fdBefore']['state']==row['fdAfter']['state']=='absent' for row in files))
    return dict(iosSnapshotUploadLocalObjectsVersion=1,upload=identifier,observedClock=deepcopy(value['clockAfter']),bodyFDAbsent=True,
        QObjectDestructionObserved=True,callbackStackDepartureObserved=True,transportProcessProofRequired=True,wholeFeatureRequired=True)


class IOSSnapshotUploads(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotUploadsAcquisitionVersion'
    _limit=LIMIT
