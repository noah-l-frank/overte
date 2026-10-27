"""Original social XHR events, actual response consumption and lifetime drainage."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
from urllib.parse import urlsplit,unquote

from adapters.native_feature_observation import decode,exact,fresh,integer,need
from ios.adapters.places_model import IOSPlacesModel

VERSION=2
READS=(1,2)
ACTION='feature-ios-avatar-social-http'
FILE='feature-ios-avatar-social-http.json'
LIMIT=262144
HEX=re.compile('[a-f0-9]{32}\\Z')
SHA=re.compile('[a-f0-9]{64}\\Z')


def identifier(value):need(type(value) is str and HEX.fullmatch(value));return value


def command(value,*,_snapshot=False):
    need(type(_snapshot) is bool)
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==('feature-ios-snapshot-preflight-http' if _snapshot else ACTION)
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    identifier(value['runId']);return value


def installed(value,suffix):
    need(type(value) is str and len(value)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in value))
    url=urlsplit(value);path=unquote(url.path,encoding='utf-8',errors='strict')
    need(url.scheme in ('qrc','file') and not url.netloc and not url.query and not url.fragment and path.endswith(suffix)
         and not any(part in ('.','..') for part in path.split('/')))
    return value


def endpoint(value,*,_snapshot=False):
    need(type(_snapshot) is bool)
    need(type(value) is str and len(value)<=4096 and all(ord(c)>32 and ord(c)!=127 for c in value))
    url=urlsplit(value);url.port
    need(url.scheme=='https' and url.hostname and url.username is None and url.password is None and not url.fragment)
    if _snapshot:
        from feature_journeys.snapshot_concurrency import query
        need(url.path=='/api/v1/user_stories' and '#' not in value);actual=query(url.query)
        need(actual['domain_id']!='00000000-0000-0000-0000-000000000000');return value
    paths={'/api/v1/user/connection_request','/api/v1/users','/api/v1/users/connections'}
    need(url.path in paths or re.fullmatch('/api/v1/user/connections/e2e-[a-f0-9]{32}',url.path) and not url.query)
    return value


def signature(value):
    need(type(value) is str and len(value)==24)
    raw=base64.b64decode(value,validate=True);need(len(raw)==16 and base64.b64encode(raw).decode()==value);return value


def source(value,version=1,epoch=None,caller=None,*,_snapshot=False):
    need(type(_snapshot) is bool)
    need(type(version) is int and version in READS)
    exact(value,{'engine','submitted','requestUrl','method','protocolSignature'}|
        ({'callerChain'} if version==1 else {'callerStackId'})|({'codeSources'} if _snapshot else set()))
    suffixes=('/system/snapshot.js',) if _snapshot else ('/system/pal.js','/system/libraries/peopleConnection.js','/system/request-service.js')
    if version==1:
        chain=value['callerChain'];need(type(chain) is list and 1<=len(chain)<=32)
        installed(chain[0],'/modules/request.js')
    else:
        from ios.adapters import avatar_call_stack
        identifier(value['callerStackId']);need(integer(epoch,1) and type(caller) is dict and caller['id']==value['callerStackId'])
        avatar_call_stack.validate(caller['callerStack'],caller['callerModules'],epoch,_snapshot=_snapshot)
        chain=[module['url'] for module in caller['callerModules']]
        need(caller['callerModules'] and caller['callerModules'][0]['frame']==0);installed(chain[0],'/modules/request.js')
    if _snapshot:
        need(version==2);code=value['codeSources'];exact(code,{'snapshotHttpSourcesVersion','complete','evaluations'})
        need(type(code['snapshotHttpSourcesVersion']) is int and code['snapshotHttpSourcesVersion']==1 and code['complete'] is True and type(code['evaluations']) is list and len(code['evaluations'])<=64)
        avatar_call_stack.evaluated(caller['callerStack'],caller['callerModules'],epoch,code['evaluations'],required={'/system/snapshot.js','/modules/request.js'},top='/modules/request.js',_snapshot=True)
        for index,module in enumerate(caller['callerModules']):
            need(module['frame']==index)
            if module['url'].endswith('/system/snapshot.js'):break
            installed(module['url'],'/modules/request.js')
        else:need(False)
    need(any(type(caller) is str and urlsplit(caller).path.endswith(suffixes)
             for caller in chain))
    for caller in chain:
        need(type(caller) is str and len(caller)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in caller))
    for caller in chain:
        for suffix in suffixes:
            if urlsplit(caller).path.endswith(suffix):installed(caller,suffix)
    endpoint(value['requestUrl'],_snapshot=_snapshot);signature(value['protocolSignature']);need(value['method'] in (('GET',) if _snapshot else ('GET','POST','DELETE')))
    engine=value['engine'];exact(engine,{'instance','assigned','url','loadGeneration','assignedEpochMs'})
    identifier(engine['instance']);need(engine['assigned'] is True and integer(engine['loadGeneration'],1)
         and integer(engine['assignedEpochMs'],1));installed(engine['url'],'/system/snapshot.js' if _snapshot else '/defaultScripts.js')
    submitted=value['submitted'];exact(submitted,{'submitted','encoding','codeUnits','sha256','submittedEpochMs'})
    need(submitted['submitted'] is True and submitted['encoding']=='utf-16le-code-units'
         and integer(submitted['codeUnits'],1,4194304) and type(submitted['sha256']) is str and SHA.fullmatch(submitted['sha256'])
         and integer(submitted['submittedEpochMs'],engine['assignedEpochMs']))
    if _snapshot:
        actual=[row for row in value['codeSources']['evaluations'] if row['url']==engine['url']]
        need(actual and all(all(row[key]==submitted[key] for key in ('encoding','codeUnits','sha256')) and row['submittedEpochMs']>=submitted['submittedEpochMs'] for row in actual))


def body(value, maximum=65536):
    exact(value,{'bytes','sha256','contentBase64'})
    need(integer(value['bytes'],0,maximum) and type(value['sha256']) is str and SHA.fullmatch(value['sha256'])
         and type(value['contentBase64']) is str and len(value['contentBase64'])<=(maximum+2)//3*4)
    raw=base64.b64decode(value['contentBase64'],validate=True)
    need(base64.b64encode(raw).decode()==value['contentBase64'] and len(raw)==value['bytes']
         and hashlib.sha256(raw).hexdigest()==value['sha256']);return raw


def clock(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs'],0));return value


def events(value,*,_snapshot=False):
    """Derive lifetime conditions from original ordered events, preserving them."""
    need(type(_snapshot) is bool)
    need(type(value['events']) is list and len(value['events'])<=1024)
    version=value['iosSnapshotPreflightHttpVersion' if _snapshot else 'iosAvatarSocialHttpVersion'];need(type(version) is int and version in ((1,) if _snapshot else READS))
    if _snapshot:version=2
    from ios.adapters import avatar_call_stack
    caller_table=avatar_call_stack.table(value['callerStacks'],value['clockBefore']['epochMs'],_snapshot=_snapshot) if version==2 else {};used_callers=set()
    histories={};states={};ids=set();replies=set();last=dict(epochMs=0,monotonicMs=0)
    for sequence,event in enumerate(value['events'],1):
        exact(event,{'sequence','eventId','xhrId','kind','clock','details'})
        need(type(event['sequence']) is int and event['sequence']==sequence)
        identifier(event['eventId']);identifier(event['xhrId']);need(event['eventId'] not in ids);ids.add(event['eventId'])
        now=clock(event['clock']);need(all(last[key]<=now[key]<=value['clockBefore'][key] for key in last));last=now
        detail=event['details'];kind=event['kind'];identifier(event['xhrId'])
        if kind=='created':
            need(event['xhrId'] not in states and len(states)<128)
            if version==2:need(type(detail) is dict and detail.get('callerStackId') in caller_table)
            actual=caller_table[detail['callerStackId']] if version==2 else None;source(detail,version,now['epochMs'],actual,_snapshot=_snapshot)
            need(detail['submitted']['submittedEpochMs']<=now['epochMs'])
            if version==2:
                history=histories.setdefault(detail['engine']['instance'],avatar_call_stack.History());history.accept(actual['callerStack']);used_callers.add(actual['id'])
            states[event['xhrId']]=dict(created=deepcopy(event),stack=[],replies={},current=None,released=False,
                timerDestroyed=False,timerActive=False,destroyed=False)
            continue
        need(event['xhrId'] in states);state=states[event['xhrId']]
        need(not state['destroyed'] or kind=='reply-destroyed')
        if kind=='sent':
            exact(detail,{'replyId','url','method','body','authorizationAttached','contentType'});identifier(detail['replyId']);endpoint(detail['url'],_snapshot=_snapshot)
            need(detail['method'] in ('GET','POST','DELETE') and type(detail['authorizationAttached']) is bool
                 and type(detail['contentType']) is str and len(detail['contentType'])<=512)
            body(detail['body'],4096)
            if _snapshot:need(detail['method']=='GET' and detail['url']==state['created']['details']['requestUrl'] and body(detail['body'],4096)==b'' and detail['contentType']=='')
            need(not state['released'] and detail['replyId'] not in replies)
            if state['current'] is not None:
                prior=state['replies'][state['current']];need(prior['finished'] is not None or prior['aborted'])
            replies.add(detail['replyId']);state['current']=detail['replyId']
            state['replies'][detail['replyId']]=dict(sent=deepcopy(event),finished=None,read=None,aborted=False,destroyed=False)
        elif kind in ('reply-finished','text-read','aborted','reply-destroyed'):
            need(type(detail) is dict and detail.get('replyId') in state['replies']);reply=state['replies'][detail['replyId']]
            need(not reply['destroyed'])
            if kind=='reply-finished':
                exact(detail,{'replyId','httpStatus','networkError','responseId','body'})
                need(not reply['aborted'] and reply['finished'] is None and integer(detail['httpStatus'],0,599)
                     and integer(detail['networkError'],0,499) and type(detail['responseId']) is str)
                if detail['responseId']:identifier(detail['responseId']);body(detail['body'],16384 if _snapshot else 65536)
                else:need(detail['body'] is None)
                reply['finished']=deepcopy(event)
            elif kind=='text-read':
                exact(detail,{'replyId','scriptSource','sha256'}|({'callerStackId'} if version==2 else set()))
                created=state['created']['details']
                original_source=created['callerChain'][0] if version==1 else caller_table[created['callerStackId']]['callerModules'][0]['url']
                need(reply['finished'] is not None and reply['read'] is None and not state['released']
                     and detail['scriptSource']==original_source
                     and type(detail['sha256']) is str and SHA.fullmatch(detail['sha256']))
                if version==2:
                    identifier(detail['callerStackId']);need(detail['callerStackId'] in caller_table);actual=caller_table[detail['callerStackId']]
                    avatar_call_stack.validate(actual['callerStack'],actual['callerModules'],now['epochMs'],required={'/modules/request.js'},_snapshot=_snapshot)
                    need(actual['callerModules'] and actual['callerModules'][0]==dict(frame=0,url=original_source))
                    if _snapshot:avatar_call_stack.evaluated(actual['callerStack'],actual['callerModules'],now['epochMs'],created['codeSources']['evaluations'],required={'/modules/request.js'},top='/modules/request.js',_snapshot=True)
                    histories[created['engine']['instance']].accept(actual['callerStack']);used_callers.add(actual['id'])
                if reply['finished']['details']['body'] is not None:need(detail['sha256']==reply['finished']['details']['body']['sha256'])
                reply['read']=deepcopy(event);reply['callbackRead']=bool(state['stack'] and state['stack'][-1]==('readystatechange',4))
            elif kind=='aborted':
                exact(detail,{'replyId'});need(not reply['aborted']);reply['aborted']=True
            else:
                exact(detail,{'replyId'});reply['destroyed']=True
        elif kind in ('callback-enter','callback-leave'):
            exact(detail,{'callback','readyState'});need(not state['released'] and detail['callback'] in ('readystatechange','timeout')
                 and integer(detail['readyState'],0,4))
            if kind=='callback-enter':need(len(state['stack'])<16);state['stack'].append((detail['callback'],detail['readyState']))
            else:need(state['stack'] and state['stack'][-1][0]==detail['callback']);state['stack'].pop()
        elif kind=='timer-state':
            exact(detail,{'active'});need(type(detail['active']) is bool and not state['timerDestroyed']);state['timerActive']=detail['active']
        elif kind=='callbacks-released':
            exact(detail,set());need(not state['released'] and not state['stack']);state['released']=True
        elif kind=='timer-destroyed':
            exact(detail,set());need(state['released'] and not state['timerDestroyed']);state['timerDestroyed']=True;state['timerActive']=False
        elif kind=='xhr-destroyed':
            exact(detail,set());need(state['released'] and state['timerDestroyed']);state['destroyed']=True
        else:need(False)
    if version==2:need(used_callers==set(caller_table))
    return states


def validate(value,query,pid,epoch=None,previous=None,*,_snapshot=False):
    command(query,_snapshot=_snapshot);marker='iosSnapshotPreflightHttpVersion' if _snapshot else 'iosAvatarSocialHttpVersion';version=value.get(marker) if type(value) is dict else None
    exact(value,{marker,'requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','events'}|({'callerStacks'} if _snapshot or version==2 else set()))
    need(type(version) is int and version in ((1,) if _snapshot else READS)
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
         and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1_000_000_000)
         and value['clockDomain']==('native-process-snapshot-preflight-http' if _snapshot else 'native-process-avatar-social-http'));identifier(value['instance'])
    before,after=clock(value['clockBefore']),clock(value['clockAfter'])
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    events(value,_snapshot=_snapshot);need(len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId'],runId=previous['runId']),pid,_snapshot=_snapshot)
        old=previous['events'];need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and version==previous[marker]
            and value['requestId']!=previous['requestId'] and len(value['events'])>=len(old) and value['events'][:len(old)]==old
            and all(before[key]>=previous['clockAfter'][key] for key in before))
        if _snapshot or version==2:
            old=previous['callerStacks'];need(len(value['callerStacks'])>=len(old) and value['callerStacks'][:len(old)]==old)
    return value


def original(value,*,_snapshot=False):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action='feature-ios-snapshot-preflight-http' if _snapshot else ACTION,runId=value.get('runId')),value.get('processId'),_snapshot=_snapshot)


def drained(value,owned_xhrs,*,_snapshot=False):
    original(value,_snapshot=_snapshot);need(type(owned_xhrs) in (list,tuple) and bool(owned_xhrs) and len(set(owned_xhrs))==len(owned_xhrs))
    actual=events(value,_snapshot=_snapshot)
    for owned in owned_xhrs:
        identifier(owned);need(owned in actual);state=actual[owned]
        if not (state['destroyed'] and state['released'] and state['timerDestroyed'] and not state['stack']
                and all(reply['destroyed'] for reply in state['replies'].values())):return False
    return True



def provider_status(value, *, instance, run, previous=None):
    """Validate provider originals in their own clock, without native equality."""
    exact(value, {'avatarSocialVersion','instance','runId','ticket','capturedEpochMs','eventSequence',
        'active','connected','pendingRoles','inflightRequests','complete','history'})
    need(type(value['avatarSocialVersion']) is int and value['avatarSocialVersion']==1
         and value['instance']==identifier(instance) and value['runId']==identifier(run)
         and integer(value['capturedEpochMs'],1) and integer(value['eventSequence'],0)
         and integer(value['inflightRequests'],0,16))
    if value['ticket'] is not None:identifier(value['ticket'])
    for key in ('active','connected','complete'):need(type(value[key]) is bool)
    need(value['complete'] and type(value['pendingRoles']) is list
         and value['pendingRoles'] in ([],['primary'],['actor'],['actor','primary'])
         and type(value['history']) is list and len(value['history'])<=1024)
    prior_sequence=prior_epoch=0;response_ids=set()
    for event in value['history']:
        exact(event, {'eventSequence','capturedEpochMs','runId','ticket','kind','responseId','role','method',
            'path','query','bodyBytes','bodySha256','status','responseBytes','responseSha256','written','writeEpochMs'})
        identifier(event['responseId']);identifier(event['ticket'])
        need(event['runId']==run and event['kind']=='request' and event['role'] in ('primary','actor')
             and event['method'] in ('GET','POST','DELETE') and event['responseId'] not in response_ids
             and integer(event['eventSequence'],prior_sequence+1,value['eventSequence'])
             and integer(event['capturedEpochMs'],max(1,prior_epoch),value['capturedEpochMs'])
             and integer(event['bodyBytes'],0,4096) and type(event['bodySha256']) is str and SHA.fullmatch(event['bodySha256'])
             and type(event['written']) is bool and type(event['path']) is str and type(event['query']) is str)
        endpoint('https://original.invalid'+event['path']+('?' + event['query'] if event['query'] else ''))
        if event['status'] is None:
            need(event['responseBytes'] is event['responseSha256'] is event['writeEpochMs'] is None and not event['written'])
        else:
            need(integer(event['status'],100,599) and integer(event['responseBytes'],0,65536)
                 and type(event['responseSha256']) is str and SHA.fullmatch(event['responseSha256']))
            if event['written']:need(integer(event['writeEpochMs'],event['capturedEpochMs'],value['capturedEpochMs']))
            else:need(event['writeEpochMs'] is None)
        response_ids.add(event['responseId']);prior_sequence=event['eventSequence'];prior_epoch=event['capturedEpochMs']
    if previous is not None:
        provider_status(previous,instance=instance,run=run)
        old=previous['history'];need(value['capturedEpochMs']>=previous['capturedEpochMs']
            and value['eventSequence']>=previous['eventSequence'] and len(value['history'])>=len(old)
            and value['history'][:len(old)]==old and (previous['active'] or not value['active']))
    return value


def consumed_responses(value, status, *, provider_instance, owned_origin, run, ticket, role,
                      after_native_epoch, after_provider_epoch, after_event):
    """Join written provider bytes to the real request.js responseText read.

    This proves neither JSON parse success, materialized relationship rows nor
    peer consent. Those require their own original model/lifetime sources.
    Native and provider barriers are separate; their timestamps are not equal.
    """
    original(value);provider_status(status,instance=provider_instance,run=run);identifier(ticket)
    origin=urlsplit(owned_origin)
    need(origin.scheme=='https' and origin.hostname and not origin.path and not origin.query and not origin.fragment
         and origin.username is None and origin.password is None and role in ('primary','actor')
         and status['active'] and status['ticket']==ticket and value['runId']==run
         and integer(after_native_epoch,1) and integer(after_provider_epoch,1) and integer(after_event,0))
    receipts={row['responseId']:row for row in status['history'] if row['role']==role and row['ticket']==ticket
              and row['written'] and row['status']==200 and row['writeEpochMs']>=after_provider_epoch}
    found=[]
    for xhr,state in events(value).items():
        created=state['created'];source=created['details']
        if created['sequence']<=after_event or created['clock']['epochMs']<after_native_epoch:continue
        for reply in state['replies'].values():
            finished,read=reply['finished'],reply['read'];sent=reply['sent']['details']
            if finished is None or read is None or not reply.get('callbackRead') or reply['aborted']:continue
            data=finished['details'];receipt=receipts.get(data['responseId'])
            if (receipt is None or data['httpStatus']!=200 or data['networkError']!=0 or data['body'] is None
                    or not sent['authorizationAttached'] or sent['method']!=source['method']
                    or sent['url']!=source['requestUrl']):continue
            url=urlsplit(sent['url'])
            if origin.scheme!=url.scheme or origin.netloc!=url.netloc:continue
            if (receipt['method']!=sent['method'] or receipt['path']!=url.path or receipt['query']!=url.query
                    or receipt['bodyBytes']!=sent['body']['bytes'] or receipt['bodySha256']!=sent['body']['sha256']
                    or receipt['responseBytes']!=data['body']['bytes'] or receipt['responseSha256']!=data['body']['sha256']):continue
            found.append(dict(xhrId=xhr,nativeCreated=deepcopy(created),nativeSent=deepcopy(reply['sent']),
                nativeReply=deepcopy(finished),nativeRead=deepcopy(read),http=deepcopy(receipt)))
    return found


def consumed_response(value, status, **kwargs):
    """Compatible latest-response facade over untouched original candidates."""
    found=consumed_responses(value,status,**kwargs);need(bool(found));return found[-1]


class IOSAvatarSocialHttp(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAvatarSocialHttpAcquisitionVersion'
