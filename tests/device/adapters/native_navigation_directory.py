"""Original Places response read, outgoing queue and actual QML records provenance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.native_navigation_replies import origin
from adapters.native_script_observation import validate_code
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import nonce
from adapters.token_places_ui import snapshot as places_packet, sha
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import configuration, validate_status
from navigation_observation import viewpoint_urls

VERSION=1
FILE='feature-navigation-directory.json'
HEX=r'[0-9a-f]{32}'


def identifier(value):return type(value) is str and re.fullmatch(HEX,value) is not None

def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-navigation-directory'
         and identifier(value['commandId']) and identifier(value['runId']))
    return value


def profile(value):
    exact(value,{'sourceRevision','scriptUrlSha256','codeSha256','codeUnits'})
    need(type(value['sourceRevision']) is str and re.fullmatch('[0-9a-f]{40}',value['sourceRevision'])
         and digest(value['scriptUrlSha256']) and digest(value['codeSha256']) and integer(value['codeUnits'],1,4194304))
    return value


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'navigationDirectoryVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','ui','reads','messages','roots'})
    need(type(value['navigationDirectoryVersion']) is int and value['navigationDirectoryVersion']==VERSION
         and value['commandId']==request['commandId'] and value['runId']==request['runId'] and identifier(value['instance'])
         and integer(value['sequence'],1,4096) and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and all(type(value[k]) is list and len(value[k])<=128 for k in ('reads','messages','roots')))
    fresh(value['capturedEpochMs'],epoch);ui=value['ui']
    exact(ui,{'bridgeId','generation','sequence','elapsedMs','observedEpochMs'})
    need(nonce(ui['bridgeId']) and nonce(ui['generation']) and integer(ui['sequence']) and integer(ui['elapsedMs'])
         and integer(ui['observedEpochMs'],1) and 0<=value['capturedEpochMs']-ui['observedEpochMs']<=1500)
    reads={};responses=set();previous=0
    for row in value['reads']:
        exact(row,{'readId','runId','responseId','origin','httpStatus','networkError','bytes','sha256','readEpochMs',
            'managerInstance','loadGeneration','scriptUrlSha256','code','idSha256','nameSha256','addressSha256','protocolSha256','maturity'})
        need(all(identifier(row[k]) for k in ('readId','runId','responseId','managerInstance'))
             and row['readId'] not in reads and row['responseId'] not in responses
             and type(row['httpStatus']) is int and row['httpStatus']==200 and type(row['networkError']) is int and row['networkError']==0
             and integer(row['bytes'],1,1048576) and integer(row['readEpochMs'],max(1,previous),value['capturedEpochMs'])
             and integer(row['loadGeneration'],1,2**53-1) and row['maturity']=='everyone'
             and all(digest(row[k]) for k in ('sha256','scriptUrlSha256','idSha256','nameSha256','addressSha256','protocolSha256')))
        origin(row['origin']);validate_code(row['code'],row['readEpochMs']);need(row['code']['submitted'])
        reads[row['readId']]=row;responses.add(row['responseId']);previous=row['readEpochMs']
    roots={}
    for row in value['roots']:
        exact(row,{'rootId','alive','current','sourceSha256','revision','frameRevision','lastMessageId','recordsSha256'})
        need(identifier(row['rootId']) and row['rootId'] not in roots and digest(row['sourceSha256'])
             and type(row['alive']) is bool and type(row['current']) is bool and (not row['current'] or row['alive'])
             and integer(row['revision']) and integer(row['frameRevision'],0,row['revision']) and (row['lastMessageId'] is None or identifier(row['lastMessageId']))
             and (row['recordsSha256'] is None if row['revision']==0 else digest(row['recordsSha256'])))
        roots[row['rootId']]=row
    need(sum(r['current'] for r in roots.values())<=1)
    messages={};previous=0
    for row in value['messages']:
        exact(row,{'messageId','readId','outgoingEpochMs','recordsSha256','targetRootId','deliveredRootId','deliveredEpochMs'})
        need(identifier(row['messageId']) and row['messageId'] not in messages and row['readId'] in reads
             and integer(row['outgoingEpochMs'],max(1,previous,reads[row['readId']]['readEpochMs']),value['capturedEpochMs'])
             and digest(row['recordsSha256']) and (row['targetRootId']=='' or row['targetRootId'] in roots))
        if row['deliveredRootId'] is None:need(row['deliveredEpochMs'] is None)
        else:
            need(row['deliveredRootId']==row['targetRootId'] and row['deliveredRootId'] in roots
                 and integer(row['deliveredEpochMs'],row['outgoingEpochMs'],value['capturedEpochMs']))
        messages[row['messageId']]=row;previous=row['outgoingEpochMs']
    for root in roots.values():
        if root['lastMessageId'] is not None:
            need(root['lastMessageId'] in messages)
            message=messages[root['lastMessageId']]
            need(message['deliveredRootId']==root['rootId'] and message['recordsSha256']==root['recordsSha256'] and root['revision']>0)
    return value


def continuation(previous,current):
    need(previous['instance']==current['instance'] and previous['processId']==current['processId']
         and current['sequence']>previous['sequence'] and current['capturedEpochMs']>=previous['capturedEpochMs']
         and current['ui']['bridgeId']==previous['ui']['bridgeId']
         and all(current['ui'][k]>=previous['ui'][k] for k in ('sequence','elapsedMs','observedEpochMs'))
         and current['reads'][:len(previous['reads'])]==previous['reads'] and len(current['messages'])>=len(previous['messages']))
    for old,new in zip(previous['messages'],current['messages']):
        need(all(old[k]==new[k] for k in set(old)-{'deliveredRootId','deliveredEpochMs'})
             and (old['deliveredRootId'] is None or old==new))
    roots={row['rootId']:row for row in current['roots']}
    for old in previous['roots']:
        need(old['rootId'] in roots);new=roots[old['rootId']]
        need(new['sourceSha256']==old['sourceSha256'] and new['revision']>=old['revision'] and new['frameRevision']>=old['frameRevision'] and (old['alive'] or not new['alive']))
        if new['revision']==old['revision']:need(new['lastMessageId']==old['lastMessageId'] and new['recordsSha256']==old['recordsSha256'])


def joined_directory(native,places,status,*,run,ticket,after_epoch,owned_origin,provider_instance,provider_inputs,source_profile,visible=True,receipt_ticket=None):
    profile(source_profile);configuration(provider_inputs);origin(owned_origin);places_packet(places)
    need(type(native) is dict)
    validate(native,dict(schemaVersion=1,commandId=native.get('commandId'),action='feature-navigation-directory',runId=run),
        places['scope']['processId'],native.get('capturedEpochMs'))
    receipt_ticket=ticket if receipt_ticket is None else receipt_ticket;need(identifier(receipt_ticket))
    validate_status(status,instance=provider_instance,run=run,inputs=provider_inputs)
    need(source_profile['sourceRevision']==provider_inputs['sourceRevision'] and native['runId']==run
         and type(visible) is bool and integer(after_epoch,1) and identifier(ticket) and status['active'] and status['ticket']==ticket)
    ui=native['ui'];scope=places['scope']
    need(places['ready'] and places['open'] and ui['bridgeId']==scope['instance'] and ui['generation']==scope['generation']
         and ui['sequence']==scope['sequence'] and native['processId']==scope['processId']
         and 0<=native['capturedEpochMs']-places['observedEpochMs']<=1500)
    pages=[row for row in places['controls'] if row['id']=='places.page'];need(len(pages)==1);page=pages[0]
    need(not page['loading'] and page['tab']==0 and not page['dialog']['visible']
         and page['queueCount']==0 and not page['dispatchTimerRunning'] and 'everyone' in page['maturity'])
    roots=[r for r in native['roots'] if r['rootId']==page['rootInstance'] and r['alive'] and r['current']
           and r['sourceSha256']==page['componentSourceSha256']];need(len(roots)==1);root=roots[0]
    messages=[m for m in native['messages'] if m['messageId']==root['lastMessageId'] and m['deliveredRootId']==root['rootId']];need(len(messages)==1)
    message=messages[0]
    need(root['frameRevision']==root['revision'] and places['observedEpochMs']>=message['deliveredEpochMs']
         and native['ui']['observedEpochMs']>=message['deliveredEpochMs'])
    reads=[r for r in native['reads'] if r['readId']==message['readId']];need(len(reads)==1);read=reads[0]
    receipts=[r for r in status['responses'] if r['responseId']==read['responseId'] and r['ticket']==receipt_ticket
              and r['kind']=='directory' and r['status']==200 and r['completedEpochMs']>=after_epoch];need(len(receipts)==1);receipt=receipts[0]
    need(read['runId']==run and read['origin']==owned_origin and read['readEpochMs']>=after_epoch
         and all(read[k]==receipt[k] for k in ('bytes','sha256')) and read['scriptUrlSha256']==source_profile['scriptUrlSha256']
         and read['code']['sha256']==source_profile['codeSha256'] and read['code']['codeUnits']==source_profile['codeUnits']
         and read['protocolSha256']==sha(provider_inputs['protocolSignature']) and read['idSha256']==sha(context(run)['destination'])
         and read['nameSha256']==sha(context(run)['name']) and read['addressSha256']==sha(viewpoint_urls(provider_inputs['sceneUrl'])['B']))
    rows=[r for r in page['directory']['rows'] if r['placeIdSha256']==read['idSha256']]
    need(len(rows)==(1 if visible else 0))
    if rows:need(rows[0]['placeNameSha256']==read['nameSha256'] and rows[0]['placeAddressSha256']==read['addressSha256'])
    return dict(read=deepcopy(read),message=deepcopy(message),root=deepcopy(root),receipt=deepcopy(receipt))


class NativeNavigationDirectory:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=None;self.requests=set()
    def read(self,run):
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-navigation-directory',runId=run)
        try:
            command(request);need(len(self.requests)<4096 and request['commandId'] not in self.requests)
            self.requests.add(request['commandId']);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));self.send(deepcopy(request))
            for attempt in range(51):
                now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                previous=now;raw=self.original()
                try:value=decode(raw) if raw else None
                except (ValueError,NativeUIError):value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms())
                    if self.last is not None:continuation(self.last,value)
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                    self.last=deepcopy(value);return value
                now=self.monotonic();need(number(now,0,1e15) and previous<=now);previous=now
                if now-started>=5 or attempt==50:break
                self.sleep(min(.1,5-(now-started)))
        except Exception:raise NativeUIError('Original directory provenance source failed') from None
        raise NativeUIError('Original directory provenance source failed')
