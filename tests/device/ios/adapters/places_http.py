"""Original native Places XHR/lifetime history and independent directory join."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
from types import BuiltinFunctionType
from urllib.parse import urlsplit,unquote

from adapters.native_feature_observation import decode,exact,fresh,integer,need
from feature_journeys.navigation_fixture import configuration,validate_status,DIRECTORY_MARKER
from feature_journeys.fixtures import context
from ios.adapters.places_model import IOSPlacesModel,current as current_model

VERSION=1
ACTION='feature-ios-places-http'
FILE='feature-ios-places-http.json'
LIMIT=262144
HEX=re.compile('[a-f0-9]{32}\\Z')
SHA=re.compile('[a-f0-9]{64}\\Z')

# Immutable born pattern scans the CURRENT exact string, never a verdict memo.
# Changed module aliases/ord retain the literal original character loop.
_INSTALLED_CONTROLS=re.compile(r'[\x00-\x1f\x7f]')
_INSTALLED_CONTROLS_BIRTH=_INSTALLED_CONTROLS
_INSTALLED_PATTERN_TYPE=type(_INSTALLED_CONTROLS)
_INSTALLED_ORD=ord


def identifier(value):need(type(value) is str and HEX.fullmatch(value));return value


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    identifier(value['runId']);return value


def installed(value,suffix):
    need(type(value) is str and len(value)<=4096 and (
        _INSTALLED_CONTROLS.search(value) is None
        if (_INSTALLED_CONTROLS is _INSTALLED_CONTROLS_BIRTH and type(_INSTALLED_CONTROLS) is _INSTALLED_PATTERN_TYPE
            and type(_INSTALLED_ORD) is BuiltinFunctionType and _INSTALLED_ORD.__module__=='builtins'
            and _INSTALLED_ORD.__name__=='ord' and ord is _INSTALLED_ORD)
        else all(ord(c)>=32 and ord(c)!=127 for c in value)))
    url=urlsplit(value);path=unquote(url.path,encoding='utf-8',errors='strict')
    need(url.scheme in ('qrc','file') and not url.netloc and not url.query and not url.fragment and path.endswith(suffix)
         and not any(part in ('.','..') for part in path.split('/')))
    return value


def directory(value):
    need(type(value) is str and len(value)<=4096 and all(ord(c)>32 and ord(c)!=127 for c in value))
    url=urlsplit(value);url.port
    need(url.scheme in ('http','https') and url.hostname and url.username is None and url.password is None
         and url.path=='/api/v1/places' and url.query=='status=online&per_page=1000' and not url.fragment)
    return value


def signature(value):
    need(type(value) is str and len(value)==24)
    raw=base64.b64decode(value,validate=True);need(len(raw)==16 and base64.b64encode(raw).decode()==value);return value


def source(value):
    exact(value,{'scriptSource','engine','submitted','requestUrl','protocolSignature'})
    installed(value['scriptSource'],'/system/places/places.js');directory(value['requestUrl']);signature(value['protocolSignature'])
    engine=value['engine'];exact(engine,{'instance','assigned','url','loadGeneration','assignedEpochMs'})
    identifier(engine['instance']);need(engine['assigned'] is True and integer(engine['loadGeneration'],1)
         and integer(engine['assignedEpochMs'],1));installed(engine['url'],'/defaultScripts.js')
    submitted=value['submitted'];exact(submitted,{'submitted','encoding','codeUnits','sha256','submittedEpochMs'})
    need(submitted['submitted'] is True and submitted['encoding']=='utf-16le-code-units'
         and integer(submitted['codeUnits'],1,4194304) and type(submitted['sha256']) is str and SHA.fullmatch(submitted['sha256'])
         and integer(submitted['submittedEpochMs'],engine['assignedEpochMs']))


def body(value):
    exact(value,{'bytes','sha256','contentBase64'})
    need(integer(value['bytes'],0,4096) and type(value['sha256']) is str and SHA.fullmatch(value['sha256'])
         and type(value['contentBase64']) is str and len(value['contentBase64'])<=5464)
    raw=base64.b64decode(value['contentBase64'],validate=True)
    need(base64.b64encode(raw).decode()==value['contentBase64'] and len(raw)==value['bytes']
         and hashlib.sha256(raw).hexdigest()==value['sha256']);return raw


def clock(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs'],0));return value


def events(value):
    """Derive lifetime conditions from original ordered events, preserving them."""
    need(type(value['events']) is list and len(value['events'])<=1024)
    states={};ids=set();replies=set();last=dict(epochMs=0,monotonicMs=0)
    for sequence,event in enumerate(value['events'],1):
        exact(event,{'sequence','eventId','xhrId','kind','clock','details'})
        need(type(event['sequence']) is int and event['sequence']==sequence)
        identifier(event['eventId']);identifier(event['xhrId']);need(event['eventId'] not in ids);ids.add(event['eventId'])
        now=clock(event['clock']);need(all(last[key]<=now[key]<=value['clockBefore'][key] for key in last));last=now
        detail=event['details'];kind=event['kind'];identifier(event['xhrId'])
        if kind=='created':
            need(event['xhrId'] not in states and len(states)<128);source(detail)
            need(detail['submitted']['submittedEpochMs']<=now['epochMs'])
            states[event['xhrId']]=dict(created=deepcopy(event),stack=[],replies={},current=None,released=False,
                timerDestroyed=False,timerActive=False,destroyed=False)
            continue
        need(event['xhrId'] in states);state=states[event['xhrId']]
        need(not state['destroyed'] or kind=='reply-destroyed')
        if kind=='sent':
            exact(detail,{'replyId','url'});identifier(detail['replyId']);directory(detail['url'])
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
                if detail['responseId']:identifier(detail['responseId']);body(detail['body'])
                else:need(detail['body'] is None)
                reply['finished']=deepcopy(event)
            elif kind=='text-read':
                exact(detail,{'replyId','scriptSource','sha256'})
                need(reply['finished'] is not None and reply['read'] is None and not state['released']
                     and detail['scriptSource']==state['created']['details']['scriptSource']
                     and type(detail['sha256']) is str and SHA.fullmatch(detail['sha256']))
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
    return states


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosPlacesHttpVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','events'})
    need(type(value['iosPlacesHttpVersion']) is int and value['iosPlacesHttpVersion']==VERSION
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
         and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1_000_000_000)
         and value['clockDomain']=='native-process-places-http');identifier(value['instance'])
    before,after=clock(value['clockBefore']),clock(value['clockAfter'])
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    events(value);need(len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId'],runId=previous['runId']),pid)
        old=previous['events'];need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and len(value['events'])>=len(old) and value['events'][:len(old)]==old
            and all(before[key]>=previous['clockAfter'][key] for key in before))
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def drained(value,owned_xhrs):
    original(value);need(type(owned_xhrs) in (list,tuple) and bool(owned_xhrs) and len(set(owned_xhrs))==len(owned_xhrs))
    actual=events(value)
    for owned in owned_xhrs:
        identifier(owned);need(owned in actual);state=actual[owned]
        if not (state['destroyed'] and state['released'] and state['timerDestroyed'] and not state['stack']
                and all(reply['destroyed'] for reply in state['replies'].values())):return False
    return True


def consumed(value,model,*,provider_status,provider_instance,inputs,owned_origin,run,ticket,after_epoch,provider_after_epoch,after_event):
    """Join originals: server body, native Places text-read and actual QML row.

    A text read alone is not parser success. This join requires the independent
    materialized record and supports the ordinary visible directory stage.
    """
    original(value);identifier(run);identifier(ticket);need(integer(after_epoch,1) and integer(provider_after_epoch,1) and integer(after_event,0))
    configuration(inputs);validate_status(provider_status,instance=provider_instance,run=run,inputs=inputs)
    need(provider_status['active'] and provider_status['ticket']==ticket and value['runId']==run
         and provider_after_epoch<=provider_status['capturedEpochMs'])
    actual=current_model(model);need(model['processId']==value['processId'] and model['runId']==run and not actual['loading']
        and actual['lists']['places']['visible'] and actual['tab']==0)
    expected_url=owned_origin+'/api/v1/places?status=online&per_page=1000';directory(expected_url)
    receipts={row['responseId']:row for row in provider_status['responses'] if row['kind']=='directory' and row['ticket']==ticket}
    found=[];ctx=context(run)
    for xhr,state in events(value).items():
        created=state['created'];source=created['details']
        if created['sequence']<=after_event or created['clock']['epochMs']<after_epoch or source['requestUrl']!=expected_url:continue
        if source['protocolSignature']!=inputs['protocolSignature']:continue
        for reply in state['replies'].values():
            finished,read=reply['finished'],reply['read']
            if finished is None or read is None or not reply.get('callbackRead') or reply['aborted']:continue
            data=finished['details'];receipt=receipts.get(data['responseId'])
            if receipt is None or data['httpStatus']!=200 or data['networkError']!=0 or data['body'] is None:continue
            if reply['sent']['details']['url']!=expected_url or receipt['completedEpochMs']<provider_after_epoch:continue
            if data['body']['sha256']!=receipt['sha256'] or data['body']['bytes']!=receipt['bytes']:continue
            if not read['clock']['epochMs']<=model['clockBefore']['epochMs']<read['clock']['epochMs']+5000:continue
            document=decode(body(data['body']).decode('utf-8'))
            need(type(document) is dict and document.get('status')=='success' and type(document.get('data')) is dict)
            entries=document['data'].get('places');need(type(entries) is list)
            wire=[entry for entry in entries if type(entry) is dict and entry.get('id')==ctx['destination']];need(len(wire)==1)
            wire=wire[0];need(wire.get('name')==ctx['name'] and wire.get('address')==configuration(inputs)[1]['B']
                 and wire.get('description')==DIRECTORY_MARKER+data['responseId']
                 and type(wire.get('domain')) is dict and wire['domain'].get('protocol_version')==source['protocolSignature'])
            records=[row for row in actual['records'] if row.get('id')==wire['id']]
            rows=[row for row in actual['lists']['places']['rows'] if row['placeId']==wire['id']]
            need(len(records)==len(rows)==1)
            record,row=records[0],rows[0]
            need(record.get('name')==wire['name'] and record.get('address')==wire['address'] and record.get('metaverseServer')==owned_origin
                 and record.get('description')==wire['description']
                 and row['placeName']==record['name'] and row['placeAddress']==record['address']
                 and row['placeDescription']==record.get('description') and row['attendance']==record.get('current_attendance')
                 and row['capacity']==record.get('capacity'))
            found.append(dict(xhrId=xhr,nativeCreated=deepcopy(created),nativeReply=deepcopy(finished),
                nativeRead=deepcopy(read),http=deepcopy(receipt),rootId=actual['rootId'],record=deepcopy(record),row=deepcopy(row)))
    need(bool(found));return found[-1]


class IOSPlacesHttp(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosPlacesHttpAcquisitionVersion'
